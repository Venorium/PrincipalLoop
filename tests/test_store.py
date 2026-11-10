from copy import deepcopy
from contextlib import closing
from dataclasses import replace
from datetime import timedelta
import json
import sqlite3

import pytest

from principalloop.domain.contracts import ContractError
from principalloop.domain.types import FixedClock, Mode, Principal, Role
from principalloop.store import Reader, Store, StoreError
from principalloop.store.migrations import APPLICATION_ID, CHECKSUM, VERSION
from principalloop.store.schema import LATEST_VERSION, CHECKSUM as V2_CHECKSUM
from principalloop.store.paths import default_state_dir


def open_store(case, **kwargs):
    return Store(case["database"], workspace=case["workspace"], clock=case["clock"], **kwargs)


def test_t01_deduplication_survives_reopen_and_json_key_order(storage_case):
    c = storage_case
    with open_store(c) as store:
        store.initialize(c["mission"], c["human"])
        first = store.record_event(c["event"], c["worker"])
    with open_store(c) as store:
        again = store.record_event(json.dumps(c["event"], sort_keys=True), c["worker"])
        assert again.duplicate and again.event_seq == first.event_seq
        assert store.status()["event_count"] == store.status()["outbox_count"] == 2
        assert store.status()["observations"][0]["event_seq"] == first.event_seq
        assert store.initialize(c["mission"], c["human"]).duplicate


def test_t02_conflicting_event_preserves_all_original_state(storage_case):
    c = storage_case
    with open_store(c) as store:
        store.initialize(c["mission"], c["human"])
        store.record_event(c["event"], c["worker"])
        before = (store.status(), store.journal(), store.outbox())
        altered = deepcopy(c["event"])
        altered["payload"]["summary"] = "Different claim"
        with pytest.raises(StoreError, match="ID_CONFLICT"):
            store.record_event(altered, c["worker"])
        assert (store.status(), store.journal(), store.outbox()) == before


def test_identity_namespaces_and_observations_never_change_the_plan(storage_case):
    c = storage_case
    with open_store(c) as store:
        store.initialize(c["mission"], c["human"])
        plan = store.plan()
        for actor in (c["worker"], replace(c["worker"], run_id="RUN-2"), replace(c["worker"], actor_id="other")):
            store.record_event(c["event"], actor)
        assert len(store.status()["observations"]) == 3
        assert store.plan() == plan
        assert store.mission() == c["mission"]


@pytest.mark.parametrize("phase", ["after_event", "after_view", "after_outbox", "before_commit"])
def test_event_view_outbox_rollback_together_without_receipt(storage_case, phase):
    c = storage_case
    def fail(at):
        if at == phase:
            raise OSError("Injected write failure")
    with open_store(c) as store:
        store.initialize(c["mission"], c["human"])
        before = store.status()
        store._fault = fail
        with pytest.raises(OSError, match="Injected"):
            store.record_event(c["event"], c["worker"])
        assert store.status() == before
        store._fault = lambda _: None
        assert not store.record_event(c["event"], c["worker"]).duplicate


def test_lost_receipt_after_commit_is_resolved_by_identical_retry(storage_case):
    c = storage_case
    with open_store(c) as store:
        store.initialize(c["mission"], c["human"])
        def fail(at):
            if at == "after_commit":
                raise OSError("Receipt lost")
        store._fault = fail
        with pytest.raises(OSError):
            store.record_event(c["event"], c["worker"])
    with open_store(c) as store:
        retry = store.record_event(c["event"], c["worker"])
        assert retry.duplicate and retry.event_seq == 2
        assert store.status()["outbox_count"] == 2


def test_receipt_boundary_is_observable_from_an_independent_reader(storage_case):
    c = storage_case
    observations = {}
    with open_store(c) as store:
        store.initialize(c["mission"], c["human"])
        with Reader(c["database"], workspace=c["workspace"]) as reader:
            def observe(phase):
                if phase in ("before_commit", "after_commit"):
                    observations[phase] = reader.status()["event_count"]
            store._fault = observe
            assert store.record_event(c["event"], c["worker"]).event_seq == 2
    assert observations == {"before_commit": 1, "after_commit": 2}


def test_sequence_not_timestamps_orders_events(storage_case):
    c = storage_case
    with open_store(c) as store:
        store.initialize(c["mission"], c["human"])
        first = store.record_event(c["event"], c["worker"])
        store.clock = FixedClock(c["clock"].now() - timedelta(days=1))
        older = {**c["event"], "event_id": "E-2", "observed_at": "2000-01-01T00:00:00Z"}
        second = store.record_event(older, c["worker"])
        assert second.event_seq > first.event_seq
        assert store.status()["observations"][0]["event"] == older
        assert [row["event_seq"] for row in store.journal(after=first.event_seq)] == [second.event_seq]


