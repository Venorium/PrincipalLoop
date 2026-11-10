# Contributing to PrincipalLoop

Thanks for your interest. PrincipalLoop is a small research project with a strict rule: **every claim must be backed by something that was executed and observed**. Contributions that keep that rule are welcome, including negative results.

## Set up

```bash
git clone https://github.com/Venorium/PrincipalLoop
cd PrincipalLoop
uv sync --locked
uv run python -m principalloop doctor     # CPython 3.13 with a patched SQLite
uv run python -m pytest -q
uv run python scripts/validate_preparation.py
```

On Windows without uv, `powershell -NoProfile -File scripts/bootstrap.ps1` builds the pinned environment in `.venv`. The published evidence uses Python 3.13.16 and uv 0.12.23; later 3.13 patch releases are accepted when their SQLite carries the WAL fix.

To exercise the real Codex integration (plugin install, App Server, MCP) without any model call:

```bash
uv run python scripts/qualify_codex.py --output .tools/codex.json
```

## Good first contributions

- Run the test suite and `principalloop demo` on macOS and report what happens.
- Add a report language: the English and French tables live in `src/principalloop/snapshot/i18n.py` and `demo.py`.
- Try the plugin on a real resume and open an issue describing whether the diff helped, misled or added noise.
- Add a scenario to the demo that shows a limit we have not documented.

## Rules that keep the project trustworthy

- **Tests exercise behavior.** New behavior comes with a nominal case, a refusal and, where state is involved, a fault (killed process, lost response, concurrent writer). Tests never call a model.
- **The model never chooses its authority.** No tool argument may select a workspace, a role, a file outside the human's list or a budget. Identity comes from the channel (the directory Codex starts the server in, or Codex's own metadata).
- **An error is never a pass.** Unavailable, refused or unknown outcomes must stay distinguishable from `UNCHANGED` and `NO_CHANGE`.
- **Shipped formats are immutable.** A new SQLite format or contract version comes with a migration, a backup test and a refusal test for the old reader.
- **Keep failures.** Do not edit an oracle, a threshold or a reserved scenario to make a result look better. Failed and interrupted runs are kept and reported.
- **No private state in the repository.** Databases, profiles and reports live outside the working tree; `.codex/config.toml` is ignored because it holds machine paths.

Design documents live in [docs/](docs/); start with the [architecture](docs/ARCHITECTURE.md) and the [backlog](docs/BACKLOG.md). Issues and pull requests are in English.

## Pull requests

Describe the problem, the behavior after the change, how you tested it and what remains unproven. Keep each pull request focused on one change; CI runs the tests on Windows and Linux.
