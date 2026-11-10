"""Read-only diagnosis of the Codex integration, written for humans.

It never edits Codex, the project or the private state. Each check states what was
observed and, when needed, the exact command to run. A green report cannot prove that
an already open chat reloaded its plugins.
"""

from importlib.metadata import version
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

from ..runtime import diagnose
from ..store import StoreError
from .install import paths
from .profile import find_profile, same_path

MARKETPLACE = "codex plugin marketplace add Venorium/PrincipalLoop"
PLUGIN = "codex plugin add principalloop@principalloop"
# uv's own Python builds carry a patched SQLite; some system builds (python.org 3.13.17 on Windows) do not.
TOOL = "uv tool install --managed-python git+https://github.com/Venorium/PrincipalLoop"
REINSTALL = "uv tool install --force --managed-python git+https://github.com/Venorium/PrincipalLoop"



def codex_config():
    path = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "config.toml"
    try:
        return tomllib.loads(path.read_text(encoding="utf-8-sig")), path
    except FileNotFoundError:
        return {}, path
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        return None, path


def _plain(key):
    for prefix in ("\\\\?\\UNC\\", "\\\\?\\"):
        if key.upper().startswith(prefix.upper()):
            return ("\\\\" if "UNC" in prefix else "") + key[len(prefix):]
    return key


def trust_level(config, workspace):
    """Trust recorded for the workspace or its nearest listed ancestor."""
    projects = (config or {}).get("projects", {})
    for candidate in (workspace, *workspace.parents):
        for key, value in projects.items():
            if isinstance(value, dict) and same_path(_plain(key), candidate):
                return value.get("trust_level"), candidate
    return None, None


def enabled_plugins(config):
    plugins = (config or {}).get("plugins", {})
    return sorted(key for key, value in plugins.items()
                  if key.split("@")[0] == "principalloop" and isinstance(value, dict) and value.get("enabled", True))


def probe(workspace, profile=None):
    """Real STDIO exchange with this installation; zero model calls."""
    command = [sys.executable, "-m", "principalloop", "codex", "serve"] + (["--profile", str(profile)] if profile else [])
    calls = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "principalloop-doctor", "version": "1"}}},
             {"jsonrpc": "2.0", "method": "notifications/initialized"},
             {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
             {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "pl_status", "arguments": {}}}]
    result = subprocess.run(command, cwd=workspace, input="\n".join(json.dumps(c) for c in calls) + "\n",
                            capture_output=True, text=True, encoding="utf-8", timeout=20)
    if result.returncode:
        raise StoreError("CONNECTOR_FAILED", "The MCP process did not exit cleanly.")
    replies = {item["id"]: item for item in map(json.loads, result.stdout.splitlines())}
    if set(replies) != {1, 2, 3} or any("error" in r for r in replies.values()) or replies[3]["result"].get("isError"):
        raise StoreError("CONNECTOR_FAILED", "The MCP exchange or project access failed.")
    return {"tools": [t["name"] for t in replies[2]["result"]["tools"]], "status": replies[3]["result"]["structuredContent"]}


