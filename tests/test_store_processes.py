"""Real process failures; this does not simulate a power loss."""

import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

from principalloop.store import Reader, Store, StoreError


CHILD = r'''
import json, os, sys
from pathlib import Path
from principalloop.store import Store
from principalloop.domain.types import Principal, Role
database, workspace, event_file, phase, ready = sys.argv[1:]
event = json.loads(Path(event_file).read_text(encoding="utf-8"))
def fault(at):
    if at == phase:
        os._exit(73)
with Store(Path(database), workspace=Path(workspace), _fault=fault) as store:
    receipt = store.record_event(event, Principal("worker", Role.EXECUTOR, event["project_id"], "RUN-1"))
    print(json.dumps({"event_seq": receipt.event_seq}), flush=True)
    if phase == "hold":
        Path(ready).write_text("ready", encoding="utf-8")
        sys.stdin.readline()
'''


def args(case, phase):
    event_file = case["workspace"] / "event.json"
    event_file.write_text(json.dumps(case["event"]), encoding="utf-8")
    return [sys.executable, "-u", "-c", CHILD, str(case["database"]), str(case["workspace"]),
            str(event_file), phase, str(case["workspace"] / "ready")]


@pytest.mark.parametrize("phase,retained", [
    ("after_event", False), ("after_view", False), ("after_outbox", False),
    ("before_commit", False), ("after_commit", True),
])
def test_process_crash_commit_boundary_and_retry(storage_case, phase, retained):
    c = storage_case
    with Store(c["database"], workspace=c["workspace"]) as store:
        store.initialize(c["mission"], c["human"])
    child = subprocess.run(args(c, phase), capture_output=True, text=True, timeout=15)
    assert child.returncode == 73, child.stderr
    assert not child.stdout  # Process died before handing the receipt to its caller.
    with Store(c["database"], workspace=c["workspace"]) as store:
        status = store.status()
        assert status["event_count"] == status["outbox_count"] == 1 + int(retained)
        assert len(status["observations"]) == int(retained)
        receipt = store.record_event(c["event"], c["worker"])
        assert receipt.duplicate is retained
        assert store.status()["event_count"] == 2


def test_second_writer_refused_readers_work_and_killed_owner_releases_lock(storage_case):
    c = storage_case
    with Store(c["database"], workspace=c["workspace"]) as store:
        store.initialize(c["mission"], c["human"])
    child = subprocess.Popen(args(c, "hold"), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 10
        marker = c["workspace"] / "ready"
        while not marker.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.025)
        assert marker.exists(), "Child did not acquire ownership in time"
        with pytest.raises(StoreError, match="WRITER_BUSY"):
            Store(c["database"], workspace=c["workspace"])
        with Reader(c["database"], workspace=c["workspace"]) as reader:
            assert reader.status()["event_count"] == 2
        child.kill()
        child.wait(timeout=10)
    finally:
        if child.poll() is None:
            child.kill()
        output, errors = child.communicate(timeout=10)
    assert json.loads(output)["event_seq"] == 2, errors
    with Store(c["database"], workspace=c["workspace"]) as store:
        assert store.record_event(c["event"], c["worker"]).duplicate


def test_migration_process_crash_rolls_back_and_owner_can_reopen(storage_case):
    c = storage_case
    child = subprocess.run(args(c, "migration_before_commit"), capture_output=True, text=True, timeout=15)
    assert child.returncode == 73, child.stderr
    with Store(c["database"], workspace=c["workspace"]) as store:
        assert store.status()["event_count"] == 0
        store.initialize(c["mission"], c["human"])
