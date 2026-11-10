# Build backlog

Status: November 10, 2026. **PL-01 to PL-04 are done within their scope**: Windows x64 qualification, Linux execution, domain, storage and snapshots without a model. The integration slices CX-01 and CX-02 deliver the Codex context plugin. PL-05 to PL-14 remain **TO DO**. Evidence and limits are in [VALIDATION.md](../VALIDATION.md). Dependencies are start conditions, not tasks to run in parallel by default.

## Order and exit gates

| Ticket | Result | Dependencies | Specification batch |
|---|---|---|---|
| PL-01 | Reproducible product environment | None | 1 |
| PL-02 | Executable domain, contracts and transitions | PL-01 | 1 |
| PL-03 | Persistent journal and transactions | PL-02 | 1 |
| PL-04 | Snapshots and dependency validation | PL-03 | 1 |
| PL-05 | Budget and effect ledger | PL-03 | 1 |
| PL-06 | Mailbox, responses and single activation | PL-04, PL-05 | 1 |
| PL-07 | Recovery, replay and fault tests | PL-06 | 1 |
| PL-08 | Deterministic demonstrator and business oracle | PL-07 | 1 |
| PL-09 | Two processes and rebuildable projections | PL-08 | 2 |
| PL-10 | Triggers and bounded cadence | PL-09 | 3 |
| PL-11 | Configurable director, SHADOW first | PL-10 | 3 |
| PL-12 | One real connector and its capability report | PL-11 | 4 |
| PL-13 | A/B/C/D campaigns and report | PL-12 | 5 |
| PL-14 | Protection of real effects, optional | PL-12 and a decision after PL-13 | 6 |

G1 covers PL-01 to PL-10 and the applicable acceptance suite; G2 adds PL-11 and PL-12. Gates and P1/P2/P3 are defined in [EXPERIMENTATION.md](EXPERIMENTATION.md). Fixture design and the experiment registry may start in PL-08; reserved runs wait for the PL-13 prerequisites.

## PL-01 — Reproducible environment

**Status: DONE — Windows x64.** CPython 3.13.16 loads SQLite 3.53.1. Local Git, manifest and lock, bootstrap, diagnosis and rebuild outside the repository are delivered. Procedure: [DEVELOPMENT.md](DEVELOPMENT.md). Linux was exercised later in a container and in CI (CX-02).

**Scope:** local Git tracking, isolated environment, dependency manifest, lock, check commands and installation documentation. Reference: CPython 3.13.16, with a check of the SQLite library actually loaded.

**Acceptance:** repeatable installation from the manifest; versions displayed; a check that refuses an unpatched SQLite library; importable project; a package test runs without an API key. Do not qualify Linux from a Windows run alone. No runtime dependency without immediate use.

**Deliverable:** minimal package, diagnosis command, dependency lock and rebuild procedure. No implicit remote, publication or provider.

## PL-02 — Domain and contracts

**Status: DONE — pure domain.** Nine contracts including the two unchanged v0.1 ones, explicit transitions, examples and behavior tests. Kernel attestations are injected; no transaction, OS authentication or real integration is simulated as achieved. Delivered contract: [CONTRACTS.md](CONTRACTS.md).

**Scope:** `domain/`, missing schemas, state types, injected clock and valid/invalid examples. Preserve the v0.1 contracts; add a version for any incompatibility. Resolve Q-02 and Q-03.

**Acceptance:** explicit allowed and forbidden transitions; ACCEPT distinct from ACTIVE; a receipt has no business effect; terminal states never reopen; a pause never permanently blocks RESUME; ESCALATE creates no automatic epoch. `NO_CHANGE` without a proposal accepted, a contradictory output refused. The client's role never comes from a free field. T-14 and T-24 exercised with injected hostile or malformed outputs, without calling a model.

**Deliverable:** pure functions, tested transition table and documented contracts; no external API. Covers F-01, F-08 and I-02 to I-04.

## PL-03 — Journal and storage

**Status: DONE — Windows x64.** Migration 1, controlled writer, immutable missions and proposals, decision and plan transitions, atomic journal and outbox. T-01 and T-02 exercised; a second process refused, forced kills at commit boundaries and receipt recovery tested. CLI and backup/restore available: [STORAGE.md](STORAGE.md). External delivery, full replay and real attestations belong to later tickets.

**Scope:** `store/`, first migration, identities, journal and outbox. Private state on a local disk; one controlled write owner.

