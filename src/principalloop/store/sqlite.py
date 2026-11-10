"""Journal, observation projection and outbox in one local transaction.

Delivery and attestation producers arrive with their own tickets.
Here no observation event ever commands the plan.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
from uuid import uuid4

from ..domain.contracts import validate_contract
from ..domain.machine import advance, propose
from ..domain.types import Action, Checks, Command, Decision, Mode, Plan, Principal, Role, Trajectory
from ..runtime import runtime_admitted
from .errors import StoreError
from .codec import decode, encode, values
from .locking import WriterLock
from .migrations import VERSION
from .schema import LATEST_VERSION, inspect, migrate
from .paths import prepare_parent, private_path


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def require_runtime():
    if not runtime_admitted():
        raise StoreError("RUNTIME_UNQUALIFIED", "Requires CPython 3.13 with a patched SQLite; run principalloop doctor")


def open_writer(database):
    """Bounded retry of Windows WAL recovery only, before any application command.

    Forced owner termination can briefly yield SQLITE_IOERR_TRUNCATE on reopening.
    Never retry a commit, a migration, corruption, or another I/O error here.
    """
    for attempt in range(3):
        connection = sqlite3.connect(database, autocommit=True, timeout=1)
        connection.row_factory = sqlite3.Row
        try:
            version = inspect(connection)
            return connection, version
        except BaseException as error:
            connection.close()
            if not (os.name == "nt" and isinstance(error, sqlite3.OperationalError)
                    and getattr(error, "sqlite_errorname", "") == "SQLITE_IOERR_TRUNCATE" and attempt < 2):
                raise
            time.sleep(0.05 * (attempt + 1))


class SystemClock:
    def now(self):
        return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Receipt:
    event_seq: int
    event_id: str
    duplicate: bool


class Reader:
    """Read only; never creates a missing database and never migrates."""

    def __init__(self, database: Path, *, workspace: Path):
        require_runtime()
        self.workspace = workspace.resolve(strict=True)
        self.database = private_path(database, self.workspace)
        self._pid = os.getpid()
        self._connection = sqlite3.connect(self.database.as_uri() + "?mode=ro", uri=True,
                                           autocommit=True, timeout=1)
        self._connection.row_factory = sqlite3.Row
        try:
            self._connection.execute("PRAGMA query_only=ON")
            if inspect(self._connection) != LATEST_VERSION:
                raise StoreError("MIGRATION_REQUIRED", "Open the database with Store to migrate before reading")
            self._check_workspace()
        except BaseException:
            self.close()
            raise

    def _guard(self):
        if self._connection is None or self._pid != os.getpid():
            raise StoreError("STORE_CLOSED", "Store is closed or inherited by another process")

    @property
    def snapshots(self):
        from ..snapshot.engine import Snapshots
        self._guard()
        return Snapshots(self)

    def _check_workspace(self):
        row = self._connection.execute("SELECT workspace FROM projects").fetchone()
        if row and os.path.normcase(row[0]) != os.path.normcase(str(self.workspace)):
            raise StoreError("WORKSPACE_MISMATCH", "Database belongs to another workspace")

    def status(self) -> dict:
        self._guard()
        # One read transaction prevents a mixed status across concurrent commits.
        self._connection.execute("BEGIN")
        try:
            project = self._connection.execute("SELECT * FROM projects").fetchone()
            events = self._connection.execute("SELECT count(*), coalesce(max(event_seq), 0) FROM events").fetchone()
            views = [dict(row) for row in self._connection.execute(
                "SELECT producer_key, event_seq, body_json FROM producer_views ORDER BY producer_key")]
            for view in views:
                view["event"] = json.loads(view.pop("body_json"))
            plan = decode(project["plan_json"], Plan) if project else None
            return {"storage_version": LATEST_VERSION, "project_id": project["project_id"] if project else None,
                    "mode": plan.mode if plan else "SHADOW", "plan_epoch": plan.epoch if plan else None,
                    "owner": plan.owner if plan else None,
                    "director": "NOT_CONNECTED", "snapshot": "AVAILABLE",
                    "snapshot_count": self._connection.execute("SELECT count(*) FROM snapshots").fetchone()[0],
                    "mission_revision": project["mission_revision"] if project else None,
                    "event_count": events[0], "last_event_seq": events[1],
                    "outbox_count": self._connection.execute("SELECT count(*) FROM outbox").fetchone()[0],
                    "outbox_delivery": "NOT_IMPLEMENTED", "observations": views}
        finally:
            self._connection.execute("ROLLBACK")

    def mission(self) -> dict | None:
        self._guard()
        row = self._connection.execute("SELECT body_json FROM mission_revisions ORDER BY revision DESC LIMIT 1").fetchone()
        return json.loads(row[0]) if row else None

    def plan(self) -> Plan:
        self._guard()
        row = self._connection.execute("SELECT plan_json FROM projects").fetchone()
        if row is None:
            raise StoreError("NOT_INITIALIZED", "Initialize a mission first")
        return decode(row[0], Plan)

    def decision(self, proposal_id: str) -> Decision:
        self._guard()
        row = self._connection.execute("SELECT state_json FROM decisions WHERE proposal_id=?", (proposal_id,)).fetchone()
        if row is None:
            raise StoreError("NOT_FOUND", "Unknown proposal")
        return decode(row[0], Decision)

    def proposal(self, proposal_id: str) -> dict:
        self._guard()
        row = self._connection.execute("SELECT proposal_json FROM decisions WHERE proposal_id=?", (proposal_id,)).fetchone()
        if row is None:
            raise StoreError("NOT_FOUND", "Unknown proposal")
        return json.loads(row[0])

    def journal(self, *, after: int = 0, limit: int = 100) -> list[dict]:
        self._guard()
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 1000:
            raise StoreError("INVALID_CURSOR", "after >= 0 and 1 <= limit <= 1000 required")
        rows = self._connection.execute("SELECT * FROM events WHERE event_seq > ? ORDER BY event_seq LIMIT ?",
                                        (after, limit)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["request"] = json.loads(item.pop("request_json"))
            item["outcome"] = json.loads(item.pop("outcome_json"))
            result.append(item)
        return result

    def outbox(self, *, after: int = 0, limit: int = 100) -> list[dict]:
        self._guard()
        if type(after) is not int or after < 0 or type(limit) is not int or not 1 <= limit <= 1000:
            raise StoreError("INVALID_CURSOR", "after >= 0 and 1 <= limit <= 1000 required")
        return [{"message_id": row[0], "event_seq": row[1], "topic": row[2], "body": json.loads(row[3])}
                for row in self._connection.execute(
                    "SELECT message_id, event_seq, topic, body_json FROM outbox WHERE event_seq > ? ORDER BY event_seq LIMIT ?",
                    (after, limit))]

    def backup(self, target: Path) -> Path:
        """Consistent copy through the SQLite backup API; never a copy of a live WAL file."""
        self._guard()
        target = private_path(target, self.workspace)
        prepare_parent(target)
        # Exclusive creation prevents overwriting either an existing backup or the source.
        descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
        try:
            destination = sqlite3.connect(target, autocommit=True)
            try:
                deadline = time.monotonic() + 15
                def progress(_status, _remaining, _total):
                    if time.monotonic() > deadline:
                        raise StoreError("BACKUP_TIMEOUT", "Backup exceeded its 15 second deadline")
                self._connection.backup(destination, pages=256, progress=progress, sleep=0.05)
                if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise StoreError("BACKUP_INVALID", "SQLite integrity check failed")
            finally:
                destination.close()
        except BaseException:
            # Only the file exclusively created by this call is removed, never a directory.
            target.unlink(missing_ok=True)
            raise
        return target

    def close(self):
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class Store(Reader):
    """Single controlled writer. One instance = one owning thread and process.

    _fault is only an internal test injection point, not an extension
    or a callback supplied by an agent. No external I/O inside a transaction.
    """

    def __init__(self, database: Path, *, workspace: Path, clock=None, _fault=None):
        require_runtime()
        self.workspace = workspace.resolve(strict=True)
        self.database = private_path(database, self.workspace)
        self._pid = os.getpid()
        self._connection = None
        self._lock = None
        self.clock = clock or SystemClock()
        self._fault = _fault or (lambda _: None)
        prepare_parent(self.database)
        lock_path = private_path(self.database.with_name(self.database.name + ".writer.lock"), self.workspace)
        self._lock = WriterLock(lock_path)
        try:
            # Restrictive creation on POSIX; Windows uses the enclosing user's ACL.
            fd = os.open(self.database, os.O_CREAT | os.O_RDWR, 0o600)
            os.close(fd)
            self._connection, previous_version = open_writer(self.database)
            if previous_version:
                self._check_workspace()
            if self._connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] != "wal":
                raise StoreError("PRAGMA_FAILED", "WAL could not be enabled")
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._connection.execute("PRAGMA synchronous=FULL")
            if self._connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1 or self._connection.execute(
                    "PRAGMA synchronous").fetchone()[0] != 2:
                raise StoreError("PRAGMA_FAILED", "foreign_keys ON and synchronous FULL are required")
            if previous_version == 1:
                self.backup(self.database.with_name(f"before-storage-v2-{uuid4().hex}.sqlite3"))
            migrate(self._connection, self._fault)
            self._check_workspace()
        except BaseException:
            self.close()
            raise

    def close(self):
        try:
            super().close()
        finally:
            if self._lock is not None:
                self._lock.close()
                self._lock = None

    def initialize(self, mission, principal: Principal, *, event_id: str = "MISSION-1", mode: Mode = Mode.SHADOW) -> Receipt:
        body = validate_contract("mission", mission)
        if principal.role != Role.HUMAN:
            raise StoreError("FORBIDDEN", "Only trusted human context can initialize a mission")
        if not isinstance(mode, Mode) or mode == Mode.ENFORCED:
            raise StoreError("CAPABILITY_UNPROVEN", "Only SHADOW or explicitly cooperative local state is supported")
        return self._write("MISSION_INITIALIZED", event_id, {"project_id": body["project_id"], "mission": body, "mode": mode}, principal)

    def record_event(self, event, principal: Principal) -> Receipt:
        body = validate_contract("event", event)
        if principal.role != Role.EXECUTOR:
            raise StoreError("FORBIDDEN", "Observation ingestion requires trusted executor context")
        return self._write("EVENT_RECORDED", body["event_id"], body, principal)

    def register_proposal(self, proposal, principal: Principal, *, event_id: str, review_id: str | None = None) -> Receipt:
        body = validate_contract("decision-proposal", proposal)
        propose(body, principal)  # Typed role/project checks; payload cannot supply authority.
        self.snapshots.check_read_set(body)
        request = {"project_id": body["project_id"], "proposal": body, "review_id": review_id} if review_id is not None else body
        return self._write("PROPOSAL_REGISTERED", event_id, request, principal)

    def apply(self, proposal_id: str, command: Command, principal: Principal, *, event_id: str,
              checks: Checks = Checks()) -> Receipt:
        """API interne du futur noyau. Checks ne doit jamais provenir du transport JSON."""
        body = {"project_id": principal.project_id, "proposal_id": proposal_id, "command": values(command)}
        return self._write("DECISION_ADVANCED", event_id, body, principal, command=command, checks=checks)

    def _write(self, operation: str, event_id: str, body: dict, principal: Principal,
               *, command: Command | None = None, checks: Checks = Checks(), _prepare=None, _persist=None) -> Receipt:
        self._guard()
        if not isinstance(event_id, str) or not 1 <= len(event_id) <= 128 or any(c.isspace() for c in event_id):
            raise StoreError("INVALID_ID", "Event ID must be 1..128 non-whitespace characters")
        if principal.project_id != body["project_id"]:
            raise StoreError("PROJECT_MISMATCH", "Authenticated project does not match the payload")
        producer = canonical([principal.actor_id, principal.run_id])
        request = canonical({"storage_version": VERSION, "operation": operation, "body": body,
                             "principal": {"actor_id": principal.actor_id, "role": principal.role,
                                           "run_id": principal.run_id, "project_id": principal.project_id}})
        digest = hashlib.sha256(request.encode("utf-8")).hexdigest()
        connection = self._connection
        connection.execute("BEGIN IMMEDIATE")
        try:
            previous = connection.execute(
                "SELECT event_seq, request_sha256, request_json FROM events WHERE project_id=? AND producer_key=? AND event_id=?",
                (principal.project_id, producer, event_id)).fetchone()
            if previous:
                if previous[1] != digest or previous[2] != request:
                    raise StoreError("ID_CONFLICT", "Same producer and event ID have different content")
                receipt = Receipt(previous[0], event_id, True)
            else:
                project = connection.execute("SELECT project_id FROM projects").fetchone()
                outcome = {}
                transition = None
                if operation == "MISSION_INITIALIZED":
                    if project:
                        raise StoreError("ALREADY_INITIALIZED", "Mission changes require a future authorized command")
                    mission = body["mission"]
                    plan = Plan(principal.project_id, mission["mission_revision"], 1, 0,
                                tuple((scope, Trajectory.RUNNING) for scope in mission["scope"]), Mode(body["mode"]))
                    connection.execute("INSERT INTO projects VALUES (1, ?, ?, ?, ?)",
                                       (principal.project_id, str(self.workspace), mission["mission_revision"], encode(plan)))
                    outcome = {"plan": json.loads(encode(plan))}
                elif not project or project[0] != principal.project_id:
                    raise StoreError("PROJECT_MISMATCH", "Initialize this project's mission first")
                elif operation == "EVENT_RECORDED":
                    pass
                elif operation == "PROPOSAL_REGISTERED":
                    proposal_body = body.get("proposal", body)
                    decision = propose(proposal_body, principal)
                    if "review_id" in body:
                        self.snapshots.check_binding(body["review_id"], proposal_body, principal)
                    outcome = {"decision": json.loads(encode(decision))}
                elif operation == "DECISION_ADVANCED":
                    if command.action in (Action.PUBLISH, Action.APPROVE, Action.REPUBLISH, Action.ACCEPT, Action.BEGIN_ACTIVATION, Action.ACTIVATE):
                        from dataclasses import replace
                        freshness = self.snapshots.validate(self.proposal(body["proposal_id"]))
                        if not freshness["eligible"]:
                            raise StoreError("STALE_CONTEXT", "; ".join(issue["message"] for issue in freshness["issues"]))
                        checks = replace(checks, dependencies_current=True, snapshot_stable=True)
                    transition = advance(self.decision(body["proposal_id"]), self.plan(), command, principal, self.clock, checks)
                    outcome = {"decision": json.loads(encode(transition.decision)), "plan": json.loads(encode(transition.plan)),
                               "transition": transition.event, "checks": values(checks)}
                elif _prepare is not None:
                    outcome = _prepare()
                else:
                    raise StoreError("INVALID_OPERATION", "Unknown persistence operation")
                instant = self.clock.now()
                if not isinstance(instant, datetime) or instant.tzinfo is None or instant.utcoffset() is None:
                    raise StoreError("INVALID_CLOCK", "Clock must return an aware datetime")
                recorded = instant.astimezone(timezone.utc).isoformat()
                cursor = connection.execute(
                    "INSERT INTO events(project_id,producer_key,event_id,actor_id,actor_role,run_id,operation,request_json,request_sha256,outcome_json,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (principal.project_id, producer, event_id, principal.actor_id, principal.role,
                     principal.run_id, operation, request, digest, canonical(outcome), recorded))
                seq = cursor.lastrowid
                self._fault("after_event")
                if operation == "MISSION_INITIALIZED":
                    connection.execute("INSERT INTO mission_revisions VALUES (?, ?, ?, ?)",
                                       (principal.project_id, mission["mission_revision"], seq, canonical(mission)))
                elif operation == "EVENT_RECORDED":
                    connection.execute(
                        "INSERT INTO producer_views VALUES(?,?,?,?) ON CONFLICT(project_id,producer_key) DO UPDATE SET event_seq=excluded.event_seq,body_json=excluded.body_json",
                        (principal.project_id, producer, seq, canonical(body)))
                elif operation == "PROPOSAL_REGISTERED":
                    connection.execute("INSERT INTO decisions VALUES (?, ?, ?, ?, ?, ?)",
                                       (principal.project_id, decision.proposal_id, decision.decision_id, decision.revision,
                                        encode(decision), canonical(proposal_body)))
                    if "review_id" in body:
                        connection.execute("INSERT INTO proposal_reviews VALUES(?,?,?)",
                                           (principal.project_id, decision.proposal_id, body["review_id"]))
                        connection.execute("UPDATE review_sessions SET sealed=1 WHERE review_id=?", (body["review_id"],))
                elif transition is not None:
                    decision, plan = transition.decision, transition.plan
                    connection.execute("UPDATE decisions SET decision_id=?, revision=?, state_json=? WHERE project_id=? AND proposal_id=?",
                                       (decision.decision_id, decision.revision, encode(decision), principal.project_id, decision.proposal_id))
                    connection.execute("UPDATE projects SET plan_json=? WHERE project_id=?", (encode(plan), principal.project_id))
                    if command.action == Action.ACTIVATE:
                        connection.execute("INSERT INTO activations VALUES (?, ?, ?, ?)",
                                           (principal.project_id, plan.epoch, decision.proposal_id, seq))
                elif _persist is not None:
                    _persist(seq, outcome)
                self._fault("after_view")
                message = {"storage_version": VERSION, "project_id": principal.project_id,
                           "event_seq": seq, "event_id": event_id, "producer_key": producer}
                connection.execute("INSERT INTO outbox VALUES (?, ?, ?, ?, ?)",
                                   (f"O-{seq}", seq, operation, canonical(message), recorded))
                self._fault("after_outbox")
                receipt = Receipt(seq, event_id, False)
            self._fault("before_commit")
            connection.execute("COMMIT")
        except BaseException as error:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            if isinstance(error, sqlite3.IntegrityError):
                raise StoreError("CONSTRAINT_CONFLICT", "Database identity or integrity constraint refused the command") from error
            raise
        self._fault("after_commit")
        return receipt
