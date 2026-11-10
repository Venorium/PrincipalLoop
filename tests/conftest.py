from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from principalloop.domain.types import FixedClock, Principal, Role


@pytest.fixture(autouse=True)
def stable_language(monkeypatch):
    # Reports default to English; an inherited PRINCIPALLOOP_LANG must not change test outcomes.
    monkeypatch.delenv("PRINCIPALLOOP_LANG", raising=False)


@pytest.fixture
def storage_case(tmp_path):
    root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    mission = json.loads((root / "examples/contracts/mission.json").read_text(encoding="utf-8"))
    event = json.loads((root / "examples/contracts/event.json").read_text(encoding="utf-8"))
    project = mission["project_id"]
    return {"workspace": workspace, "database": tmp_path / "state/control.sqlite3",
            "mission": mission, "event": event,
            "human": Principal("human", Role.HUMAN, project),
            "worker": Principal("worker", Role.EXECUTOR, project, "RUN-1"),
            "director": Principal("director", Role.DIRECTOR, project),
            "kernel": Principal("kernel", Role.KERNEL, project),
            "clock": FixedClock(datetime(2026, 10, 4, 11, tzinfo=timezone.utc))}
