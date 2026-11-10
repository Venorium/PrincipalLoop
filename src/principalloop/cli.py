"""Command line entry point. No model call and no background service."""

import argparse
from importlib.metadata import version
import json
from pathlib import Path

from .domain.contracts import ContractError, contract_names, validate_contract
from .runtime import diagnose
from .store.cli import add_commands, execute
from .snapshot.cli import add_commands as add_snapshot_commands, execute as execute_snapshot
from .codex.cli import add_commands as add_codex_commands, execute as execute_codex


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="principalloop")
    parser.add_argument("--version", action="version", version=f"principalloop {version('principalloop')}")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Check the loaded runtime and a throwaway SQLite database")
    validator = commands.add_parser("validate", help="Valider la forme d'un contrat JSON")
    validator.add_argument("contract", choices=contract_names())
    validator.add_argument("path", type=Path)
    add_commands(commands)
    add_snapshot_commands(commands)
    add_codex_commands(commands)
    args = parser.parse_args(argv)
    if args.command == "codex":
        return execute_codex(args)
    if args.command in ("demo", "snapshot", "context"):
        return execute_snapshot(args)
    if args.command in ("store", "demo-store"):
        return execute(args)
    if args.command == "doctor":
        report = diagnose()
        print(json.dumps(report, ensure_ascii=True, indent=2))
        # Exit 0 when the kernel may run; "qualified" also requires the reference runtime.
        return 0 if report["admitted"] else 2
    try:
        validate_contract(args.contract, args.path.read_bytes())
    except (ContractError, OSError) as error:
        print(f"INVALID: {error}")
        return 1
    print(f"VALID: {args.contract} (shape only; no authority or evidence established)")
    return 0
