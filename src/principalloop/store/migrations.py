"""Storage format 1, independent from the v0.1 JSON contracts.

Never edit a shipped migration: add a version. Transactional DDL,
without executescript (which may change transaction boundaries).
"""

import hashlib
import sqlite3

from .errors import StoreError

APPLICATION_ID = 0x504C4F50
VERSION = 1
DDL = (
    """CREATE TABLE schema_migrations (
        version INTEGER PRIMARY KEY, checksum TEXT NOT NULL) STRICT""",
    """CREATE TABLE projects (
        singleton INTEGER NOT NULL UNIQUE CHECK(singleton = 1),
        project_id TEXT PRIMARY KEY, workspace TEXT NOT NULL,
        mission_revision INTEGER NOT NULL CHECK(mission_revision >= 1),
        plan_json TEXT NOT NULL CHECK(json_valid(plan_json))) STRICT""",
    """CREATE TABLE events (
        event_seq INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT NOT NULL REFERENCES projects(project_id),
        producer_key TEXT NOT NULL, event_id TEXT NOT NULL,
        actor_id TEXT NOT NULL, actor_role TEXT NOT NULL, run_id TEXT,
        operation TEXT NOT NULL CHECK(operation IN ('MISSION_INITIALIZED', 'EVENT_RECORDED', 'PROPOSAL_REGISTERED', 'DECISION_ADVANCED')),
        request_json TEXT NOT NULL CHECK(json_valid(request_json)),
        request_sha256 TEXT NOT NULL CHECK(length(request_sha256) = 64),
        outcome_json TEXT NOT NULL CHECK(json_valid(outcome_json)), recorded_at TEXT NOT NULL,
        UNIQUE(project_id, producer_key, event_id)) STRICT""",
    """CREATE TABLE mission_revisions (
        project_id TEXT NOT NULL REFERENCES projects(project_id),
        revision INTEGER NOT NULL CHECK(revision >= 1),
        event_seq INTEGER NOT NULL UNIQUE REFERENCES events(event_seq),
        body_json TEXT NOT NULL CHECK(json_valid(body_json)),
        PRIMARY KEY(project_id, revision)) STRICT""",
    """CREATE TABLE producer_views (
        project_id TEXT NOT NULL REFERENCES projects(project_id),
        producer_key TEXT NOT NULL, event_seq INTEGER NOT NULL UNIQUE REFERENCES events(event_seq),
        body_json TEXT NOT NULL CHECK(json_valid(body_json)),
        PRIMARY KEY(project_id, producer_key)) STRICT""",
    """CREATE TABLE outbox (
        message_id TEXT PRIMARY KEY, event_seq INTEGER NOT NULL UNIQUE REFERENCES events(event_seq),
        topic TEXT NOT NULL, body_json TEXT NOT NULL CHECK(json_valid(body_json)),
        created_at TEXT NOT NULL) STRICT""",
    """CREATE TABLE decisions (
        project_id TEXT NOT NULL REFERENCES projects(project_id), proposal_id TEXT NOT NULL,
        decision_id TEXT, revision INTEGER NOT NULL CHECK(revision >= 1),
        state_json TEXT NOT NULL CHECK(json_valid(state_json)),
        proposal_json TEXT NOT NULL CHECK(json_valid(proposal_json)),
        PRIMARY KEY(project_id, proposal_id), UNIQUE(project_id, decision_id)) STRICT""",
    """CREATE TABLE activations (
        project_id TEXT NOT NULL REFERENCES projects(project_id),
        plan_epoch INTEGER NOT NULL CHECK(plan_epoch >= 1),
        proposal_id TEXT NOT NULL, event_seq INTEGER NOT NULL UNIQUE REFERENCES events(event_seq),
        PRIMARY KEY(project_id, plan_epoch), UNIQUE(project_id, proposal_id),
        FOREIGN KEY(project_id, proposal_id) REFERENCES decisions(project_id, proposal_id)) STRICT""",
    """CREATE TRIGGER proposal_no_change BEFORE UPDATE OF proposal_json ON decisions
        WHEN NEW.proposal_json != OLD.proposal_json
        BEGIN SELECT RAISE(ABORT, 'proposals are immutable'); END""",
    """CREATE TRIGGER events_no_update BEFORE UPDATE ON events
        BEGIN SELECT RAISE(ABORT, 'events are append-only'); END""",
    """CREATE TRIGGER events_no_delete BEFORE DELETE ON events
        BEGIN SELECT RAISE(ABORT, 'events are append-only'); END""",
    """CREATE TRIGGER mission_no_update BEFORE UPDATE ON mission_revisions
        BEGIN SELECT RAISE(ABORT, 'missions are immutable'); END""",
    """CREATE TRIGGER mission_no_delete BEFORE DELETE ON mission_revisions
        BEGIN SELECT RAISE(ABORT, 'missions are immutable'); END""",
)
CHECKSUM = hashlib.sha256("\n".join(DDL).encode("utf-8")).hexdigest()


def inspect(connection: sqlite3.Connection) -> int:
    application = connection.execute("PRAGMA application_id").fetchone()[0]
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    tables = connection.execute("SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
    if application == 0 and version == 0 and not tables:
        return 0
    if application != APPLICATION_ID or version != VERSION:
        raise StoreError("SCHEMA_UNSUPPORTED", "Foreign database or unsupported storage version")
    try:
        history = connection.execute("SELECT version, checksum FROM schema_migrations ORDER BY version").fetchall()
    except sqlite3.DatabaseError as error:
        raise StoreError("SCHEMA_INVALID", "Missing migration history") from error
    if [tuple(row) for row in history] != [(VERSION, CHECKSUM)]:
        raise StoreError("SCHEMA_INVALID", "Migration checksum does not match this software")
    return version


def migrate(connection: sqlite3.Connection, fault) -> None:
    if inspect(connection) == VERSION:
        return
    connection.execute("BEGIN IMMEDIATE")
    try:
        for statement in DDL:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_migrations VALUES (?, ?)", (VERSION, CHECKSUM))
        connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
        connection.execute(f"PRAGMA user_version={VERSION}")
        fault("migration_before_commit")
        connection.execute("COMMIT")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
