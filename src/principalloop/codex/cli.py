"""Human commands for the Codex companion: activation, diagnosis, report, server."""

import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from uuid import uuid4
import webbrowser

from ..snapshot.cli import _report_for_snapshot
from ..snapshot.i18n import LANGS, TEXT, default_lang
from ..snapshot.report import write_report
from ..store import Reader, StoreError
from ..store.paths import private_path
from .doctor import diagnose_integration, probe, render
from .install import disable, enable, install, paths, uninstall
from .profile import find_profile, load_profile
from .protocol import serve
from .service import current_bytes

HELP = {
    "enable": "Enable this project for the Codex plugin: the human chooses the tracked files",
    "disable": "Remove the activation; private captures are kept",
    "doctor": "Diagnose the Codex integration and print the exact fix",
    "report": "Open the visual report of a checkpoint (latest by default)",
    "install": "Project mode: write .codex/config.toml and the skill into the repository (no plugin)",
    "uninstall": "Remove project mode; --keep-profile keeps the activation",
    "serve": "MCP STDIO server (started by Codex)",
}


def add_commands(commands):
    root = commands.add_parser("codex", help="Context companion for Codex: enable, diagnose, inspect")
    actions = root.add_subparsers(dest="codex_action", required=True)
    for name, text in HELP.items():
        action = actions.add_parser(name, help=text, description=text)
        if name == "serve":
            action.add_argument("--profile", type=Path, help="Project mode: profile fixed by the human installation")
            continue
        action.add_argument("--workspace", type=Path, default=Path.cwd(), help="Project root (default: current directory)")
        if name not in ("enable", "disable"):
            action.add_argument("--state-dir", type=Path, help="Custom private state directory, outside the workspace")
        action.add_argument("--json", action="store_true", help="Machine-readable output")
        if name in ("enable", "install"):
            action.add_argument("--allow-file", action="append", required=True, metavar="PATH", help="Tracked file, relative to the root; repeatable")
            action.add_argument("--object", action="append", default=[], metavar="ID", help="Tracked premise; repeatable")
            action.add_argument("--objective", help="Human goal, required on the first activation")
        if name == "uninstall":
            action.add_argument("--keep-profile", action="store_true", help="Keep the activation for the plugin")
        if name == "report":
            action.add_argument("--snapshot", default="latest", help="Exact checkpoint ID, or latest")
            action.add_argument("--no-open", action="store_true", help="Generate without opening the browser")
            action.add_argument("--lang", choices=LANGS, help="Report language (default: English)")


def _profile_for(args, p):
    if args.state_dir or p["receipt"].exists():
        return p["profile"] if p["profile"].exists() else None
    return find_profile(p["workspace"])[0]


def _preview(data, lang):
    if data is None:
        return TEXT[lang]["missing_file"]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return TEXT[lang]["binary"]
    return text if len(text) <= 8192 else text[:8192] + "\n…"


def execute(args):
    if args.codex_action == "serve":
        return serve(args.profile)  # Only JSON-RPC on stdout.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        action = args.codex_action
        state_dir = getattr(args, "state_dir", None)
        p = paths(args.workspace, state_dir)
        if action == "enable":
            result = enable(args.workspace, files=args.allow_file, object_ids=args.object, objective=args.objective)
            verb = ("enabled" if result["created"] else "updated" if result["changed"] else "already enabled, unchanged")
            message = f"PrincipalLoop {verb} — {result['workspace']}\n" + "Tracked files: " + ", ".join(result["files"])
            if result["missing_files"]:
                message += "\nNot present yet: " + ", ".join(result["missing_files"])
            message += "\nCheck the integration: principalloop codex doctor"
        elif action == "disable":
            result = disable(args.workspace)
            message = "Disabled. Private captures are kept." if result["disabled"] else "This project was not enabled."
        elif action == "install":
            result = install(args.workspace, files=args.allow_file, object_ids=args.object, objective=args.objective, state_dir=state_dir)
            message = "Project mode installed. Codex loads it only for a trusted project; the plugin is recommended.\nTracked files: " + ", ".join(result["files"]) + "\nprincipalloop codex doctor"
        elif action == "uninstall":
            result = uninstall(args.workspace, state_dir, keep_profile=args.keep_profile)
            message = "Project mode removed" + ("; activation kept for the plugin." if args.keep_profile else ". Private captures are kept.")
        elif action == "doctor":
            result = diagnose_integration(args.workspace, state_dir)
            print(json.dumps(result, ensure_ascii=True) if args.json else render(result))
            return 0 if result["ready"] else 1
        else:
            profile_path = _profile_for(args, p)
            if profile_path is None:
                raise StoreError("NOT_ENABLED", "Project not enabled: principalloop codex enable --allow-file <path> --objective \"<goal>\"")
            profile = load_profile(profile_path)
            workspace, database = Path(profile["workspace"]), Path(profile["database"])
            with Reader(database, workspace=workspace) as store:
                snapshots = store.snapshots.list()
                if not snapshots:
                    raise StoreError("UNKNOWN_SNAPSHOT", "No checkpoint yet: ask Codex \"$principalloop Save a checkpoint of this work\".")
                sid = snapshots[0]["snapshot_id"] if args.snapshot == "latest" else args.snapshot
                lang = args.lang or default_lang()
                data = _report_for_snapshot(store, sid, lang)
                case = data["scenarios"][0]
                case["validation"] = store.snapshots.compare(sid)
                files = case["snapshot"]["details"]["files"]
                case["changes"] = [{"name": files[d["reference_id"]]["path"],
                                    "before": _preview(store.snapshots.artifact(sid, d["reference_id"]), lang),
                                    "after": _preview(current_bytes(workspace, files[d["reference_id"]]["path"]), lang)}
                                   for d in case["validation"]["dependencies"] if d["state"] != "CURRENT" and d["reference_id"] in files]
                case["explanation"] = TEXT[lang]["compare"]
                note = case["snapshot"]["details"].get("agent_note", {}).get("text")
                if note:
                    case["explanation"] += TEXT[lang]["note"] + note
                output = write_report(data, private_path(database.parent / "reports" / f"codex-{uuid4().hex}.html", workspace))
            result = {"report": str(output), "snapshot_id": sid, "context_unchanged": case["validation"]["eligible"]}
            message = ("No change observed" if result["context_unchanged"] else "Review needed") + f" — {sid}\n" + "Report: " + str(output)
            if not args.no_open:
                webbrowser.open(output.as_uri())
        print(json.dumps(result, ensure_ascii=True) if args.json else message)
        return 0
    except (StoreError, ValueError, OSError, sqlite3.Error, subprocess.SubprocessError) as error:
        result = {"error": getattr(error, "code", type(error).__name__), "detail": str(error)}
        print(json.dumps(result, ensure_ascii=True) if args.json else "Stopped" + f" ({result['error']}). {result['detail']}")
        return 1
