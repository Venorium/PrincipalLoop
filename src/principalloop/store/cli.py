"""Explicit local facade. No watch service and no remote authentication."""

from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import tempfile

from ..domain.contracts import ContractError, validate_contract
from ..domain.types import Principal, Role
from .errors import StoreError
from .paths import default_state_dir
from .sqlite import Reader, Store


def add_commands(commands):
    commands.add_parser("demo-store", help="Throwaway demonstration: commit, duplicate, conflict and reopen")
    parser = commands.add_parser("store", help="Local journal (no director connected)")
    actions = parser.add_subparsers(dest="store_action", required=True)
    for name in ("init", "observe", "status", "journal", "outbox", "backup"):
        action = actions.add_parser(name)
        action.add_argument("--workspace", type=Path, default=Path.cwd())
        action.add_argument("--state-dir", type=Path, help="Private directory outside the workspace; default: local user state")
        if name == "init":
            action.add_argument("--mission", type=Path, required=True)
            action.add_argument("--event-id", default="MISSION-1")
        if name == "observe":
            action.add_argument("--event", type=Path, required=True)
            action.add_argument("--run-id", required=True, help="Stable identity for retries by the same executor")
        if name in ("journal", "outbox"):
            action.add_argument("--after", type=int, default=0)
            action.add_argument("--limit", type=int, default=100)
        if name == "backup":
            action.add_argument("--output", type=Path, required=True, help="Nouveau fichier hors workspace")


def demo() -> dict:
    mission = {"schema_version": "0.1", "project_id": "demo", "mission_revision": 1, "goal_id": "G-1",
               "objective": "Exercise local storage.", "acceptance_criteria": ["Event kept after reopening."],
               "scope": ["service"], "hard_constraints": ["No model."], "allowed_actions": ["SIMULATE"],
               "observable_sources": ["events"], "budget": {"max_tokens": 0, "max_wall_seconds": 60, "max_tool_calls": 0},
               "escalation_conditions": []}
    event = {"schema_version": "0.1", "project_id": "demo", "event_id": "E-1", "event_type": "OBSERVATION",
             "observed_at": "2026-10-04T12:00:00Z", "causal_ids": [],
             "payload": {"summary": "Synthetic observation, not a snapshot.", "reference_ids": []}}
    worker = Principal("demo-worker", Role.EXECUTOR, "demo", "run-1")
    with tempfile.TemporaryDirectory(prefix="principalloop-demo-") as folder:
        root = Path(folder).resolve()
        assert root.is_relative_to(Path(tempfile.gettempdir()).resolve())
        workspace = root / "workspace"
        workspace.mkdir()
        database = root / "state/control.sqlite3"
        with Store(database, workspace=workspace) as store:
            store.initialize(mission, Principal("demo-human", Role.HUMAN, "demo"))
            first = store.record_event(event, worker)
            duplicate = store.record_event(event, worker)
            altered = {**event, "payload": {"summary": "Contradictory content.", "reference_ids": []}}
            conflict = None
            try:
                store.record_event(altered, worker)
            except StoreError as error:
                if error.code != "ID_CONFLICT":
                    raise
                conflict = error.code
        with Store(database, workspace=workspace) as store:
            status = store.status()
            checks = {"committed": not first.duplicate, "deduplicated": duplicate.duplicate and first.event_seq == duplicate.event_seq,
                      "conflict_refused": conflict == "ID_CONFLICT", "reopened": status["event_count"] == 2,
                      "outbox_retained": status["outbox_count"] == 2,
                      "observation_retained": status["observations"][0]["event"] == event}
        return {"passed": all(checks.values()), "checks": checks, "receipt": asdict(first),
                "mode": "SHADOW", "director": "NOT_CONNECTED", "temporary_state_removed_on_exit": True}


def execute(args) -> int:
    try:
        if args.command == "demo-store":
            result = demo()
            code = 0 if result["passed"] else 1
        else:
            workspace = args.workspace.resolve(strict=True)
            database = (args.state_dir or default_state_dir(workspace)) / "control.sqlite3"
            action = args.store_action
            # Validate files before creating or locking a database.
            if action == "init":
                payload = validate_contract("mission", args.mission.read_bytes())
            elif action == "observe":
                payload = validate_contract("event", args.event.read_bytes())
            access = Store if action in ("init", "observe") else Reader
            with access(database, workspace=workspace) as store:
                if action == "init":
                    result = asdict(store.initialize(payload, Principal("local-human", Role.HUMAN, payload["project_id"]), event_id=args.event_id))
                elif action == "observe":
                    result = asdict(store.record_event(payload, Principal("local-cli", Role.EXECUTOR, payload["project_id"], args.run_id)))
                elif action == "status":
                    result = store.status()
                elif action in ("journal", "outbox"):
                    result = getattr(store, action)(after=args.after, limit=args.limit)
                else:
                    result = {"backup": str(store.backup(args.output))}
            code = 0
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return code
    except (StoreError, ContractError, OSError, sqlite3.Error, ValueError) as error:
        print(json.dumps({"error": getattr(error, "code", type(error).__name__), "detail": str(error)}, ensure_ascii=True))
        return 1
