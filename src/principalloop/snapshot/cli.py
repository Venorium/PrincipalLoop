"""Human journey: visual report by default, JSON only on request."""

import json
from pathlib import Path
import sqlite3
from uuid import uuid4
import webbrowser

from ..domain.types import Principal, Role
from ..store import Reader, Store, StoreError
from ..store.paths import default_state_dir, private_path
from .demo import inspection, run_demo
from .i18n import LANGS, TEXT, default_lang
from .report import write_report
from .types import Document, KINDS


def add_commands(commands):
    demo = commands.add_parser("demo", help="Open the visual explorer: eight real freshness scenarios, no model")
    demo.add_argument("--output", type=Path, help="New synthetic HTML report to keep")
    demo.add_argument("--no-open", action="store_true", help="Generate the report without opening the browser")
    demo.add_argument("--json", action="store_true", help="Optional machine-readable summary")
    demo.add_argument("--lang", choices=LANGS, help="Report language (default: English)")
    for group, names in (("snapshot", ("capture", "list", "inspect")), ("context", ("put", "list", "required"))):
        parent = commands.add_parser(group, help="Capture and inspect context" if group == "snapshot" else "Describe premises and their dependencies")
        actions = parent.add_subparsers(dest="snapshot_action", required=True)
        for name in names:
            action = actions.add_parser(name)
            action.add_argument("--workspace", type=Path, default=Path.cwd())
            action.add_argument("--state-dir", type=Path)
            action.add_argument("--json", action="store_true")
            if name in ("capture", "put", "required"):
                action.add_argument("--event-id", default=None, help="Identity to reuse when retrying after a lost response")
            if name == "capture":
                action.add_argument("--file", action="append", default=[], help="Explicit relative path; repeatable, no implicit scan")
                action.add_argument("--object", action="append", default=[], help="Premise ID; repeatable")
            if name == "inspect":
                action.add_argument("snapshot_id", nargs="?", default="latest")
            if name in ("capture", "inspect"):
                action.add_argument("--output", type=Path)
                action.add_argument("--lang", choices=LANGS, help="Report language (default: English)")
                action.add_argument("--no-open", action="store_true")
            if name == "put":
                action.add_argument("--id", required=True)
                action.add_argument("--kind", choices=sorted(KINDS), default="HYPOTHESIS")
                action.add_argument("--title", required=True)
                action.add_argument("--text", required=True)
                action.add_argument("--depends-on", action="append", default=[])
                action.add_argument("--expected-revision", type=int, default=0)
            if name == "required":
                action.add_argument("--object", action="append", default=[])
                action.add_argument("--expected-revision", type=int, required=True)


def _report_for_snapshot(store, sid, lang="en"):
    text = TEXT[lang]
    data = inspection(store, sid, lang)
    manifest = data["snapshot"]["manifest"]
    return {"kind": "snapshot", "lang": lang, "title": text["snap_title"], "subtitle": text["snap_subtitle"],
            "scenarios": [{"id": "capture", "title": text["snap_case"], "subtitle": manifest["snapshot_id"][:18] + "…",
                           "explanation": text["snap_explanation"],
                           "limit": False, "validation": {"eligible": None, "stability": manifest["stability"], "dependencies": [],
                           "issues": [{"message": message, "reference_id": None} for message in data["snapshot"]["details"]["issues"]]}, **data}],
            "limits": text["snap_limits"]}