def diagnose_integration(workspace, state_dir=None):
    workspace = Path(workspace).resolve(strict=True)
    checks = []

    def add(key, status, label, detail, fix=None):
        checks.append({"id": key, "status": status, "label": label, "detail": detail, "fix": fix})

    runtime = diagnose()
    if not runtime["admitted"]:
        add("runtime", "fail", "Runtime", f"Python {runtime['python']} / SQLite {runtime['sqlite']} refused by the kernel.", REINSTALL)
    elif not runtime["reference_runtime"]:
        add("runtime", "warn", "Runtime", f"Python {runtime['python']}, SQLite {runtime['sqlite']}: accepted; published evidence uses Python {runtime['reference_python']}.")
    else:
        add("runtime", "ok", "Runtime", f"Python {runtime['python']}, SQLite {runtime['sqlite']}: reference runtime.")

    p = paths(workspace, state_dir)
    legacy = p["receipt"].exists()
    profile_path = p["profile"] if (legacy or state_dir) and p["profile"].exists() else find_profile(workspace)[0]
    enable = f'principalloop codex enable --workspace "{workspace}" --allow-file <relative/path> --objective "<goal>"'
    profile = None
    if profile_path is None:
        add("activation", "fail", "Activation", "No tracked file for this project.", enable)
    else:
        profile = json.loads(Path(profile_path).read_text(encoding="utf-8"))
        root = Path(profile["workspace"])
        missing = [f for f in profile["files"] if not (root / f).is_file()]
        where = "" if same_path(root, workspace) else f" (parent project {root})"
        add("activation", "warn" if missing else "ok", "Activation",
            f"{len(profile['files'])} tracked file(s){where}" + ("; missing: " + ", ".join(missing) if missing else "."))

    if profile is not None:
        try:
            exchange = probe(Path(profile["workspace"]), profile_path if legacy or state_dir else None)
            add("mcp", "ok", "MCP server", f"Real STDIO exchange, {len(exchange['tools'])} tools, no model call.")
        except (StoreError, OSError, ValueError, subprocess.SubprocessError) as error:
            add("mcp", "fail", "MCP server", "Local exchange failed" + f" ({getattr(error, 'code', type(error).__name__)}).", "principalloop doctor")

    config, config_path = codex_config()
    plugins = enabled_plugins(config)
    command = shutil.which("principalloop")
    mine = version("principalloop")
    if plugins:
        if command is None:
            add("command", "fail", "Plugin command", "The plugin runs 'principalloop', which is not on PATH.", TOOL + ", then uv tool update-shell, and restart Codex")
        else:
            try:
                found = subprocess.run([command, "--version"], capture_output=True, text=True, timeout=15).stdout.strip().split()[-1]
            except (OSError, subprocess.SubprocessError, IndexError):
                found = "?"
            status = "ok" if found == mine else "warn"
            add("command", status, "Plugin command", f"{command} (version {found}" + ("" if found == mine else f", this diagnosis: {mine}") + ").",
                None if status == "ok" else "uv tool upgrade principalloop")

    # The project-mode block and its trust belong to the activated root, not to a subdirectory.
    root = Path(profile["workspace"]) if profile else workspace
    project_config = root / ".codex/config.toml"
    block = project_config.is_file() and "[mcp_servers.principalloop]" in project_config.read_text(encoding="utf-8-sig")
    level, trusted_root = trust_level(config, root)
    if config is None:
        add("codex", "warn", "Codex", f"Unreadable configuration: {config_path}.")
    elif plugins:
        add("codex", "ok", "Codex", "Plugin enabled: " + ", ".join(plugins) + ". Open a new chat to load its tools.")
    elif block and level == "trusted":
        add("codex", "ok", "Codex", "Project mode: .codex/config.toml is loaded because the project is trusted. Open a new chat.")
    elif block:
        add("codex", "fail", "Codex", "Codex ignores .codex/config.toml: this project is not trusted.",
            "Install the plugin: " + MARKETPLACE + ", then " + PLUGIN)
    else:
        add("codex", "fail", "Codex", "The PrincipalLoop plugin is not installed in Codex.", MARKETPLACE + ", then " + PLUGIN)
    ready = all(c["status"] != "fail" for c in checks)
    return {"ready": ready, "workspace": str(workspace), "version": mine, "checks": checks,
            "desktop_chat_connected": "UNKNOWN", "director": "NOT_CONNECTED", "model_calls": 0}


def render(report):
    marks = {"ok": "[ok]  ", "warn": "[!]   ", "fail": "[X]   "}
    lines = [f"PrincipalLoop {report['version']} — {report['workspace']}", ""]
    for check in report["checks"]:
        lines.append(f"{marks[check['status']]}{check['label']}{': '}{check['detail']}")
        if check["fix"]:
            lines.append(f"      → {check['fix']}")
    lines.append("")
    lines.append("Ready. In a new Codex chat: $principalloop Save a checkpoint of this work." if report["ready"]
                 else "Fix the [X] lines before using it in Codex.")
    return "\n".join(lines)
