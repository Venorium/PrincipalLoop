# Storage and local workflow — PL-03

Delivered on 4 October 2026, qualified on Windows x64. PL-03 persists the mission, proposals, decision/plan transitions, observations and outgoing messages. It provides a journal usable from the CLI and an internal API for the future kernel. The [PL-04 snapshots](SNAPSHOTS.md) are now available; decision delivery and the director are still to be built. See the [evidence](../VALIDATION.md) and the [planned Codex path](CODEX_INTEGRATION.md).

## Try it now, no configuration

From the project root after [installation](DEVELOPMENT.md):

```powershell
.venv/Scripts/python -m principalloop demo-store
```

The demo creates a disposable workspace and database outside the repository. It initializes a synthetic mission, records an observation, replays the same ID, refuses contradictory content, then reopens the database. `passed: true` means these six local checks succeeded. No model, monitoring or evidence of strategic utility is involved.

## Keeping a work journal

The following path uses the provided synthetic examples. The ID `principal-loop-demo` belongs to these examples; for a real project, write and validate your own mission before initialization.

```powershell
.venv/Scripts/python -m principalloop store init --mission examples/contracts/mission.json
.venv/Scripts/python -m principalloop store observe --event examples/contracts/event.json --run-id codex-principal-1
.venv/Scripts/python -m principalloop store status
.venv/Scripts/python -m principalloop store journal --after 0 --limit 100
.venv/Scripts/python -m principalloop store outbox --after 0 --limit 100
```

The JSON returned after a write contains `event_seq`, `event_id` and `duplicate`. Replaying `observe` with the same data and the same `run-id` returns the initial sequence and `duplicate: true`. Changing the content under the same identity produces `ID_CONFLICT`, exit code 1. A new observation needs a new ID. A lost response calls for an identical retry, never for the automatic generation of a new ID.

Every `store` command accepts `--workspace <existing directory>` and `--state-dir <private directory>`. By default the workspace is the current directory and the database lives in `%LOCALAPPDATA%/PrincipalLoop/state/<workspace-path-digest>/control.sqlite3`. Use the same workspace on every call, even from another directory. An initialized database refuses another workspace or another project. Moving the workspace is not a supported migration.

`status` shows the mode, the plan generation, the owner if any, the current observations and the number of kept messages. `snapshot: AVAILABLE` and `snapshot_count` show the availability of the PL-04 captures. `director: NOT_CONNECTED` and `outbox_delivery: NOT_IMPLEMENTED` show the missing functions. A `CHECKPOINT_AVAILABLE` observation remains a producer's declaration; it proves neither a stable capture nor a safe point.

The CLI is a trusted local tool: `init` represents the human operator, `observe` the `local-cli` executor in the given run. These identities are not network authentication and do not protect against another program running under the same account. The CLI offers no `--role` argument, no activation command and no mission editing. Exit codes: 0 success or identical duplicate, 1 refusal/error, 2 incorrect CLI syntax.

## Guarantees and boundaries

The central invariant is: **every acknowledged event has its state and its outgoing message in the same commit**. If the process disappears before the commit, none of these writes is visible. If it disappears after the commit but before the acknowledgement is received, the retry finds the commit. Reversing this rule — acknowledging before the commit — would allow an observation to be announced and then lost.

| Element | Delivered guarantee | Limit |
|---|---|---|
| Journal | Increasing SQLite `event_seq`; content and provenance kept; UPDATE/DELETE refused by triggers | Sequence = admission order, not the real order of facts nor a general invalidation |
| Identity | UNIQUE `(project_id, producer_key, event_id)` in the database | `producer_key` is the canonical actor/run pair supplied by the trusted context |
| Duplicate | Comparison of the canonical JSON and its SHA-256, including operation and role | No semantic comparison of two different narratives |
| Transaction | `BEGIN IMMEDIATE`, journal + state + outbox, then COMMIT, then receipt | No model call, external tool or publication inside this transaction |
| Decision/plan | Loaded inside the transaction; `advance()` applies the guards; joint state recorded | The real `Checks` attestations remain to be produced in PL-04/05/06 |
| Activation | UNIQUE per proposal and per epoch/project; retrying a committed command creates no new activation | This is not yet the coordination of a real tool or safe point |
| Writer | OS lock held for the lifetime of `Store`; a second `Store` is refused | Every writer must use this API; direct SQL access from the same account is outside the guarantee |
| Outbox | One durable message per event, stable identifier `O-<event_seq>` | No transport or delivery acknowledgement yet; PL-06/09 |

The canonical format sorts keys, preserves lists and encodes strings as ASCII JSON; no Unicode normalization and no additional numeric equivalence. The clock is injectable and timestamps are kept; only the kernel sequence orders admission. The journal keeps the **accepted** commands and the attestations used. Refusals are returned to the caller but do not yet have a durable incident journal.

