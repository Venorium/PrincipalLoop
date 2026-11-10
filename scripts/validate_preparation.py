"""Structural checks of the documentation, contracts and examples. Not a product test."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import re
import sqlite3
import sys


# Fingerprint of the published v0.1 specification; any edit must be deliberate.
SPEC_SHA256 = "56eb037fb208338d6d3779a5cfcc675ddded5b8f968f13f18f02321962ec5eda"
ROOT_DOCS = ("README.md", "SPECIFICATION.md", "VALIDATION.md", "CONTRIBUTING.md", "SECURITY.md", "CHANGELOG.md")
DOCS = ("ANALYSIS", "ARCHITECTURE", "EXPERIMENTATION", "BACKLOG", "TRACEABILITY", "DECISIONS", "SOURCES", "CONTRACTS",
        "DEVELOPMENT", "STORAGE", "CODEX_INTEGRATION", "SNAPSHOTS", "CODEX_QUICKSTART")


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)


def changed(document, path, value, *, remove=False):
    result = deepcopy(document)
    parent = result
    for part in path[:-1]:
        parent = parent[part]
    if remove:
        del parent[path[-1]]
    else:
        parent[path[-1]] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    root = parser.parse_args().root.resolve()
    try:
        from jsonschema import Draft202012Validator, FormatChecker
        import yaml
    except ImportError as exc:
        print(f"Missing dependency: {exc}. Run uv sync --locked.")
        return 2

    passed = 0
    failed = []
    limitations = []

    def check(label, condition):
        nonlocal passed
        if condition:
            passed += 1
        else:
            failed.append(label)

    required = [root / name for name in ROOT_DOCS]
    required += [root / "docs" / f"{name}.md" for name in DOCS]
    required += [root / ".gitignore", root / "scripts" / "validate_preparation.py"]
    required += [root / "contracts" / f"decision-{name}.schema.json" for name in ("proposal", "response")]
    required += [root / "examples" / f"decision-{name}.json" for name in ("proposal", "response")]
    required += [root / "examples" / "README.md", root / "examples" / "project.config.example.yaml"]
    required += [root / "prompts" / f"{name}.md" for name in ("DIRECTOR", "EXECUTOR")]
    check("Every expected file exists", all(path.is_file() for path in required))
    if failed:
        for path in required:
            if not path.is_file():
                print(f"MISSING: {path.relative_to(root)}")
        return 1

    texts = {}
    for path in required:
        try:
            content = path.read_text(encoding="utf-8")
            check(f"UTF-8 without replacement characters: {path.name}", "\ufffd" not in content)
            texts[path] = content
        except UnicodeError:
            failed.append(f"Invalid UTF-8: {path.name}")
    if failed:
        print("\n".join(failed))
        return 1

    check("Specification v0.1 unchanged byte for byte", hashlib.sha256((root / "SPECIFICATION.md").read_bytes()).hexdigest() == SPEC_SHA256)
    for path, content in texts.items():
        if path.suffix != ".md":
            continue
        # Plain Markdown links outside code blocks; no URL is visited.
        prose = re.sub(r"```.*?```", "", content, flags=re.S)
        for target in re.findall(r"\[[^\]\n]+\]\(([^)\n]+)\)", prose):
            if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target) or target.startswith("#"):
                continue
            local = target.split("#", 1)[0]
            dest = (path.parent / local).resolve()
            check(f"Local link: {path.relative_to(root)} -> {target}", dest.is_relative_to(root) and dest.exists())

    trace = texts[root / "docs" / "TRACEABILITY.md"]
    for prefix, count in (("F", 14), ("I", 12), ("N", 8), ("T", 24), ("X", 10)):
        rows = re.findall(rf"^\| ({prefix}-\d{{2}})\b[^|]*\|", trace, flags=re.M)
        expected = {f"{prefix}-{i:02d}" for i in range(1, count + 1)}
        check(f"Traceability {prefix} complete, without duplicates", set(rows) == expected and len(rows) == count)
    backlog = texts[root / "docs" / "BACKLOG.md"]
    tickets = re.findall(r"^## (PL-\d{2})\b", backlog, flags=re.M)
    check("14 detailed tickets without duplicates", set(tickets) == {f"PL-{i:02d}" for i in range(1, 15)} and len(tickets) == 14)
    dependency_rows = re.findall(r"^\| (PL-\d{2}) \| [^|]+ \| ([^|]+) \|", backlog, flags=re.M)
    dependencies = {ticket: re.findall(r"PL-\d{2}", deps) for ticket, deps in dependency_rows}
    known = set(dependencies) == set(tickets) and all(dep in dependencies for deps in dependencies.values() for dep in deps)
    check("Dependencies: known tickets and complete table", known and len(dependency_rows) == len(tickets))

    visited, visiting = set(), set()

    def acyclic(ticket):
        if ticket in visiting:
            return False
        if ticket in visited:
            return True
        visiting.add(ticket)
        if not all(acyclic(dep) for dep in dependencies[ticket]):
            return False
        visiting.remove(ticket)
        visited.add(ticket)
        return True

    check("Dependencies: no cycle", known and all(acyclic(ticket) for ticket in dependencies))
    spec = texts[root / "SPECIFICATION.md"]
    check("Seven specification references present", set(re.findall(r"^\[(S\d+)\]", spec, flags=re.M)) == {f"S{i}" for i in range(1, 8)})

    checker = FormatChecker()
    check("date-time format check actually active", not checker.conforms("not-a-date", "date-time"))
    validators = {}
    instances = {}
    for name in ("proposal", "response"):
        schema = read_json(root / "contracts" / f"decision-{name}.schema.json")
        Draft202012Validator.check_schema(schema)
        check(f"Meta-schema {name}", True)
        validators[name] = Draft202012Validator(schema, format_checker=checker)
        instances[name] = read_json(root / "examples" / f"decision-{name}.json")
        check(f"Example {name} conforms", validators[name].is_valid(instances[name]))

    proposal = instances["proposal"]
    negatives = [
        ("negative budget", "proposal", ("budget_request", "additional_tokens"), -1, False),
        ("no evidence", "proposal", ("evidence_ids",), [], False),
        ("missing snapshot", "proposal", ("basis_snapshot_id",), None, True),
        ("added authority field", "proposal", ("admin",), True, False),
        ("invalid date", "proposal", ("activation", "expires_at"), "not-a-date", False),
        ("NO_CHANGE used as a proposal", "proposal", ("kind",), "NO_CHANGE", False),
        ("empty read_set", "proposal", ("read_set",), [], False),
        ("DEFER without trigger", "response", ("resume_trigger",), None, False),
        ("DEFER without deadline", "response", ("defer_until",), None, False),
        ("DEFER invalid date", "response", ("defer_until",), "not-a-date", False),
        ("zero revision", "response", ("expected_decision_revision",), 0, False),
    ]
    for label, name, path, value, remove in negatives:
        candidate = changed(instances[name], path, value, remove=remove)
        check(f"Refused: {label}", not validators[name].is_valid(candidate))
    outside = changed(proposal, ("proposed_action", "scope_delta"), "REQUEST_HUMAN_SCOPE_CHANGE")
    check("Refused: scope extension without a human request", not validators["proposal"].is_valid(outside))
    outside["authority_requested"] = "HUMAN_APPROVAL"
    check("Human request syntactically admissible", validators["proposal"].is_valid(outside))

    # Characterize the current limits; never present them as guarantees.
    probes = [
        ("a duplicated read_set", changed(proposal, ("read_set",), proposal["read_set"] * 2)),
        ("nonexistent evidence", changed(proposal, ("evidence_ids",), ["E-NONEXISTENT"])),
        ("a past deadline", changed(proposal, ("activation", "expires_at"), "2000-01-01T00:00:00Z")),
    ]
    for label, candidate in probes:
        if validators["proposal"].is_valid(candidate):
            limitations.append(f"The schema accepts {label}; it validates neither provenance nor current state.")

    config = yaml.safe_load(texts[root / "examples" / "project.config.example.yaml"])
    check("YAML configuration parses as an object", isinstance(config, dict))
    check("Configuration example in SHADOW mode", isinstance(config, dict) and config.get("mode") == "SHADOW")
    check("Business test namespace distinct from T-17", proposal["verification"]["check_ids"] == ["ORD-IDEMPOTENCY-01"] and "test T-17" not in proposal["rationale"]["observation"])

    print(f"Documentation checks: {passed} passed, {len(failed)} failed.")
    print(f"Environment: Python {sys.version.split()[0]}, SQLite {sqlite3.sqlite_version}, jsonschema {version('jsonschema')}, PyYAML {version('PyYAML')}.")
    for label in failed:
        print(f"FAILED: {label}")
    for limitation in limitations:
        print(f"LIMIT: {limitation}")
    print("These checks validate neither the kernel, a runner, recovery nor strategic usefulness.")
    return 1 if failed else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        sys.exit(main())
    except (ValueError, OSError) as exc:
        print(f"FAILED to read or parse: {exc}")
        sys.exit(1)
