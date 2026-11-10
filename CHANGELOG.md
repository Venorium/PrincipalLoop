# Changelog

All notable changes are listed here. The project follows [Semantic Versioning](https://semver.org/); before 1.0, minor versions may change formats with an explicit migration.

## 0.1.0 — first public preview

### Codex plugin

- Installable plugin (`codex plugin marketplace add Venorium/PrincipalLoop`) with an MCP server and a resume skill.
- Four tools: `pl_status`, `pl_checkpoint`, `pl_check` (with a bounded unified diff) and `pl_read`.
- The project is identified by Codex (the chat's working directory or sandbox metadata), never by tool arguments; subdirectories resolve to the enabled project.
- `principalloop codex enable / disable` for human activation, `codex doctor` for a readable diagnosis with exact fixes, `codex report` for a private visual report with captured and current versions side by side.
- Optional project mode (`codex install`) kept for setups without plugins; `codex uninstall --keep-profile` migrates to the plugin.

### Kernel

- Versioned JSON contracts and a pure state machine for proposals, decisions and plans.
- SQLite journal with atomic event, projection and outbox writes, a single-writer lock, backups and migrations 1 to 2.
- Immutable snapshots with double reads, recorded reads, evidence bound to captured bytes and freshness checks at every transition.
- Runtime admission: CPython 3.13.x with a SQLite that carries the WAL-reset fix; the exact reference runtime stays reported.

### Visual reports

- Standalone offline HTML explorer with eight executed scenarios, in English by default and in French with `--lang fr`.

### Evidence

- Tests on Windows and Linux; real Codex qualification with Codex CLI 0.166.0 and the 0.167 desktop build, without model turns. See [VALIDATION.md](VALIDATION.md).
