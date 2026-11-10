"""Plugin mode: Codex chooses the start directory, the human chooses the files."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from principalloop.codex import doctor
from principalloop.codex.doctor import diagnose_integration, probe
from principalloop.codex.install import disable, enable, install, paths, uninstall
from principalloop.codex.profile import load_profile, path_from_codex, profile_path_for
from principalloop.codex.protocol import Protocol
from principalloop.codex.service import Companion
from principalloop.codex.skill import skill_bytes
from principalloop.store import Reader, StoreError

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/principalloop"


@pytest.fixture
def project(tmp_path, monkeypatch):
    # Default private state lives under these roots; isolate them per test.
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local-app-data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
    home = tmp_path / "codex-home"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    workspace = tmp_path / "project"
    (workspace / "src").mkdir(parents=True)
    (workspace / ".git").mkdir()
    (workspace / "service.py").write_text("return original\n", encoding="utf-8", newline="\n")
    (workspace / "notes.md").write_text("plan\n", encoding="utf-8", newline="\n")
    return workspace, home


def activated(workspace, files=("service.py",)):
    return enable(workspace, files=list(files), objective="Reprendre un travail Codex")


def test_codex_start_directory_and_subdirectories_resolve_the_activated_project(project):
    workspace, _ = project
    activated(workspace)
    for start in (workspace, workspace / "src"):
        status = Companion(cwd=start).call("pl_status", {})
        assert status["enabled"] and Path(status["workspace"]) == workspace.resolve()
        assert status["workspace_source"] == "codex-process-cwd" and status["allowed_files"] == ["service.py"]
    companion = Companion(cwd=workspace / "src")
    sid = companion.call("pl_checkpoint", {"request_id": "r-1", "summary": "Plan approved.", "files": ["service.py"]})["snapshot_id"]
    (workspace / "service.py").write_text("return changed\n", encoding="utf-8")
    check = companion.call("pl_check", {"snapshot_id": sid})
    assert check["status"] == "REVIEW_REQUIRED" and check["changed"][0]["path"] == "service.py"
    assert companion.call("pl_read", {"snapshot_id": sid, "path": "service.py"})["text"] == "return original\n"


@pytest.mark.parametrize("encode", [lambda p: p.as_uri(), str])
def test_sandbox_cwd_sent_by_codex_takes_precedence_over_process_directory(project, tmp_path, encode):
    workspace, _ = project
    activated(workspace)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    meta = {"codex/sandbox-state": {"sandboxCwd": encode(workspace / "src"), "permissionProfile": {}}}
    status = Companion(cwd=elsewhere).call("pl_status", {}, meta=meta)
    assert status["enabled"] and status["workspace_source"] == "codex-sandbox-state"
    assert not Companion(cwd=elsewhere).call("pl_status", {})["enabled"]


@pytest.mark.parametrize("value", ["relative/dir", "file://server/share/project", "", None, 42, "x" * 5000])
def test_untrusted_or_relative_sandbox_values_are_ignored(value):
    assert path_from_codex(value) is None


def test_tool_arguments_never_select_a_workspace(project):
    workspace, _ = project
    activated(workspace)
    companion = Companion(cwd=workspace)
    for name, arguments in (("pl_status", {"workspace": str(workspace)}), ("pl_check", {"snapshot_id": "S-x", "cwd": "C:/"})):
        with pytest.raises(StoreError, match="INVALID_ARGUMENTS"):
            companion.call(name, arguments)


def test_check_returns_a_bounded_diff_for_text_and_none_for_binary(project):
    workspace, _ = project
    (workspace / "blob.bin").write_bytes(b"\xff\x00\x01")
    (workspace / "big.txt").write_text("".join(f"line {i}\n" for i in range(2000)), encoding="utf-8")
    enable(workspace, files=["service.py", "notes.md", "blob.bin", "big.txt"], objective="Diff")
    companion = Companion(cwd=workspace)
    sid = companion.call("pl_checkpoint", {"request_id": "d", "summary": "s", "files": ["service.py", "notes.md", "blob.bin", "big.txt"]})["snapshot_id"]
    (workspace / "service.py").write_text("return changed\n", encoding="utf-8", newline="\n")
    (workspace / "notes.md").unlink()
    (workspace / "blob.bin").write_bytes(b"\xff\x00\x02")
    (workspace / "big.txt").write_text("".join(f"edited {i}\n" for i in range(2000)), encoding="utf-8")
    changed = {c["path"]: c for c in companion.call("pl_check", {"snapshot_id": sid})["changed"]}
    assert "-return original\n+return changed" in changed["service.py"]["diff"] and not changed["service.py"]["diff_truncated"]
    assert "+++ /dev/null" in changed["notes.md"]["diff"] and "-plan" in changed["notes.md"]["diff"]
    assert "diff" not in changed["blob.bin"]
    assert changed["big.txt"]["diff_truncated"] and sum(len(c.get("diff", "")) for c in changed.values()) <= 6000


def test_inactive_project_explains_activation_and_never_reports_unchanged(project, tmp_path):
    _, _ = project
    other = tmp_path / "other"
    (other / ".git").mkdir(parents=True)
    status = Companion(cwd=other).call("pl_status", {})
    assert status["enabled"] is False and "principalloop codex enable" in status["next_step"] and str(other) in status["next_step"]
    with pytest.raises(StoreError, match="NOT_ENABLED"):
        Companion(cwd=other).call("pl_checkpoint", {"request_id": "r", "summary": "s", "files": ["a.py"]})
    protocol = Protocol(Companion(cwd=other))
    protocol.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}})
    protocol.handle({"jsonrpc": "2.0", "method": "notifications/initialized"})
    reply = protocol.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "pl_check", "arguments": {"snapshot_id": "S-1"}}})["result"]
    assert reply["isError"] and reply["structuredContent"] == {"error": "NOT_ENABLED", "not_a_no_change": True}
    assert "principalloop codex enable" in reply["content"][0]["text"] and str(other) not in reply["content"][0]["text"]


def test_enable_updates_scope_in_place_and_disable_keeps_captures(project):
    workspace, _ = project
    with pytest.raises(StoreError, match="OBJECTIVE_REQUIRED"):
        enable(workspace, files=["service.py"])
    first = activated(workspace)
    actor = load_profile(first["profile"])["actor_id"]
    sid = Companion(cwd=workspace).call("pl_checkpoint", {"request_id": "r", "summary": "s", "files": ["service.py"]})["snapshot_id"]
    assert not activated(workspace)["changed"]
    second = enable(workspace, files=["service.py", "notes.md", "later.txt"])
    assert second["changed"] and second["missing_files"] == ["later.txt"]
    assert load_profile(second["profile"])["actor_id"] == actor
    assert [c["snapshot_id"] for c in Companion(cwd=workspace).call("pl_status", {})["checkpoints"]] == [sid]
    with pytest.raises(StoreError, match="PATH_DENIED"):
        enable(workspace, files=["../outside.txt"])
    assert disable(workspace)["disabled"] and disable(workspace)["already_disabled"]
    assert not Companion(cwd=workspace).call("pl_status", {})["enabled"]
    with Reader(paths(workspace)["database"], workspace=workspace) as reader:
        assert reader.status()["snapshot_count"] == 1


def test_project_mode_can_migrate_to_plugin_without_losing_identity(project):
    workspace, _ = project
    install(workspace, files=["service.py"], objective="Observe")
    with pytest.raises(StoreError, match="INSTALL_PRESENT"):
        disable(workspace)
    actor = load_profile(profile_path_for(workspace))["actor_id"]
    result = uninstall(workspace, keep_profile=True)
    assert result["profile_kept"] and not (workspace / ".agents/skills/principalloop/SKILL.md").exists()
    assert not (workspace / ".codex/config.toml").exists()
    assert load_profile(profile_path_for(workspace))["actor_id"] == actor
    assert Companion(cwd=workspace).call("pl_status", {})["enabled"]


def test_plugin_server_over_stdio_uses_its_start_directory(project):
    workspace, _ = project
    activated(workspace)
    exchange = probe(workspace / "src")
    assert exchange["status"]["enabled"] and exchange["status"]["workspace_source"] == "codex-process-cwd"
    assert len(exchange["tools"]) == 4


def test_doctor_names_the_untrusted_project_failure_and_the_fix(project, monkeypatch):
    workspace, home = project
    install(workspace, files=["service.py"], objective="Observe")
    report = diagnose_integration(workspace)
    codex = next(c for c in report["checks"] if c["id"] == "codex")
    assert not report["ready"] and codex["status"] == "fail" and "not trusted" in codex["detail"]
    assert "codex plugin marketplace add Venorium/PrincipalLoop" in codex["fix"]
    uninstall(workspace, keep_profile=True)
    (home / "config.toml").write_text('[plugins."principalloop@principalloop"]\nenabled = true\n', encoding="utf-8")
    monkeypatch.setattr(doctor.shutil, "which", lambda name: None)
    report = diagnose_integration(workspace / "src")
    states = {c["id"]: c["status"] for c in report["checks"]}
    assert states["codex"] == "ok" and states["command"] == "fail" and states["mcp"] == "ok"
    monkeypatch.setattr(doctor.shutil, "which", lambda name: sys.executable)
    monkeypatch.setattr(doctor.subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout="principalloop 9.9.9\n"))
    monkeypatch.setattr(doctor, "probe", lambda *a, **k: {"tools": [1, 2, 3, 4], "status": {}})
    command = next(c for c in diagnose_integration(workspace)["checks"] if c["id"] == "command")
    assert command["status"] == "warn" and "uv tool upgrade" in command["fix"]


def test_doctor_cli_is_readable_and_exit_code_reflects_readiness(project):
    workspace, _ = project
    result = subprocess.run([sys.executable, "-m", "principalloop", "codex", "doctor", "--workspace", str(workspace)],
                            capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 1 and "[X]" in result.stdout and "principalloop codex enable" in result.stdout


def test_plugin_package_is_consistent_and_starts_in_the_chat_directory():
    market = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
    entry = market["plugins"][0]
    manifest = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    servers = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
    assert (ROOT / entry["source"]["path"]).resolve() == PLUGIN.resolve()
    assert entry["name"] == manifest["name"] == PLUGIN.name == "principalloop"
    assert {"installation", "authentication"} <= set(entry["policy"]) and entry["category"]
    server = servers["principalloop"]
    # No cwd: Codex then launches the server in the chat's working directory.
    assert "cwd" not in server and server["command"] == "principalloop" and server["args"] == ["codex", "serve"]
    interface = manifest["interface"]
    assert len(interface["defaultPrompt"]) <= 3 and all(len(p) <= 128 for p in interface["defaultPrompt"])
    for asset in [interface["composerIcon"], interface["logo"], *interface["screenshots"]]:
        assert asset.startswith("./assets/") and (PLUGIN / asset).is_file(), asset
    import tomllib
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    assert manifest["version"] == version


def test_packaged_skill_is_the_plugin_skill():
    source = (PLUGIN / "skills/principalloop/SKILL.md").read_text(encoding="utf-8").encode("utf-8")
    assert skill_bytes() == source and source.startswith(b"---\nname: principalloop\n")
