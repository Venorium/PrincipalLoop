"""Real migration, human journey and hostile HTML projection."""

import base64
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from principalloop.cli import main
from principalloop.domain.types import Principal, Role
from principalloop.snapshot.demo import run_demo
from principalloop.snapshot.report import JS, render, write_report
from principalloop.store import Reader, Store, StoreError
from principalloop.store import migrations, sqlite as storage
from principalloop.store.schema import inspect


def seed_v1(c, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(storage, "migrate", migrations.migrate)
        with Store(c["database"], workspace=c["workspace"], clock=c["clock"]) as store:
            store.initialize(c["mission"], c["human"])
            store.record_event(c["event"], c["worker"])
            return store.journal(), store.outbox(), store.plan()


def test_v1_upgrade_preserves_receipts_and_has_restorable_backup(storage_case, monkeypatch):
    c = storage_case
    journal, outbox, plan = seed_v1(c, monkeypatch)
    with pytest.raises(StoreError, match="MIGRATION_REQUIRED"):
        Reader(c["database"], workspace=c["workspace"])
    with Store(c["database"], workspace=c["workspace"]) as store:
        assert (store.journal(), store.outbox(), store.plan()) == (journal, outbox, plan)
        assert store.record_event(c["event"], c["worker"]).duplicate
        assert store.initialize(c["mission"], c["human"]).duplicate
        assert store._connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert store._connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    backups = list(c["database"].parent.glob("before-storage-v2-*.sqlite3"))
    assert len(backups) == 1
    with closing(sqlite3.connect(backups[0], autocommit=True)) as sql:
        assert migrations.inspect(sql) == 1
        assert sql.execute("SELECT count(*) FROM events").fetchone()[0] == 2


@pytest.mark.parametrize("process_death", [False, True])
def test_v2_failed_migration_retains_v1_then_reopens(storage_case, monkeypatch, process_death):
    c = storage_case
    journal, _, _ = seed_v1(c, monkeypatch)
    if process_death:
        script = """import os,sys
from pathlib import Path
from principalloop.store import Store
with Store(Path(sys.argv[1]), workspace=Path(sys.argv[2]), _fault=lambda at: os._exit(73) if at=='migration_v2_before_commit' else None):
    pass
"""
        result = subprocess.run([sys.executable, "-c", script, str(c["database"]), str(c["workspace"])], capture_output=True, timeout=15)
        assert result.returncode == 73, result.stderr
    else:
        def fault(at):
            if at == "migration_v2_before_commit":
                raise OSError("injected migration failure")
        with pytest.raises(OSError, match="injected"):
            Store(c["database"], workspace=c["workspace"], _fault=fault)
    sql, version = storage.open_writer(c["database"])
    with closing(sql):
        assert version == 1
        assert sql.execute("SELECT count(*) FROM events").fetchone()[0] == 2
        assert not sql.execute("SELECT 1 FROM sqlite_master WHERE name='snapshots'").fetchall()
    with Store(c["database"], workspace=c["workspace"]) as store:
        assert inspect(store._connection) == 2 and store.journal() == journal


@pytest.mark.skipif(os.name != "nt", reason="Windows-specific recovery")
@pytest.mark.parametrize("errorname,failures,attempts,success", [
    ("SQLITE_IOERR_TRUNCATE", 2, 3, True), ("SQLITE_IOERR_TRUNCATE", 3, 3, False),
    ("SQLITE_CORRUPT", 1, 1, False), ("SQLITE_IOERR_WRITE", 1, 1, False),
])
def test_recovery_retry_is_bounded_and_only_before_commands(monkeypatch, errorname, failures, attempts, success):
    connections, waits = [], []
    class Connection:
        closed = False
        def close(self):
            self.closed = True
    def connect(*args, **kwargs):
        connection = Connection()
        connections.append(connection)
        return connection
    def check(connection):
        if len(connections) <= failures:
            error = sqlite3.OperationalError("injected")
            error.sqlite_errorname = errorname
            raise error
        return 2
    monkeypatch.setattr(storage.sqlite3, "connect", connect)
    monkeypatch.setattr(storage, "inspect", check)
    monkeypatch.setattr(storage.time, "sleep", waits.append)
    if success:
        assert storage.open_writer(Path("unused"))[1] == 2
    else:
        with pytest.raises(sqlite3.OperationalError):
            storage.open_writer(Path("unused"))
    assert len(connections) == attempts and len(waits) == attempts - 1
    assert all(c.closed for c in (connections[:-1] if success else connections))


def test_demo_executes_expected_cases_and_report_treats_payload_as_text(tmp_path):
    data = run_demo()
    assert len(data["scenarios"]) == 8 and data["all_expected_results_observed"]
    results = {case["id"]: case["validation"]["eligible"] for case in data["scenarios"]}
    assert results == dict(initial=True, noise=True, premise=False, file=False, unstable=False, served=False, mandatory=False, omitted=True)
    assert data["scenarios"][2]["changes"][0]["before"] != data["scenarios"][2]["changes"][0]["after"]
    attack = '</script><img src="https://example.invalid/" onerror="alert(1)">'
    data["scenarios"][0]["explanation"] = attack
    page = render(data)
    assert attack not in page and "\\u003c/script\\u003e" in page
    assert "sha256-" + base64.b64encode(hashlib.sha256(JS.encode()).digest()).decode() in page
    assert "connect-src 'none'" in page and 'src="http' not in page
    path = write_report(data, tmp_path / "report.html")
    with pytest.raises(FileExistsError):
        write_report(data, path)


def test_report_language_changes_text_only_and_covers_every_kernel_issue(monkeypatch):
    import re
    from principalloop.snapshot.i18n import UI, default_lang
    french, english = run_demo("fr"), run_demo("en")
    verdicts = lambda data: [(c["id"], c["validation"]["eligible"], [i["code"] for i in c["validation"]["issues"]]) for c in data["scenarios"]]
    assert verdicts(french) == verdicts(english)
    page = render(english)
    assert '<html lang="en">' in page and "Same proposal. Different contexts." in page and "Explorez" not in page
    assert '<html lang="fr">' in render(french)
    assert set(UI["fr"]) == set(UI["en"]) and set(UI["fr"]["states"]) == set(UI["en"]["states"])
    engine = (Path(__file__).resolve().parents[1] / "src/principalloop/snapshot/engine.py").read_text(encoding="utf-8")
    emitted = set(re.findall(r'issue\("([A-Z_]+)"', engine)) | set(re.findall(r'"code": "([A-Z_]+)"', engine))
    assert emitted <= set(UI["en"]["issues"])
    assert default_lang() == "en"
    monkeypatch.setenv("PRINCIPALLOOP_LANG", "fr")
    assert default_lang() == "fr"
    assert set(UI["fr"]["issues"]) == set(UI["en"]["issues"])


def test_human_cli_captures_inspects_and_keeps_real_reports_private(storage_case, capsys):
    c = storage_case
    with Store(c["database"], workspace=c["workspace"]) as store:
        store.initialize(c["mission"], c["human"])
    common = ["--workspace", str(c["workspace"]), "--state-dir", str(c["database"].parent)]
    assert main(["context", "put", *common, "--id", "H-1", "--title", "Premise", "--text", "Content"]) == 0
    assert "Premise saved" in capsys.readouterr().out
    (c["workspace"] / "input.txt").write_text("content", encoding="utf-8")
    output = c["database"].parent / "report.html"
    assert main(["snapshot", "capture", *common, "--file", "input.txt", "--object", "H-1", "--no-open", "--output", str(output)]) == 0
    assert "Visual report" in capsys.readouterr().out and output.exists()
    assert main(["snapshot", "list", *common, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["stability"] == "STABLE"
    assert main(["snapshot", "inspect", *common, "--no-open", "--output", str(c["database"].parent / "inspect.html")]) == 0
    capsys.readouterr()
    assert main(["snapshot", "inspect", *common, "--no-open", "--output", str(c["workspace"] / "leak.html")]) == 1
    assert not (c["workspace"] / "leak.html").exists()


def test_read_only_capture_refuses_before_reading_or_evaluating(storage_case):
    c = storage_case
    with Store(c["database"], workspace=c["workspace"]) as store:
        store.initialize(c["mission"], c["human"])
    with Reader(c["database"], workspace=c["workspace"]) as reader:
        with pytest.raises(StoreError, match="READ_ONLY"):
            reader.snapshots.capture({"F": "missing"}, [], c["human"], event_id="C")
        verifier = Principal("verifier", Role.VERIFIER, c["mission"]["project_id"])
        with pytest.raises(StoreError, match="READ_ONLY"):
            reader.snapshots.record_evidence("E", "missing", "F", "check", verifier, lambda _: pytest.fail("Must not run"), event_id="E")


def test_failed_export_reports_committed_capture_for_recovery(storage_case, monkeypatch, capsys):
    from principalloop.snapshot import cli
    c = storage_case
    with Store(c["database"], workspace=c["workspace"]) as store:
        store.initialize(c["mission"], c["human"])
    def unavailable(*args):
        raise OSError("Injected disk failure")
    monkeypatch.setattr(cli, "write_report", unavailable)
    assert main(["snapshot", "capture", "--workspace", str(c["workspace"]), "--state-dir", str(c["database"].parent),
                 "--no-open", "--json", "--event-id", "CAPTURE-RETRY"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["committed_capture"]["event_id"] == "CAPTURE-RETRY"
    with Reader(c["database"], workspace=c["workspace"]) as reader:
        assert reader.snapshots.get(result["committed_capture"]["snapshot_id"])
