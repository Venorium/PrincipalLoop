"""Exercise real Codex -> MCP -> PrincipalLoop the way a user installs it, without a model turn.

Plugin mode: the repository marketplace is added to an isolated CODEX_HOME, the plugin is
installed with `codex plugin add`, and App Server threads start in three directories: the
activated project, one of its subdirectories and an unrelated project.
Project mode: the optional .codex/config.toml path on a trusted synthetic project.

Only synthetic files, a temporary CODEX_HOME and temporary state roots are used. No
credentials are copied, no user chat is resumed, no turn/start request is sent, and
temporary or personal paths are removed from the report.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from queue import Queue, Empty
import shutil
import subprocess
import sys
import tempfile
import time
from threading import Thread

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ["pl_status", "pl_checkpoint", "pl_check", "pl_read"]


def executable():
    direct = shutil.which("codex.exe") or shutil.which("codex")
    if direct and Path(direct).suffix.lower() in (".cmd", ".ps1", ""):
        bundled = Path(direct).parent / "node_modules/@openai/codex/node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe"
        if bundled.is_file():
            return bundled
    if direct and Path(direct).suffix.lower() not in (".cmd", ".ps1"):
        return Path(direct)
    raise RuntimeError("Specify --codex with the real Codex executable, not a shell wrapper")


def origin(binary):
    text = str(binary).replace("\\", "/").lower()
    return "npm CLI" if "node_modules" in text else "desktop app bundle" if "/openai/codex/bin/" in text else "custom path"


class Client:
    def __init__(self, process):
        self.process = process
        self.queue = Queue()
        self.counter = 0
        self.methods = []
        self.samples = []
        def receive():
            for line in process.stdout:
                self.queue.put(json.loads(line))
            self.queue.put(None)
        self.reader = Thread(target=receive, daemon=True)
        self.reader.start()

    def send(self, payload):
        self.process.stdin.write(json.dumps(payload) + "\n")
        self.process.stdin.flush()

    def request(self, method, params):
        self.counter += 1
        self.methods.append(method)
        self.send({"jsonrpc": "2.0", "id": self.counter, "method": method, "params": params})
        started = time.perf_counter()
        deadline = time.monotonic() + 60
        while True:
            try:
                message = self.queue.get(timeout=max(.01, deadline - time.monotonic()))
            except Empty:
                raise RuntimeError(f"Codex request timed out: {method}") from None
            if message is None:
                raise RuntimeError(f"Codex exited during {method}")
            if message.get("id") == self.counter and ("result" in message or "error" in message):
                if "error" in message:
                    raise RuntimeError(f"{method}: {message['error']}")
                self.samples.append({"method": method, "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
                                     "response_bytes": len(json.dumps(message, ensure_ascii=False).encode("utf-8"))})
                return message["result"]
            if "id" in message and "method" in message:
                self.send({"jsonrpc": "2.0", "id": message["id"], "error": {"code": -32601, "message": "Qualification never grants additional capabilities"}})


class AppServer:
    def __init__(self, binary, cwd, env, log):
        self.errors = log.open("w", encoding="utf-8")
        self.process = subprocess.Popen([str(binary), "app-server", "--stdio"], cwd=cwd, env=env, stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=self.errors, text=True, encoding="utf-8", bufsize=1)
        self.client = Client(self.process)
        self.client.request("initialize", {"clientInfo": {"name": "principalloop_qualification", "version": "0.1.0"}, "capabilities": {"experimentalApi": True}})
        self.client.send({"jsonrpc": "2.0", "method": "initialized", "params": {}})

    def thread(self, cwd):
        return self.client.request("thread/start", {"cwd": str(cwd), "ephemeral": True})["thread"]["id"]

    def server(self, tid):
        inventory = self.client.request("mcpServerStatus/list", {"threadId": tid, "detail": "toolsAndAuthOnly"})
        entry = next(e for e in inventory.get("data", []) if e.get("name") == "principalloop")
        return entry

    def call(self, tid, tool, arguments, expect_error=False):
        result = self.client.request("mcpServer/tool/call", {"threadId": tid, "server": "principalloop", "tool": tool, "arguments": arguments})
        if bool(result.get("isError")) != expect_error:
            raise RuntimeError(f"{tool}: unexpected result {result}")
        return result["structuredContent"]

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            self.process.terminate()
            self.process.wait(timeout=10)
        self.client.reader.join(timeout=2)
        self.process.stdout.close()
        self.errors.close()


def resume_cycle(server, tid, workspace):
    """The user-visible loop: checkpoint, unchanged, noise, change, old bytes, lost-response retry."""
    source = workspace / "service.txt"
    captured = server.call(tid, "pl_checkpoint", {"request_id": "qualification-1", "summary": "Synthetic resume checkpoint", "files": ["service.txt"]})
    sid = captured["snapshot_id"]
    before = server.call(tid, "pl_check", {"snapshot_id": sid})
    (workspace / "unrelated.txt").write_bytes(b"noise")
    noise = server.call(tid, "pl_check", {"snapshot_id": sid})
    source.write_bytes(b"changed premise\n")
    after = server.call(tid, "pl_check", {"snapshot_id": sid})
    historical = server.call(tid, "pl_read", {"snapshot_id": sid, "path": "service.txt"})
    repeated = server.call(tid, "pl_checkpoint", {"request_id": "qualification-1", "summary": "Synthetic resume checkpoint", "files": ["service.txt"]})
    return {"unchanged_context": before["status"] == "UNCHANGED", "unrelated_change_ignored": noise["status"] == "UNCHANGED",
            "stale_context_detected": after["status"] == "REVIEW_REQUIRED" and [c["path"] for c in after["changed"]] == ["service.txt"],
            "captured_bytes_preserved": historical["text"] == "original premise\n", "retry_keeps_checkpoint": repeated["snapshot_id"] == sid}


def run(command, env, cwd):
    result = subprocess.run([str(c) for c in command], cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", timeout=180)
    if result.returncode:
        raise RuntimeError(f"{command[1:4]} failed: {result.stdout[-800:]} {result.stderr[-800:]}")
    return result.stdout


def plugin_mode(binary, root, env):
    project, other = root / "project", root / "other"
    for folder in (project / "src", other):
        folder.mkdir(parents=True)
    (project / ".git").mkdir()
    (other / ".git").mkdir()
    (project / "service.txt").write_bytes(b"original premise\n")
    principalloop = shutil.which("principalloop", path=env["PATH"])
    if principalloop is None:
        raise RuntimeError("The plugin launches 'principalloop'; install the package in this environment first")
    run([principalloop, "codex", "enable", "--workspace", project, "--allow-file", "service.txt", "--objective", "Synthetic plugin qualification"], env, root)
    market = json.loads(run([binary, "plugin", "marketplace", "add", ROOT, "--json"], env, root))
    added = json.loads(run([binary, "plugin", "add", "principalloop@principalloop", "--json"], env, root))
    server = AppServer(binary, root, env, root / "plugin.stderr")
    try:
        main = server.thread(project)
        entry = server.server(main)
        status = server.call(main, "pl_status", {})
        checks = {"marketplace_added": market.get("marketplaceName") == "principalloop",
                  "plugin_installed": added.get("pluginId") == "principalloop@principalloop" and added.get("version") == "0.1.0",
                  "server_launched_by_plugin": entry.get("pluginId") == "principalloop@principalloop" and sorted(entry.get("tools", {})) == sorted(TOOLS),
                  "project_resolved_from_chat_directory": status["enabled"] and Path(status["workspace"]) == project.resolve()}
        checks.update(resume_cycle(server, main, project))
        nested = server.call(server.thread(project / "src"), "pl_status", {})
        checks["subdirectory_resolves_project"] = nested["enabled"] and Path(nested["workspace"]) == project.resolve()
        outsider = server.thread(other)
        inactive = server.call(outsider, "pl_status", {})
        refused = server.call(outsider, "pl_check", {"snapshot_id": "S-unknown"}, expect_error=True)
        checks["inactive_project_explained"] = inactive["enabled"] is False and "principalloop codex enable" in inactive["next_step"]
        checks["inactive_project_never_unchanged"] = refused == {"error": "NOT_ENABLED", "not_a_no_change": True}
        return {"checks": checks, "workspace_source": sorted({status["workspace_source"], nested["workspace_source"], inactive["workspace_source"]}),
                "server_capabilities": entry.get("serverCapabilities"), "observed_calls": server.client.samples,
                "protocol_methods": sorted(set(server.client.methods))}
    finally:
        server.close()


def project_mode(binary, root, env):
    from principalloop.codex.install import install
    workspace = root / "legacy"
    workspace.mkdir()
    (workspace / "service.txt").write_bytes(b"original premise\n")
    install(workspace, files=["service.txt"], objective="Synthetic project-mode qualification", state_dir=root / "legacy-state")
    home = root / "legacy-codex-home"
    home.mkdir()
    config = (workspace / ".codex/config.toml").read_text(encoding="utf-8")
    config += '\n[analytics]\nenabled = false\n[projects.' + json.dumps(str(workspace)) + ']\ntrust_level = "trusted"\n'
    (home / "config.toml").write_text(config, encoding="utf-8")
    server = AppServer(binary, workspace, {**env, "CODEX_HOME": str(home)}, root / "project.stderr")
    try:
        tid = server.thread(workspace)
        server.server(tid)
        status = server.call(tid, "pl_status", {})
        checks = {"status_available": status["enabled"] and status["workspace_source"] == "project-config"}
        checks.update(resume_cycle(server, tid, workspace))
        return {"checks": checks, "observed_calls": server.client.samples}
    finally:
        server.close()


def scrub(value, replacements):
    if isinstance(value, dict):
        return {k: scrub(v, replacements) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v, replacements) for v in value]
    if isinstance(value, str):
        for secret, label in replacements:
            value = value.replace(secret, label)
    return value


def qualify(binary):
    version = subprocess.check_output([str(binary), "--version"], text=True, encoding="utf-8", timeout=10).strip()
    with tempfile.TemporaryDirectory(prefix="principalloop-codex-") as directory:
        root = Path(directory).resolve()
        assert root.is_relative_to(Path(tempfile.gettempdir()).resolve())
        env = os.environ.copy()
        for key in ("OPENAI_API_KEY", "CODEX_API_KEY", "CHATGPT_API_KEY"):
            env.pop(key, None)
        home = root / "codex-home"
        home.mkdir()
        (home / "config.toml").write_text("[analytics]\nenabled = false\n", encoding="utf-8")
        # Standard roots, redirected for these children only: Codex config and private state.
        env.update(CODEX_HOME=str(home), LOCALAPPDATA=str(root / "local-app-data"), XDG_STATE_HOME=str(root / "xdg-state"), PYTHONUTF8="1")
        env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
        plugin = plugin_mode(binary, root, env)
        project = project_mode(binary, root, env)
    report = {"codex": version, "binary": origin(binary), "plugin_mode": plugin, "project_mode": project,
              "passed": all(plugin["checks"].values()) and all(project["checks"].values()), "model_turns": 0}
    return scrub(report, [(str(root), "<temp>"), (str(Path.home()), "<home>")])


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--codex", type=Path, action="append", help="Real Codex executable; repeatable")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    runs = [qualify(binary) for binary in (args.codex or [executable()])]
    sources = [*ROOT.glob("src/principalloop/codex/*.py"), ROOT / "src/principalloop/snapshot/engine.py", Path(__file__).resolve(),
               ROOT / "plugins/principalloop/.mcp.json", ROOT / "plugins/principalloop/.codex-plugin/plugin.json",
               ROOT / "plugins/principalloop/skills/principalloop/SKILL.md", ROOT / ".agents/plugins/marketplace.json"]
    report = {"qualified_at_utc": datetime.now(timezone.utc).isoformat(), "passed": all(r["passed"] for r in runs), "runs": runs,
              "transport": "Codex App Server -> plugin MCP STDIO -> PrincipalLoop", "model_turns": 0,
              "latency_claim": "Descriptive samples on synthetic files, not a benchmark",
              "scope": "Ephemeral synthetic threads; a desktop chat and the strategic benefit are not qualified here",
              "source_sha256": {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(sources)}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"passed": report["passed"], "runs": [{"codex": r["codex"], "binary": r["binary"], "passed": r["passed"],
                                                            "failed": [k for m in ("plugin_mode", "project_mode") for k, v in r[m]["checks"].items() if not v]}
                                                           for r in runs]}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