def execute(args):
    committed_capture = None
    try:
        if args.command == "demo":
            lang = args.lang or default_lang()
            data = run_demo(lang)
            path = args.output or default_state_dir(Path.cwd()) / "reports" / f"demo-{uuid4().hex}.html"
            report = write_report(data, path)
            result = {"passed": data["all_expected_results_observed"], "scenarios": len(data["scenarios"]), "report": str(report)}
            message = f"PrincipalLoop: {result['scenarios']} scenarios executed, every expected result observed.\nVisual report: {report}"
        else:
            workspace = args.workspace.resolve(strict=True)
            directory = args.state_dir or default_state_dir(workspace)
            action = args.snapshot_action
            if args.command == "snapshot" and action in ("capture", "inspect"):
                path = private_path(args.output or directory / "reports" / f"snapshot-{uuid4().hex}.html", workspace)
                if path.exists():
                    raise FileExistsError("The report already exists; choose a new path.")
            access = Store if action in ("capture", "put", "required") else Reader
            with access(directory / "control.sqlite3", workspace=workspace) as store:
                human = Principal("local-human", Role.HUMAN, store.plan().project_id)
                event_id = getattr(args, "event_id", None) or "CMD-" + uuid4().hex
                report = None
                if args.command == "context":
                    if action == "put":
                        document = Document(args.id, args.kind, args.title, args.text, tuple(("depends_on", item) for item in args.depends_on))
                        store.snapshots.put_object(document, human, expected_revision=args.expected_revision, event_id=event_id)
                        result = store.snapshots.objects()[args.id]
                        message = f"Premise saved: {args.id}, revision {result['revision']}.\nCommand identity: {event_id}"
                    elif action == "required":
                        store.snapshots.set_required(args.object, human, expected_revision=args.expected_revision, event_id=event_id)
                        result = store.snapshots.policy()
                        message = f"Mandatory dependencies: {len(result['object_ids'])}, revision {result['revision']}.\nCommand identity: {event_id}"
                    else:
                        result = list(store.snapshots.objects().values())
                        message = "\n".join(f"{item['object_id']} | r{item['revision']} | {item['title']}" for item in result) or "No premise yet. Use context put to add one."
                elif action == "list":
                    result = store.snapshots.list()
                    message = "\n".join(f"{item['snapshot_id']} | {item['stability']} | {len(item['artifact_manifest'])} file(s)" for item in result) or "No snapshot yet. Use snapshot capture --file relative/path."
                else:
                    if action == "capture":
                        if len(set(args.file)) != len(args.file):
                            raise StoreError("DUPLICATE_REFERENCE", "A file was selected twice")
                        snapshot = store.snapshots.capture({"artifact:" + path: path for path in args.file}, args.object, human, event_id=event_id)
                        sid = snapshot["manifest"]["snapshot_id"]
                        committed_capture = {"snapshot_id": sid, "event_id": event_id}
                    else:
                        snapshots = store.snapshots.list()
                        if not snapshots:
                            raise StoreError("UNKNOWN_SNAPSHOT", "No snapshot exists; capture selected files first")
                        sid = snapshots[0]["snapshot_id"] if args.snapshot_id == "latest" else args.snapshot_id
                        snapshot = store.snapshots.get(sid)
                    report = write_report(_report_for_snapshot(store, sid, args.lang or default_lang()), path)
                    result = {"snapshot": snapshot["manifest"], "report": str(report), "event_id": event_id if action == "capture" else None}
                    label = "stable across both reads" if snapshot["manifest"]["stability"] == "STABLE" else "UNSTABLE: capture again before any activation"
                    message = f"Snapshot saved: {label}.\n{sid}\nVisual report: {report}"
                    if action == "capture":
                        message += f"\nCommand identity: {event_id}"
        print(json.dumps(result, ensure_ascii=True) if args.json else message)
        if report is not None and not args.no_open:
            if not webbrowser.open(report.as_uri()):
                print("The browser was not opened. The report is available at the path above.")
        return 0
    except (StoreError, ValueError, OSError, sqlite3.Error) as error:
        code = getattr(error, "code", type(error).__name__)
        detail = str(error)
        if getattr(args, "json", False):
            print(json.dumps({"error": code, "detail": detail, "committed_capture": committed_capture}, ensure_ascii=True))
        else:
            print(f"Stopped ({code}). {detail}")
            if committed_capture:
                print(f"Capture {committed_capture['snapshot_id']} is kept (command {committed_capture['event_id']}). Use snapshot inspect to regenerate its report.")
        return 1
