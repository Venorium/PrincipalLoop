import io
import json
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest

from principalloop.codex.doctor import diagnose_integration, probe
from principalloop.codex.install import disable, enable, install, paths, uninstall
from principalloop.codex.profile import load_profile, path_from_codex, profile_path_for
from principalloop.codex.protocol import MAX_LINE, Protocol, serve
from principalloop.codex.service import Companion
from principalloop.codex.skill import skill_bytes
from principalloop.domain.types import Principal, Role
from principalloop.snapshot import Document
from principalloop.store import Reader, Store, StoreError


@pytest.fixture
def connected(storage_case):
    c = storage_case
    (c["workspace"] / "service.py").write_text("return original\n", encoding="utf-8", newline="\n")
    (c["workspace"] / "unrelated.txt").write_text("elsewhere", encoding="utf-8")
    result = install(c["workspace"], files=["service.py"], objective="Exercise resume context", state_dir=c["database"].parent)
    return c, Path(result["profile"]), Companion(result["profile"])


def checkpoint(companion, request="checkpoint-1"):
    return companion.call("pl_checkpoint", {"request_id": request, "summary": "Work interrupted; behavior still to verify.", "files": ["service.py"]})


def test_real_context_value_unchanged_noise_changed_and_historical_bytes(connected):
    c, profile, companion = connected
    first = checkpoint(companion)
    check = lambda: companion.call("pl_check", {"snapshot_id": first["snapshot_id"]})
    assert check()["status"] == "UNCHANGED"
    (c["workspace"] / "unrelated.txt").write_text("noise")
    assert check()["status"] == "UNCHANGED"
    (c["workspace"] / "service.py").write_text("return changed\n")
    result = check()
    assert result["status"] == "REVIEW_REQUIRED" and len(result["changed"]) == 1
    assert result["authorizes_action"] is False and result["complete_context_proven"] is False
    read = companion.call("pl_read", {"snapshot_id": first["snapshot_id"], "path": "service.py"})
    assert read["text"] == "return original\n" and read["trusted_instructions"] is False
    with Reader(c["database"], workspace=c["workspace"]) as store:
        assert store.snapshots.get(first["snapshot_id"])["details"]["agent_note"]["status"] == "UNVERIFIED"
        assert store.plan().epoch == 0 and not store.status()["owner"]


def test_retry_across_process_restart_preserves_original_capture(connected):
    c, profile, companion = connected
    first = checkpoint(companion)
    (c["workspace"] / "service.py").unlink()
    assert checkpoint(Companion(profile))["snapshot_id"] == first["snapshot_id"]
    assert Companion(profile).call("pl_check", {"snapshot_id": first["snapshot_id"]})["status"] == "REVIEW_REQUIRED"
    with pytest.raises(StoreError, match="ID_CONFLICT"):
        companion.call("pl_checkpoint", {"request_id": "checkpoint-1", "summary": "Different", "files": ["service.py"]})


@pytest.mark.parametrize("extra", [{"role": "HUMAN"}, {"workspace": "C:/"}, {"project_id": "another"}, {"budget": 10}])
def test_tool_cannot_assign_itself_authority(connected, extra):
    _, _, companion = connected
    with pytest.raises(StoreError, match="INVALID_ARGUMENTS"):
        companion.call("pl_checkpoint", {"request_id": "one", "summary": "test", "files": ["service.py"], **extra})


@pytest.mark.parametrize("path", ["unrelated.txt", "../outside", ".env", ".codex/config.toml"])
def test_selection_outside_human_scope_refused(connected, path):
    _, _, companion = connected
    with pytest.raises(StoreError, match="SCOPE_DENIED"):
        companion.call("pl_checkpoint", {"request_id": "one", "summary": "test", "files": [path]})


def test_new_human_restrictions_apply_to_old_capture(connected):
    c, profile, companion = connected
    first = checkpoint(companion)
    data = load_profile(profile)
    data["files"] = ["unrelated.txt"]
    profile.write_text(json.dumps(data))
    assert companion.call("pl_status", {})["checkpoints"] == []
    with pytest.raises(StoreError, match="SCOPE_DENIED"):
        companion.call("pl_read", {"snapshot_id": first["snapshot_id"], "path": "service.py"})