`Reader` opens the existing database read-only; its status uses a consistent read transaction. `Store` is reserved for one thread and one process. The `.writer.lock` lock must never be deleted to unblock a writer: identify and stop its owner. The OS releases the lock after the owner dies; the file, which carries no business meaning, may remain. No PID assumed alive, no lease and no fencing in this ticket.

## Internal API

The entry points are in [store/](../src/principalloop/store/):

| Call | Use |
|---|---|
| `Store.initialize(mission, principal, event_id=..., mode=...)` | Authorized initial mission; SHADOW by default, COOPERATIVE for the local harness; ENFORCED refused |
| `Store.record_event(event, principal)` | Validated observation, projection of the latest event per producer and notification |
| `Store.register_proposal(proposal, principal, event_id=...)` | Full immutable proposal and initial decision state |
| `Store.apply(proposal_id, command, principal, event_id=..., checks=...)` | Domain mutation on the current state, with a journal of results and attestations |
| `Reader.status/mission/plan/decision/proposal/journal/outbox` | Reads without write ownership; journal/outbox cursors of 1 to 1,000 items |
| `Reader.backup(target)` | Consistent backup into a new private file |

External JSON never builds a `Principal` or `Checks`. Guards default to false. An observation containing an imperative remains an observation. The test examples that build `Checks(...=True)` are simulated attestations; they must not become a production adapter. Saving a result's references does not prove that its artifact exists; keeping and integrating old results remains PL-06.

## Schema, migration and rollback

**Storage format 1** is independent of the **0.1** JSON contracts. The initial migration creates `projects`, `mission_revisions`, `events`, `producer_views`, `decisions`, `activations`, `outbox` and `schema_migrations`. `application_id` identifies PrincipalLoop; `user_version` and the DDL digest identify the migration. A foreign database, a future one or one with an incompatible digest is refused. The digest detects a migration divergence, not a hostile alteration of the file by an administrator.

The migration uses transactional DDL. An exception or the death of the process before its commit leaves a database without a schema, which can be reopened for a new attempt. Any change after delivery adds a migration; never rewrite version 1. The plan/decision values also have a version envelope and an exact set of fields; an unknown value fails explicitly.

Before a future version upgrade:

```powershell
.venv/Scripts/python -m principalloop store backup --output "$env:LOCALAPPDATA/PrincipalLoop/backups/before-next-migration.sqlite3"
```

Choose a new name for every backup; an existing file is refused. The [SQLite Backup API exposed by Python](https://docs.python.org/3.13/library/sqlite3.html#sqlite3.Connection.backup) copies a consistent state, including pages present in the WAL. The integrity check runs on the copy; the operation is bounded to 15 seconds. Never copy only the main file of an open WAL database.

To return to an earlier version: stop the writers, keep the failed directory intact, place the backup in **a new private directory** under the name `control.sqlite3`, then use `--state-dir` with the compatible software and check status/journal before resuming. This restoration abandons the events recorded after the backup: they remain to be reconciled in the kept database. No destructive downgrade or automatic overwrite is provided. The backup test actually reopens a copy and finds its original receipt; PL-07 will handle replay and later migrations.

## Support and privacy

The runtime checks the reference Python and a patched SQLite, then verifies WAL, foreign_keys ON and synchronous FULL. The [SQLite WAL](https://www.sqlite.org/wal.html) documentation requires processes on the same machine; network paths are refused. Windows requires a fixed local volume here. State inside the workspace or under known OneDrive roots is refused, including after link resolution; files with several hard links are refused. These checks do not detect every synchronization tool.

On Windows, permissions are inherited from the user directory; there is no PrincipalLoop-specific encryption and no isolation against the same account. On POSIX, new directories/files request 0700/0600; Linux is exercised in a container and in CI, without a dedicated qualification report. Backups, CLI outputs and observations may contain sensitive data: they are not meant for a public repository.

The tests cover commit boundaries with `os._exit`, forced termination of the owner, refusals and restoration. They simulate neither power loss, hardware corruption nor every publication failure. No performance measurement is claimed.

## PL-04 evolution: storage format 2

The current code opens format 2. It adds documentary revisions, immutable captures and BLOBs, read sessions, mandatory dependencies and verifier evidence. Migration 1 stays intact. Any v1 database is backed up consistently before migration; receipts, journal and outbox keep their identities. The [PL-04 procedure](SNAPSHOTS.md) covers recovery and rollback without a downward migration. The format 1 descriptions above document the PL-03 base.

On Windows, reopening after a forced kill sometimes returned `SQLITE_IOERR_TRUNCATE`. Opening the owner makes at most three attempts for this error only, before any migration or command (waits of 50 then 100 ms). Other errors are raised immediately; this mechanism never repeats a commit or an effect. The exact system cause has not been established.