**Acceptance:** T-01/T-02; commit before acknowledgment; atomic event, view and outbox; a restart keeps the acknowledged event; a second concurrent kernel refused or arbitrated; uniqueness enforced in the database. Migration tested on a throwaway database with a documented rollback.

**Deliverable:** persistent storage and transaction tests. No model call or external publication inside a transaction.

## PL-04 — Snapshots and freshness

**Status: DONE — Windows x64.** Revisioned objects, bounded immutable captures, read sessions, evidence bound to bytes and revalidation at transitions are delivered. Migration 2 with a prior backup and tested recovery. The [visual walkthrough](SNAPSHOTS.md) opens eight real scenarios without a model and supports private captures. T-05, T-06, T-19 and X-01 are exercised locally; neither a file-system freeze nor a real connector is claimed.

**Scope:** `snapshot/`, object revisions, relations, immutable artifacts and read validation.

**Acceptance:** T-05/T-06/T-19; an unstable capture refused for the dependent activation; evidence bound to the tested content; duplicate IDs in `read_set` rejected; served reads and mandatory dependencies taken into account; omission case X-01 documenting the remaining limit.

**Deliverable:** reproducible manifest, authorized read APIs and readable invalidation causes. A replaced hypothesis makes its dependents "to be reviewed", not automatically false.

## PL-05 — Budget and effects

**Next slice.** Keep the reproducible walkthrough and present reservations, unknown costs, refusals and recoveries in readable form, with concrete situations.

**Scope:** `budget_ledger`, `effect_ledger`, reservations, action identifiers and admission rules.

**Acceptance:** concurrent reservations without over-allocation; an unknown cost is not released; T-11/T-17; no blind retry after an effect with a lost response; investigation budget counted in the total. Simulated clock and provider; limits testable without real waiting.

**Deliverable:** reconcilable ledger, stop reasons, proof that recovery does not restart a confirmed effect. Real provider guarantees remain unknown.

## PL-06 — Delivery and activation

**Scope:** `mailbox/`, runtime coordination, responses, contest, safe points and generations.

**Acceptance:** T-07/T-08/T-09/T-10/T-15/T-16; a single activation; new epoch in the same commit; a stale response refused; DEFER stays readable; bounded contest; effects in flight reported. Duplicates and concurrency tested, not only the nominal path.

**Deliverable:** proposal → response → safe point → ACTIVE loop with two simulated clients. STOP_BRANCH keeps the artifacts. A human stop revokes future protected rights without claiming to undo the past.

## PL-07 — Recovery and replay

**Scope:** recovery of jobs, locks, reservations, decisions, outbox and effects; tests with throwaway processes.

**Acceptance:** controlled crash before and after each relevant commit, delivery, activation, effect and result boundary; T-03/T-23; replay without a model or tool; equal logical state; an unknown future event refused. No transaction stays open while waiting on anything external.

**Deliverable:** crash matrix and minimal traces to reproduce failures. A process kill is not announced as a power-loss test.

## PL-08 — Demonstrator and oracle

**Scope:** synthetic order service, deterministic director and executor, independent verifier, five development variants.

**Acceptance:** real defect, misleading alert, concurrent fix, changed mission and absence of anomaly; T-13 simulated, T-20, T-21, T-22. Oracle read-only for agents, result bound to the executed fingerprint. Business test `ORD-IDEMPOTENCY-01` distinct from acceptance test T-17.

**Deliverable:** key-free demonstration, text status and audit artifacts. Provide the actually installed command once it exists. The deterministic director does not demonstrate H1. Test the repair budget for malformed outputs and their distinction from NO_CHANGE here, before gate G1; PL-11 reuses this mechanism.

## PL-09 — Bridge and projections

**Scope:** generic local transport, two processes, separate channels, immutable files and manifest, status CLI.

**Acceptance:** T-04/T-18; a partial generation refused; projections deletable in a throwaway space then rebuilt; no unresolved decision lost; producer derived from the channel; paths outside the root and links escaping it refused. Display the exact COOPERATIVE coverage.

**Deliverable:** Windows then Linux procedure and a report of what was exercised. A documentation-vault export is not required; simulating an unavailable local export is enough for the fault.

## PL-10 — Scheduler

**Scope:** event-driven triggers, coalescing, deadlines, turn exclusivity and cadence limits.

**Acceptance:** 100 events coalesced without losing provenance; no call without a change or a due deadline; an event arriving during a turn is kept; T-12; budget and call limits respected; a deterministic imperative handled without waiting for a model; no oscillation without new evidence.