def test_readonly_calls_do_not_write_journal(connected):
    c, _, companion = connected
    sid = checkpoint(companion)["snapshot_id"]
    with Reader(c["database"], workspace=c["workspace"]) as reader:
        before = reader.status()["event_count"]
        companion.call("pl_status", {})
        companion.call("pl_check", {"snapshot_id": sid})
        companion.call("pl_read", {"snapshot_id": sid, "path": "service.py"})
        assert reader.status()["event_count"] == before


def test_install_preserves_other_settings_and_uninstall_keeps_data(storage_case):
    c = storage_case
    (c["workspace"] / "input.txt").write_text("input")
    config = c["workspace"] / ".codex/config.toml"
    config.parent.mkdir()
    original = b'model = "a-human-choice"\n[mcp_servers.existing]\ncommand = "other"\n'
    config.write_bytes(original)
    options = dict(files=["input.txt"], objective="Observe", state_dir=c["database"].parent)
    install(c["workspace"], **options)
    assert install(c["workspace"], **options)["already_installed"]
    assert tomllib.loads(config.read_text())["mcp_servers"]["existing"]["command"] == "other"
    assert uninstall(c["workspace"], c["database"].parent)["state_preserved"]
    assert config.read_bytes().rstrip() == original.rstrip()
    assert c["database"].exists()
    assert not (c["workspace"] / ".agents/skills/principalloop/SKILL.md").exists()


def test_modified_managed_config_is_never_overwritten(connected):
    c, _, _ = connected
    config = c["workspace"] / ".codex/config.toml"
    config.write_text(config.read_text().replace("startup_timeout_sec = 15", "startup_timeout_sec = 17"))
    before = config.read_bytes()
    with pytest.raises(StoreError, match="INSTALL_CONFLICT"):
        uninstall(c["workspace"], c["database"].parent)
    assert config.read_bytes() == before


def test_diagnostic_exercises_a_real_stdio_process_without_model(connected, tmp_path, monkeypatch):
    c, profile, _ = connected
    result = probe(c["workspace"], profile)
    assert set(result["tools"]) == {"pl_status", "pl_checkpoint", "pl_check", "pl_read"}
    assert result["status"]["enabled"] and result["status"]["workspace_source"] == "project-config"
    home = tmp_path / "codex-home"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    (home / "config.toml").write_text("[projects." + json.dumps(str(c["workspace"])) + ']\ntrust_level = "trusted"\n', encoding="utf-8")
    human = subprocess.run([sys.executable, "-m", "principalloop", "codex", "doctor", "--workspace", str(c["workspace"]),
                            "--state-dir", str(c["database"].parent)], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert human.returncode == 0 and "Real STDIO exchange" in human.stdout and "Project mode" in human.stdout, human.stdout


def init():
    return {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}}


def test_protocol_lifecycle_notifications_errors_and_utf8(connected):
    _, _, companion = connected
    protocol = Protocol(companion)
    assert protocol.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["error"]["code"] == -32002
    assert protocol.handle(init())["result"]["protocolVersion"] == "2025-11-25"
    assert protocol.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert len(protocol.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})["result"]["tools"]) == 4
    assert protocol.handle({"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "pl_checkpoint"}}) is None
    response = protocol.handle({"jsonrpc": "2.0", "id": "utf8", "method": "tools/call", "params": {"name": "pl_checkpoint", "arguments": {"request_id": "unicode", "summary": "Unicode note ✓ — Ω, ü, 漢字", "files": ["service.py"]}}})
    assert not response["result"]["isError"]
    refused = protocol.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "activate", "arguments": {}}})
    assert refused["result"]["isError"] and refused["result"]["structuredContent"]["not_a_no_change"]
    assert protocol.handle([])["error"]["code"] == -32600


def test_transport_rejects_malformed_and_oversized_messages(connected):
    _, profile, _ = connected
    output = io.BytesIO()
    assert serve(profile, io.BytesIO(b'{"id":1,"id":2}\n'), output) == 0
    assert json.loads(output.getvalue())["error"]["code"] == -32700
    output = io.BytesIO()
    assert serve(profile, io.BytesIO(b'x' * (MAX_LINE + 1)), output) == 2
    assert len(output.getvalue().splitlines()) == 1


