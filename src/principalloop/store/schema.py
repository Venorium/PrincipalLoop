"""Migration 2. La migration PL-03 et son empreinte restent immuables."""

import hashlib
import sqlite3

from . import migrations as v1
from .errors import StoreError

LATEST_VERSION = 2
OPERATIONS = ("OBJECT_UPDATED", "DEPENDENCIES_SET", "SNAPSHOT_CAPTURED", "REVIEW_STARTED", "CONTEXT_READ", "EVIDENCE_RECORDED")
EVENTS_V2 = v1.DDL[2].replace("CREATE TABLE events", "CREATE TABLE events_v2").replace(
    "'DECISION_ADVANCED'))", "'DECISION_ADVANCED'," + ",".join(repr(op) for op in OPERATIONS) + "))")
DDL = (
    EVENTS_V2,
    "INSERT INTO events_v2 SELECT * FROM events",
    "DROP TABLE events",
    "ALTER TABLE events_v2 RENAME TO events",
    *tuple(sql for sql in v1.DDL if sql.startswith("CREATE TRIGGER events_")),
    """CREATE TABLE object_revisions (
        object_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0),
        body_json TEXT NOT NULL CHECK(json_valid(body_json)), sha256 TEXT NOT NULL,
        actor_id TEXT NOT NULL, actor_role TEXT NOT NULL,
        event_seq INTEGER NOT NULL REFERENCES events(event_seq), PRIMARY KEY(object_id,revision)) STRICT""",
    """CREATE TABLE object_heads (
        object_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, title TEXT NOT NULL,
        FOREIGN KEY(object_id,revision) REFERENCES object_revisions(object_id,revision)) STRICT""",
    """CREATE TABLE review_flags (
        object_id TEXT NOT NULL REFERENCES object_heads(object_id),
        dependency_id TEXT NOT NULL REFERENCES object_heads(object_id),
        event_seq INTEGER NOT NULL REFERENCES events(event_seq), PRIMARY KEY(object_id,dependency_id)) STRICT""",
    """CREATE TABLE dependency_policy (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1), revision INTEGER NOT NULL,
        object_ids_json TEXT NOT NULL CHECK(json_valid(object_ids_json))) STRICT""",
    "INSERT INTO dependency_policy VALUES(1,1,'[]')",
    """CREATE TABLE artifact_blobs (
        sha256 TEXT PRIMARY KEY, content BLOB NOT NULL, size INTEGER NOT NULL CHECK(size=length(content))) STRICT""",
    """CREATE TABLE snapshots (
        snapshot_id TEXT PRIMARY KEY, manifest_json TEXT NOT NULL CHECK(json_valid(manifest_json)),
        details_json TEXT NOT NULL CHECK(json_valid(details_json)),
        event_seq INTEGER NOT NULL UNIQUE REFERENCES events(event_seq)) STRICT""",
    """CREATE TABLE artifact_heads (
        artifact_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, sha256 TEXT NOT NULL REFERENCES artifact_blobs(sha256),
        relative_path TEXT NOT NULL) STRICT""",
    """CREATE TABLE snapshot_artifacts (
        snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id), artifact_id TEXT NOT NULL,
        sha256 TEXT NOT NULL REFERENCES artifact_blobs(sha256), relative_path TEXT NOT NULL, revision INTEGER NOT NULL,
        PRIMARY KEY(snapshot_id,artifact_id)) STRICT""",
    """CREATE TABLE review_sessions (
        review_id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
        actor_id TEXT NOT NULL, run_id TEXT NOT NULL, sealed INTEGER NOT NULL DEFAULT 0 CHECK(sealed IN (0,1))) STRICT""",
    """CREATE TABLE served_reads (
        review_id TEXT NOT NULL REFERENCES review_sessions(review_id),
        reference_id TEXT NOT NULL, reference_kind TEXT NOT NULL CHECK(reference_kind IN ('OBJECT','ARTIFACT')),
        event_seq INTEGER NOT NULL REFERENCES events(event_seq), PRIMARY KEY(review_id,reference_id,reference_kind)) STRICT""",
    """CREATE TABLE proposal_reviews (
        project_id TEXT NOT NULL, proposal_id TEXT NOT NULL,
        review_id TEXT NOT NULL UNIQUE REFERENCES review_sessions(review_id),
        PRIMARY KEY(project_id,proposal_id), FOREIGN KEY(project_id,proposal_id) REFERENCES decisions(project_id,proposal_id)) STRICT""",
    """CREATE TABLE evidence_records (
        evidence_id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
        artifact_id TEXT NOT NULL, sha256 TEXT NOT NULL REFERENCES artifact_blobs(sha256),
        check_id TEXT NOT NULL, verdict TEXT NOT NULL CHECK(verdict IN ('PASS','FAIL','INCONCLUSIVE')),
        actor_id TEXT NOT NULL, event_seq INTEGER NOT NULL UNIQUE REFERENCES events(event_seq),
        FOREIGN KEY(snapshot_id,artifact_id) REFERENCES snapshot_artifacts(snapshot_id,artifact_id)) STRICT""",
    *tuple(f"CREATE TRIGGER {table}_no_{operation.lower()} BEFORE {operation} ON {table} "
           "BEGIN SELECT RAISE(ABORT, 'immutable snapshot history'); END"
           for table in ("object_revisions", "snapshots", "snapshot_artifacts", "artifact_blobs", "evidence_records", "served_reads")
           for operation in ("UPDATE", "DELETE")),
)
CHECKSUM = hashlib.sha256("\n".join(DDL).encode("utf-8")).hexdigest()


def inspect(connection):
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version in (0, 1):
        return v1.inspect(connection)
    if version != LATEST_VERSION or connection.execute("PRAGMA application_id").fetchone()[0] != v1.APPLICATION_ID:
        raise StoreError("SCHEMA_UNSUPPORTED", "Foreign database or unsupported storage version")
    try:
        rows = [tuple(row) for row in connection.execute("SELECT version,checksum FROM schema_migrations ORDER BY version")]
    except sqlite3.Error as error:
        raise StoreError("SCHEMA_INVALID", "Missing migration history") from error
    if rows != [(1, v1.CHECKSUM), (2, CHECKSUM)]:
        raise StoreError("SCHEMA_INVALID", "Migration checksum mismatch")
    return version


def migrate(connection, fault):
    version = inspect(connection)
    if version == 0:
        v1.migrate(connection, fault)
        version = 1
    if version == LATEST_VERSION:
        return
    # SQLite's documented table-rebuild sequence; never rename the old table first.
    connection.execute("PRAGMA foreign_keys=OFF")
    connection.execute("BEGIN IMMEDIATE")
    try:
        for statement in DDL:
            connection.execute(statement)
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise StoreError("MIGRATION_INVALID", "Foreign keys failed after migration")
        connection.execute("INSERT INTO schema_migrations VALUES(2,?)", (CHECKSUM,))
        connection.execute("PRAGMA user_version=2")
        fault("migration_v2_before_commit")
        connection.execute("COMMIT")
    except BaseException:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    finally:
        connection.execute("PRAGMA foreign_keys=ON")