def test_sql_constraints_are_effective_and_journal_is_append_only(storage_case):
    c = storage_case
    with open_store(c) as store:
        store.initialize(c["mission"], c["human"])
        store.record_event(c["event"], c["worker"])
        with closing(sqlite3.connect(c["database"], autocommit=True)) as sql:
            sql.execute("PRAGMA foreign_keys=ON")
            columns = [row[1] for row in sql.execute("PRAGMA table_info(events)") if row[1] != "event_seq"]
            names = ",".join(columns)
            with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
                sql.execute(f"INSERT INTO events({names}) SELECT {names} FROM events WHERE event_seq=2")
            for query in ("UPDATE events SET event_id='changed'", "DELETE FROM events", "UPDATE mission_revisions SET revision=2"):
                with pytest.raises(sqlite3.IntegrityError):
                    sql.execute(query)
            with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
                sql.execute("INSERT INTO outbox VALUES('bad',999,'bad','{}','now')")
            with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
                sql.execute("INSERT INTO outbox SELECT 'different-id',event_seq,topic,body_json,created_at FROM outbox WHERE event_seq=2")
        assert store.status()["event_count"] == 2


def test_migration_is_atomic_and_repeatable(storage_case):
    c = storage_case
    def fail(phase):
        if phase == "migration_before_commit":
            raise RuntimeError("migration interrupted")
    with pytest.raises(RuntimeError):
        open_store(c, _fault=fail)
    with closing(sqlite3.connect(c["database"])) as sql:
        assert sql.execute("PRAGMA user_version").fetchone()[0] == 0
        assert sql.execute("PRAGMA application_id").fetchone()[0] == 0
        assert sql.execute("SELECT name FROM sqlite_master").fetchall() == []
    for _ in range(2):
        with open_store(c) as store:
            assert store.status()["event_count"] == 0
    with closing(sqlite3.connect(c["database"])) as sql:
        assert sql.execute("PRAGMA user_version").fetchone()[0] == LATEST_VERSION
        assert sql.execute("SELECT * FROM schema_migrations").fetchall() == [(VERSION, CHECKSUM), (2, V2_CHECKSUM)]


@pytest.mark.parametrize("case", ["foreign", "future", "checksum"])
def test_unknown_or_inconsistent_schema_is_refused_without_migration(storage_case, case):
    c = storage_case
    c["database"].parent.mkdir()
    if case != "foreign":
        with open_store(c):
            pass
    with closing(sqlite3.connect(c["database"], autocommit=True)) as sql:
        if case == "foreign":
            sql.execute("CREATE TABLE unrelated(secret TEXT)")
        elif case == "future":
            sql.execute("PRAGMA user_version=999")
        else:
            sql.execute("UPDATE schema_migrations SET checksum='changed'")
    before = c["database"].read_bytes()
    with pytest.raises(StoreError, match="SCHEMA_"):
        open_store(c)
    assert c["database"].read_bytes() == before


def test_private_paths_missing_readers_and_workspace_binding(storage_case, monkeypatch):
    c = storage_case
    with pytest.raises(StoreError, match="UNSAFE_PATH"):
        Store(c["workspace"] / "control.sqlite3", workspace=c["workspace"])
    with pytest.raises(sqlite3.OperationalError):
        Reader(c["database"], workspace=c["workspace"])
    assert not c["database"].exists()
    monkeypatch.setenv("OneDrive", str(c["database"].parent))
    with pytest.raises(StoreError, match="UNSAFE_PATH"):
        open_store(c)
    monkeypatch.delenv("OneDrive")
    assert not default_state_dir(c["workspace"]).is_relative_to(c["workspace"])
    with open_store(c) as store:
        store.initialize(c["mission"], c["human"])
    other = c["workspace"].parent / "other"
    other.mkdir()
    with pytest.raises(StoreError, match="WORKSPACE_MISMATCH"):
        Store(c["database"], workspace=other)


def test_backup_is_a_consistent_reopenable_copy_and_never_overwrites(storage_case):
    c = storage_case
    backup = c["database"].parent / "backup.sqlite3"
    with open_store(c) as store:
        store.initialize(c["mission"], c["human"])
        store.record_event(c["event"], c["worker"])
        with Reader(c["database"], workspace=c["workspace"]) as reader:
            reader.backup(backup)
            with pytest.raises(FileExistsError):
                reader.backup(backup)
        before = store.status()
    with Store(backup, workspace=c["workspace"]) as restored:
        assert restored.status() == before
        assert restored.record_event(c["event"], c["worker"]).duplicate


def test_roles_projects_payload_authority_and_missing_checks_fail_closed(storage_case):
    c = storage_case
    with open_store(c) as store:
        with pytest.raises(StoreError, match="FORBIDDEN"):
            store.initialize(c["mission"], c["worker"])
        with pytest.raises(StoreError, match="CAPABILITY_UNPROVEN"):
            store.initialize(c["mission"], c["human"], mode=Mode.ENFORCED)
        store.initialize(c["mission"], c["human"])
        with pytest.raises(StoreError, match="FORBIDDEN"):
            store.record_event(c["event"], c["director"])
        with pytest.raises(StoreError, match="PROJECT_MISMATCH"):
            store.record_event(c["event"], replace(c["worker"], project_id="other"))
        with pytest.raises(ContractError):
            store.record_event({**c["event"], "role": "HUMAN"}, c["worker"])
        changed = {**c["mission"], "objective": "Change mission"}
        with pytest.raises(StoreError, match="ALREADY_INITIALIZED"):
            store.initialize(changed, c["human"], event_id="MISSION-2")
        assert store.status()["event_count"] == 1
    with pytest.raises(StoreError, match="STORE_CLOSED"):
        store.status()