**Deliverable:** simulated-time tests, wake-up metrics and a validated configuration. Publish the difference between a mandatory alert and a strategic review.

## PL-11 — Bounded real director

**Scope:** a configurable model adapter, context building, traced reads, a strict envelope and accounting. Start in SHADOW; provide a fake model for every reproducible acceptance test.

**Acceptance:** T-14/T-24; `NO_CHANGE`, INVESTIGATE and contract failure kept distinct; no business write capability; bounded context; a single turn; invalid output and timeout grant no power. Version prompts, model and parameters. External budget and transmissible data approved before any call.

**Deliverable:** audited SHADOW runs, then a bounded demonstration. One successful example is not a strategic benchmark.

## PL-12 — First real runner

**Scope:** an adapter chosen from the interfaces actually accessible, without assuming control of an existing personal session.

**Acceptance:** versioned capability report; observation, delivery, receipt, checkpoint, interruption and effect paths tested separately; kernel failure and an old worker exercised on throwaway resources; sub-agent restrictions included.

**Deliverable:** reproducible SHADOW/COOPERATIVE integration. ENFORCED is announced only for the surfaces actually covered and tested.

## PL-13 — Comparative evaluation

**Scope:** campaign registry, reserved variants, access control, randomization, A/B/C/D, data and analysis.

**Acceptance:** B, T, global cap and thresholds fixed before the campaign; oracles inaccessible; comparable observation opportunities; compute and time evaluated separately; every run kept; interval and denominator published; negative and unknown results visible.

**Deliverable:** a report that supports continuing, simplifying or declaring the result inconclusive. The 144-run pilot per campaign remains exploratory; do not run the campaign by default on the illustrative budget.

## PL-14 — Optional hardening

**Scope:** real gateway, permissions, resource fencing, stop, reconciliation and inventory of alternative paths.

**Acceptance:** a stale epoch or lease refused at effect time; no alternative authorized access to the same resource; an interruption does not erase committed effects; tests with an old live process and an unavailable kernel.

**Deliverable:** a guarantee limited per resource and version, known incidents and a recovery procedure. Conditional on enough project value and a specific authorization for the resources involved.

## Common definition of done

A ticket is done when its observable behavior is exercised, its useful refusals are tested, its documentation matches the code and the referenced evidence exists. The result lists the cases not exercised and the platform limits. Numerical coverage or an enthusiastic review does not replace the ticket's criteria.

The next kernel ticket is **PL-05**.

## CX-01 — Codex context companion

**DONE — Windows x64, context scope.** Slice prioritized by the maintainer after PL-04 to make the project usable in Codex. Depends on PL-03 and PL-04; does not replace PL-05 to PL-12.

**Result:** MCP STDIO server, resume skill, reversible project installation, diagnosis and private visual report. Four bounded operations: status, checkpoint, check and historical read. No model, director, scheduler or plan change in this slice.

**Exercised acceptance:** Codex App Server called the four tools for real; noise ignored, difference detected, old bytes kept and identical retry. Tests also cover restrictions, installation failure, removal, concurrency and protocol errors.

## CX-02 — Codex plugin and publication

**DONE — Windows x64, Linux in a container, context scope.** Slice prioritized by the maintainer before the public release. Depends on CX-01; does not replace PL-05 to PL-12.

**Result:** plugin installable from the repository catalog, human activation with `codex enable` and `codex disable`, project identified by Codex rather than by the model, bounded diff in `pl_check`, readable diagnosis that names the untrusted-project failure, visual report with captured and current versions, reports in English by default with French on request, admission of Python 3.13.x.

**Exercised acceptance:** real plugin installation into an isolated Codex home with CLI 0.166.0 and the 0.167 desktop build, three chat directories, `NOT_ENABLED` refusal, complete resume cycle, project mode; tests for sandbox metadata, hostile arguments, migration and diagnosis; full suite on Linux. A desktop chat with a model and the benefit on real resumes remain to be observed.

**Deliverables:** [guide](CODEX_QUICKSTART.md), [design](CODEX_INTEGRATION.md), [qualification](reports/cx02-codex-windows.json), README, Windows/Linux CI and demo site. Rollback: uninstall the plugin and run `codex disable`; captures are kept. The next usage evidence is the resume pilot described in [EXPERIMENTATION.md](EXPERIMENTATION.md).
