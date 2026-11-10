import json

from principalloop.cli import main


def test_demo_store_is_runnable_without_files_or_model(capsys):
    assert main(["demo-store"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["passed"] and all(output["checks"].values())
    assert output["director"] == "NOT_CONNECTED"


def test_cli_complete_local_journey(storage_case, capsys):
    c = storage_case
    mission = c["workspace"] / "mission.json"
    event = c["workspace"] / "event.json"
    mission.write_text(json.dumps(c["mission"]), encoding="utf-8")
    event.write_text(json.dumps(c["event"]), encoding="utf-8")
    common = ["--workspace", str(c["workspace"]), "--state-dir", str(c["database"].parent)]
    def run(action, *extra):
        code = main(["store", action, *common, *extra])
        return code, json.loads(capsys.readouterr().out)
    assert run("init", "--mission", str(mission))[0] == 0
    for duplicate in (False, True):
        code, receipt = run("observe", "--event", str(event), "--run-id", "RUN-1")
        assert code == 0 and receipt["duplicate"] is duplicate
    code, status = run("status")
    assert code == 0 and status["event_count"] == 2 and status["mode"] == "SHADOW"
    code, journal = run("journal", "--after", "1")
    assert code == 0 and len(journal) == 1 and journal[0]["event_seq"] == 2
    assert len(run("outbox")[1]) == 2
    assert run("journal", "--limit", "0")[0] == 1
    event.write_text(json.dumps({**c["event"], "role": "KERNEL"}), encoding="utf-8")
    assert run("observe", "--event", str(event), "--run-id", "RUN-1")[0] == 1
    backup = c["database"].parent / "saved.sqlite3"
    assert run("backup", "--output", str(backup))[0] == 0
    assert run("backup", "--output", str(backup))[0] == 1
    assert not (c["workspace"] / "control.sqlite3").exists()
