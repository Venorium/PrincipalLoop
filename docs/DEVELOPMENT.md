# Developing PrincipalLoop

PL-01 to PL-04 deliver a local package, a pure state machine and its [transactional storage](STORAGE.md), together with the [snapshots and their explorer](SNAPSHOTS.md). The reference qualification covers **Windows 11 x64, CPython 3.13.16 and SQLite 3.53.1**; the same suite passes on Linux (Debian container, uv and managed CPython 3.13.16) and CI runs both systems.

With uv installed, on any system: `uv sync --locked`, then `uv run python -m pytest -q`. The `.venv/Scripts/python` commands below are equivalent to `uv run python`; on Linux the interpreter is `.venv/bin/python`. The diagnostic reads `sqlite3.sqlite_version` in the tested process. It never infers SQLite from the Python version.

## Reproducible installation

Windows prerequisites: Git, a Python able to create the bootstrap, PowerShell, and access to the public package indexes during the first installation. From the repository root:

```powershell
powershell -NoProfile -File scripts/bootstrap.ps1
.venv/Scripts/python -m pytest -q
.venv/Scripts/python scripts/validate_preparation.py
```

The bootstrap installs uv **0.12.23** in `.tools/bootstrap` and CPython **3.13.16** in `.tools/python`, then syncs `.venv` with `uv.lock`. It adds Python neither to the PATH nor to the registry. The global Python stays independent. `.python-version`, the lock file and the diagnostic pin the reference. The kernel admits any CPython 3.13.x whose SQLite carries the WAL fix (ADR-20); `doctor` reports `admitted`, `reference_runtime` and `qualified` separately.

`pyproject.toml` pins the direct dependencies, `uv.lock` the transitive ones and the digests of the runtime/development distributions. The build uses hatchling 1.32.4; its transitive dependencies are also pinned by the manifest's build constraints. The runtime uses jsonschema, referencing and rfc3339-validator for the contracts; pytest/Hypothesis and PyYAML are development dependencies. No model SDK, server or ORM is installed.

Environments, caches, builds, `.env` files and SQLite databases are excluded by `.gitignore`. `.gitattributes` enforces LF so that contract digests stay stable, even with `core.autocrlf=true` on Windows.

## Available commands

```powershell
.venv/Scripts/python -m principalloop doctor
.venv/Scripts/python -m principalloop validate director-turn examples/contracts/director-turn.json
.venv/Scripts/python -m principalloop validate event examples/contracts/invalid/event.json
.venv/Scripts/python -m principalloop demo-store
.venv/Scripts/python scripts/qualify_package.py --output .tools/qualification-package.json
```

`doctor` returns 0 if the runtime is admitted and 2 otherwise; `qualified` additionally requires the reference version. It creates a disposable database under the system temporary directory: WAL, foreign keys, synchronous FULL, commit, rollback and re-read. No product database is created. `validate` returns 0 for a valid shape, 1 for a contract/read error and 2 for incorrect CLI usage. The counter-example above must return 1.

`qualify_package.py` rebuilds a second disposable environment from the lock file, offline once the cache is filled. It installs a non-editable wheel, checks that the import comes from that environment, and runs the diagnostic, the tests, `demo-store`, the visual report `demo --no-open` and the documentation check from a directory outside the repository. The lock file must stay identical. The report keeps the date, versions/builds, source digests and outputs; it does not replace a new run after a change. The `limits` field is the one from the `doctor` diagnostic only; the PL-03 crash tests run separately in the suite. The [kept report](reports/cx02-package-windows.json) is the one for the published sources.

The schemas in `contracts/` are the only editable source. They are embedded in the package at build time. The cache keys include the Python sources, the schemas and the README. After changing the schemas, sync the data before testing; the following explicit reinstall is also available:

```powershell
.tools/bootstrap/Scripts/uv --cache-dir .tools/cache sync --locked --reinstall-package principalloop
```

The tests compare the installed bytes with the sources and detect a stale package. An incompatible change to the two initial contracts requires a new version.

## Platforms and rollback

Linux was run in a Debian container: uv 0.12.23, managed CPython 3.13.16, `uv sync --locked`, then diagnostic, tests, documentation check and demo. Four tests specific to Windows recovery are skipped. The [GitHub Actions](../.github/workflows/ci.yml) CI repeats these checks on Windows and Linux, and installs the package as a user would with `uv tool install --managed-python`. macOS is not tested.

The PL-01/02 changes have no migration and no persistent state to undo. A rollback restores only the affected files from Git history, after comparing them with more recent changes. Local environments can be recreated without touching the global Python. Never delete an environment, `.git` or a computed directory without checking its path and content.

PL-03 adds storage migration 1. Consistent backup, restoration into another directory and rollback limits are described in [STORAGE.md](STORAGE.md). An older version of the code must not open a database format it does not understand. Never replace an open database or delete its lock to take over.

## Next ticket

[PL-05](BACKLOG.md) builds the budget and the effect registry. `Store.apply` now produces real freshness; the other `Checks` remain trusted facts to be produced by PL-05/06/08. Never turn the simulated attestations of the tests into real verifications.

## Codex context connector

The [Codex guide](CODEX_QUICKSTART.md) covers installation and removal. The protocol and plugin tests need neither Codex nor an API key; they are part of pytest. The script below requires an installed Codex binary: it installs the plugin from this repository into a temporary `CODEX_HOME` and exercises App Server → MCP, without any model call:

```powershell
.venv/Scripts/python scripts/qualify_codex.py --output .tools/qualification-codex.json
```

If several versions are installed, repeat `--codex C:/path/to/codex.exe` for each one; a single report gathers the runs. The script records the version actually launched; never infer the binary's version from another `codex` shim. The schemas can be generated by the same executable with `app-server generate-json-schema --experimental --out .tools/codex-protocol`. App Server remains a surface to requalify whenever the version changes. The [kept evidence](reports/cx02-codex-windows.json) uses CLI 0.166.0 and desktop 0.167 on Windows.

The skill text has a single source, `plugins/principalloop/skills/principalloop/SKILL.md`, copied into the wheel. After editing it, resync the environment (`uv sync --locked`): a test compares the installed copy with the source. The images in `docs/images` and in the plugin are produced from reports that were actually generated.
