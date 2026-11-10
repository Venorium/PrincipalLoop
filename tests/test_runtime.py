import json
import sqlite3
import sys

import pytest

from principalloop.cli import main
from principalloop.runtime import diagnose, runtime_admitted, sqlite_has_wal_reset_fix
from principalloop.store import Store, StoreError


@pytest.mark.parametrize("release,qualified", [
    ((3, 44, 5), False), ((3, 44, 6), True), ((3, 45, 9), False),
    ((3, 49, 9), False), ((3, 50, 4), False), ((3, 50, 7), True),
    ((3, 51, 2), False), ((3, 51, 3), True), ((3, 53, 1), True),
])
def test_sqlite_fix_is_branch_specific(release, qualified):
    assert sqlite_has_wal_reset_fix(release) is qualified


def test_actual_runtime_and_database_are_qualified():
    report = diagnose()
    assert report["qualified"] and report["admitted"] and report["reference_runtime"], report
    assert sys.version_info[:3] == (3, 13, 16)
    assert report["sqlite"] == sqlite3.sqlite_version
    assert all(report["checks"].values())


def test_doctor_refuses_old_sqlite_without_opening_database(monkeypatch, capsys):
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 50, 4))
    monkeypatch.setattr(sqlite3, "connect", lambda *a, **kw: pytest.fail("Unqualified runtime opened database"))
    assert main(["doctor"]) == 2
    report = json.loads(capsys.readouterr().out)
    assert not report["qualified"] and not report["admitted"]


@pytest.mark.parametrize("version,sqlite_release,admitted", [
    ((3, 13, 16), (3, 53, 1), True), ((3, 13, 99), (3, 53, 1), True),
    ((3, 14, 2), (3, 53, 1), False), ((3, 12, 9), (3, 53, 1), False), ((3, 13, 16), (3, 50, 4), False),
])
def test_admission_requires_series_and_patched_sqlite_not_exact_patch(version, sqlite_release, admitted):
    assert runtime_admitted(version, sqlite_release) is admitted


def test_later_patch_release_runs_but_is_reported_unqualified(monkeypatch, capsys, storage_case):
    monkeypatch.setattr(sys, "version_info", (3, 13, 99, "final", 0))
    assert main(["doctor"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["admitted"] and not report["reference_runtime"] and not report["qualified"]
    with Store(storage_case["database"], workspace=storage_case["workspace"]) as store:
        assert store.status()["project_id"] is None


def test_store_refuses_unpatched_sqlite_before_opening(monkeypatch, storage_case):
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 50, 4))
    with pytest.raises(StoreError, match="RUNTIME_UNQUALIFIED"):
        Store(storage_case["database"], workspace=storage_case["workspace"])
    assert not storage_case["database"].exists()


def test_doctor_reports_sqlite_failure(monkeypatch):
    def failed_connection(*args, **kwargs):
        raise sqlite3.OperationalError("injected disk failure")
    monkeypatch.setattr(sqlite3, "connect", failed_connection)
    report = diagnose()
    assert not report["qualified"]
    assert "injected disk failure" in report["probe_error"]