def test_three_independent_mcp_clients_serialize_captures(connected):
    c, profile, _ = connected
    script = """import sys
from principalloop.codex.service import Companion
print(Companion(sys.argv[1]).call('pl_checkpoint', {'request_id':sys.argv[2], 'summary':'parallel client', 'files':['service.py']})['snapshot_id'])
"""
    clients = [subprocess.Popen([sys.executable, "-c", script, str(profile), f"client-{i}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE) for i in range(3)]
    try:
        for client in clients:
            out, err = client.communicate(timeout=15)
            assert client.returncode == 0 and out.startswith(b"S-"), err
    finally:
        for client in clients:
            if client.poll() is None:
                client.kill()
                client.communicate(timeout=5)
    with Reader(c["database"], workspace=c["workspace"]) as reader:
        assert reader.status()["snapshot_count"] == 3


def test_changed_mandatory_context_is_not_silently_accepted(connected):
    c, _, companion = connected
    sid = checkpoint(companion)["snapshot_id"]
    with Store(c["database"], workspace=c["workspace"]) as store:
        human = Principal("human", Role.HUMAN, store.plan().project_id)
        store.snapshots.put_object(Document("H-new", "HYPOTHESIS", "New premise", "Requires review"), human, expected_revision=0, event_id="new-premise")
        store.snapshots.set_required(["H-new"], human, expected_revision=store.snapshots.policy()["revision"], event_id="new-policy")
    check = companion.call("pl_check", {"snapshot_id": sid})
    assert check["status"] == "REVIEW_REQUIRED"
    assert "CONTEXT_VERSION_CHANGED" in {i["code"] for i in check["issues"]}
    with pytest.raises(StoreError, match="SCOPE_DENIED"):
        checkpoint(companion, "next-capture")


@pytest.mark.parametrize("change", ["missing", "modified"])
def test_reinstall_does_not_claim_success_with_missing_or_modified_skill(connected, change):
    c, _, _ = connected
    skill = paths(c["workspace"], c["database"].parent)["skill"]
    if change == "missing":
        skill.unlink()
    else:
        skill.write_text("Human customization")
    with pytest.raises(StoreError, match="INSTALL_CONFLICT"):
        install(c["workspace"], files=["service.py"], state_dir=c["database"].parent)


def test_uninstall_preserves_preexisting_portable_skill(storage_case):
    c = storage_case
    p = paths(c["workspace"], c["database"].parent)
    p["skill"].parent.mkdir(parents=True)
    p["skill"].write_bytes(skill_bytes())
    (c["workspace"] / "input.txt").write_text("input")
    install(c["workspace"], files=["input.txt"], objective="Observe", state_dir=c["database"].parent)
    uninstall(c["workspace"], c["database"].parent)
    assert p["skill"].read_bytes() == skill_bytes()


def test_install_failure_restores_config_and_keeps_recoverable_database(storage_case, monkeypatch):
    import importlib
    module = importlib.import_module("principalloop.codex.install")
    c = storage_case
    p = paths(c["workspace"], c["database"].parent)
    p["config"].parent.mkdir()
    before = b'model = "human-choice"\n'
    p["config"].write_bytes(before)
    (c["workspace"] / "input.txt").write_text("input")
    original = module.write_atomic
    def failure(path, data):
        if path == p["config"]:
            raise OSError("injected write failure")
        original(path, data)
    monkeypatch.setattr(module, "write_atomic", failure)
    with pytest.raises(OSError, match="injected"):
        install(c["workspace"], files=["input.txt"], objective="Observe", state_dir=c["database"].parent)
    assert p["config"].read_bytes() == before
    assert all(not p[key].exists() for key in ("profile", "receipt", "skill"))
    with Reader(c["database"], workspace=c["workspace"]) as store:
        assert store.mission()["objective"] == "Observe"


def test_context_report_is_private_and_does_not_claim_a_director_proposal(connected):
    c, _, companion = connected
    sid = checkpoint(companion)["snapshot_id"]
    result = subprocess.run([sys.executable, "-m", "principalloop", "codex", "report", "--workspace", str(c["workspace"]),
                             "--state-dir", str(c["database"].parent), "--snapshot", sid, "--json", "--no-open"], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(result.stdout)
    report = Path(data["report"])
    assert not report.is_relative_to(c["workspace"]) and data["context_unchanged"]
    content = report.read_text(encoding="utf-8")
    assert 'CONTEXT_INSPECTION_NOT_AUTHORIZATION' in content
    assert 'Work interrupted' in content
