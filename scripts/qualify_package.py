"""Rebuild outside .venv from uv.lock, then test the installed wheel outside the repository.

Run with the project interpreter (.venv/Scripts/python on Windows) after the environment
is built. Uses the filled cache; calls no model and creates no product state.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from principalloop.runtime import diagnose


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, *, cwd, env):
    result = subprocess.run([str(arg) for arg in args], cwd=cwd, env=env, capture_output=True,
                            text=True, encoding="utf-8", timeout=120)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}): {result.stdout}\n{result.stderr}")
    return result.stdout.strip()


def qualify():
    report = diagnose()
    report["limits_scope"] = "The limits field describes doctor only; process-crash tests belong to the test suite."
    report["qualified_at_utc"] = datetime.now(timezone.utc).isoformat()
    if not report["qualified"]:
        raise RuntimeError("Primary runtime not qualified")
    uv = ROOT / ".tools/bootstrap" / ("Scripts/uv.exe" if os.name == "nt" else "bin/uv")
    report["uv"] = run([uv, "--version"], cwd=ROOT, env=os.environ.copy())
    lock = ROOT / "uv.lock"
    before = digest(lock)
    with tempfile.TemporaryDirectory(prefix="principalloop-wheel-") as folder:
        target = Path(folder).resolve()
        if not target.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise RuntimeError("Temporary directory escaped expected root")
        environment = target / "environment"
        env = os.environ.copy()
        env["UV_PROJECT_ENVIRONMENT"] = str(environment)
        env["PYTHONUTF8"] = "1"
        run([uv, "--cache-dir", ROOT / ".tools/cache", "sync", "--offline", "--locked", "--no-editable",
             "--no-python-downloads", "--project", ROOT, "--python", sys.executable], cwd=target, env=env)
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        location = run([python, "-c", "import principalloop; print(principalloop.__file__)"], cwd=target, env=env)
        if not Path(location).resolve().is_relative_to(environment.resolve()):
            raise RuntimeError("Import did not come from the newly installed wheel")
        fresh_doctor = json.loads(run([python, "-m", "principalloop", "doctor"], cwd=target, env=env))
        report["fresh_install_qualified"] = fresh_doctor["qualified"]
        report["non_editable_import_outside_repository"] = True
        report["tests"] = run([python, "-m", "pytest", ROOT / "tests", "-q"], cwd=target, env=env)
        report["store_demo"] = json.loads(run([python, "-m", "principalloop", "demo-store"], cwd=target, env=env))
        if not report["store_demo"]["passed"]:
            raise RuntimeError("Installed storage demonstration failed")
        visual = json.loads(run([python, "-m", "principalloop", "demo", "--no-open", "--json", "--output", target / "demo.html"], cwd=target, env=env))
        if not visual["passed"] or visual["scenarios"] != 8 or not (target / "demo.html").is_file():
            raise RuntimeError("Installed visual snapshot demonstration failed")
        report["snapshot_demo"] = {"passed": visual["passed"], "scenarios": visual["scenarios"], "html_generated": True}
        report["preparation"] = run([python, ROOT / "scripts/validate_preparation.py"], cwd=target, env=env)
    report["lock_sha256"] = before
    report["lock_unchanged"] = digest(lock) == before
    paths = sorted([*ROOT.glob("src/**/*.py"), *ROOT.glob("contracts/*.json"), *ROOT.glob("examples/**/*.json"),
                    *ROOT.glob("tests/*.py"), *ROOT.glob("plugins/principalloop/**/*.json"), *ROOT.glob("plugins/principalloop/.*/*.json"),
                    ROOT / "plugins/principalloop/.mcp.json", ROOT / "plugins/principalloop/skills/principalloop/SKILL.md",
                    ROOT / ".agents/plugins/marketplace.json", *ROOT.glob(".github/workflows/*.yml"), ROOT / "pyproject.toml", ROOT / "scripts/qualify_package.py",
                    ROOT / "scripts/bootstrap.ps1", ROOT / "scripts/validate_preparation.py", ROOT / "scripts/qualify_codex.py",
                    ROOT / ".gitattributes", ROOT / ".python-version"])
    report["source_sha256"] = {path.relative_to(ROOT).as_posix(): digest(path) for path in paths}
    if not report["lock_unchanged"]:
        raise RuntimeError("Qualification modified lock file")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="Local JSON report to keep")
    args = parser.parse_args()
    report = qualify()
    rendered = json.dumps(report, ensure_ascii=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered)


if __name__ == "__main__":
    main()
