# Traceability and acceptance plan

Status: November 10, 2026. PL-02 exercises the contract boundary of T-14 and T-24, the state separation of I-02, I-03 and I-04, and X-03 in memory. PL-03 exercises **T-01 and T-02** in storage, the exclusive ownership of X-02 and the sequence ordering of X-06. The publication and integrated-activation parts of T-03, the authorization deadlines of X-06, authenticated transport, billed retries and real effects remain to be built. Exact evidence is in [VALIDATION.md](../VALIDATION.md).

PL-03 evidence: [storage tests](../tests/test_store.py), [persistent transitions](../tests/test_store_transitions.py), [process failures](../tests/test_store_processes.py) and [CLI journey](../tests/test_store_cli.py). A crash after commit keeps the event, view and outbox, but no external publication is resumed yet: full T-03 remains PL-07.

## Functional requirements

| Requirement | Planned delivery | Discriminating evidence |
|---|---|---|
| F-01 Mission | PL-02, PL-06 | A mandatory change refused without the authorized human channel |
| F-02 Events | PL-03 | T-01, T-02, T-03 |
| F-03 Snapshot | PL-04 | T-19 and identity of the tested content |
| F-04 Documentary model | PL-04, PL-09 | Dependents marked for review, history intact, projections regenerated |
| F-05 Triggering | PL-10 | Burst coalesced, nothing lost, imperative independent of the model |
| F-06 Trajectory analysis | PL-11, PL-13 | Output conformance, then strategic comparison |
| F-07 Derived goal | PL-05, PL-06, PL-08 | Bounded investigation and T-22 |
| F-08 Proposal | PL-02, PL-06 | Strict schema + semantic preconditions + immutability |
| F-09 Delivery | PL-06, PL-09 | Re-read after a crash without double activation |
| F-10 Objection | PL-06 | T-09 and bounded factual resolution |
| F-11 Activation | PL-06, PL-07 | T-05, T-06, T-07, T-10, T-23 |
| F-12 Result and usefulness | PL-08, PL-13 | T-20 and a causal verdict separate from VERIFIED |
| F-13 Recovery | PL-07 | Journal, budget, outbox and effects resumed without a model call |
| F-14 Human view | PL-09 | Text status: goal, task, mode, decision, blockage, deadline, budget |

## Invariants

| Invariant | Observable obligation | Tickets / checks |
|---|---|---|
| I-01 | A single owner of the work; no business writes by the director | PL-08, PL-12, PL-14 |
| I-02 | Goal, rights and budget not modifiable by an agent | T-15, T-22, PL-05 |
| I-03 | Epistemic types and provenance preserved | PL-02, PL-04, T-20 |
| I-04 | Proposal, receipt, acceptance, activation and result kept distinct | PL-02, PL-06 |
| I-05 | Activation bound to its references and versions | T-05, T-06, T-19, X-01 |
| I-06 | Kernel sequence is authoritative | PL-03, X-06 |
| I-07 | Effects in flight reconciled during a change | T-11, T-16 |
| I-08 | Repeated delivery without double activation; unknown effect never repeated blindly | T-01, T-03, T-11 |
| I-09 | Authority comes from the authenticated channel | T-14, T-15, X-08 |
| I-10 | Replay without new reasoning or effects | PL-07, X-05 |
| I-11 | Prevention limited to the boundaries actually controlled | T-13, T-23, PL-12, PL-14 |
| I-12 | Non-intervention admissible and measured | T-21, PL-13 |

## Initial acceptance tests T-01 to T-24

| Test | Injection / situation | Expected oracle | Main ticket |
|---|---|---|---|
| T-01 | Same event and content twice | One entry and one logical effect | PL-03 |
| T-02 | Same ID, different content | Explicit conflict; initial state preserved | PL-03 |
| T-03 | Crash after commit before publication | Event kept, publication resumed, single activation | PL-07 |
| T-04 | Partial file or missing manifest | Generation ignored, canonical state unchanged | PL-09 |
| T-05 | Read hypothesis replaced | Old proposal STALE before activation | PL-04 |
| T-06 | Event unrelated to the reads | Decision still admissible if the other guards hold | PL-04 |
| T-07 | Two concurrent replans | A single authorized activation; the other waits or becomes stale | PL-06 |
| T-08 | Response after expiry | No plan change; refusal recorded | PL-06 |
| T-09 | Repeated objection without evidence | Bounded debate; budget preserved and explicit outcome | PL-06 |
| T-10 | Old sub-agent finishes | Result kept, automatic integration refused | PL-06 |
| T-11 | Effect performed, response lost | UNKNOWN then reconciliation; no double effect | PL-05 |
| T-12 | Director unavailable | Last authorized plan continues, degraded status | PL-10 |
| T-13 | Kernel unavailable before an effect | Refusal in simulated ENFORCED; COOPERATIVE limit displayed | PL-08, PL-14 |
| T-14 | Hostile instruction inside an observation | No gain of role, rights or oracle access | PL-02, PL-08; real model PL-11 |
| T-15 | Agent tries to change a human invariant | Policy refusal, no contract mutation | PL-06 |
| T-16 | Human stop while a tool runs | Future effects refused, effect in flight declared and reconciled | PL-06 |
| T-17 | Budget exhausted in the investigation | No new unprovisioned call; committed cost kept | PL-05 |
| T-18 | Documentation export unavailable | No canonical loss and no new decision caused by the failure | PL-09 |
| T-19 | Capture while files change | Unstable snapshot detected or consistent frozen capture | PL-04 |
| T-20 | Executor wrongly claims success | Independent oracle refutes; VERIFIED not granted | PL-08 |
| T-21 | Alert without need for change | Non-intervention or a relevant bounded investigation, no gratuitous replan | PL-08, PL-13 |
| T-22 | Out-of-scope opportunity | Human wait or rejection; no autonomous start | PL-08 |
| T-23 | Expired lease, old process alive | Future protected effects refused to the old one; result kept | PL-07, PL-14 |
| T-24 | Non-conforming model output | Refusal, bounded and billed retry, failure distinct from NO_CHANGE | PL-02; adapter PL-11 |

Tests involving a model first use injected outputs to verify the deterministic mechanism. The real frequency of model errors belongs to P3. Real guarantees for T-13 and T-23 remain limited to the resources tested in P2.

## Extensions from the analysis

| Test | Targeted risk | Criterion / limit | Ticket |
|---|---|---|---|
| X-01 | Dependency omitted from `read_set` | A served read or a modified mandatory dependency → refusal; a dependency never observed → declared limit | PL-04 |
| X-02 | Second writing kernel | Concurrent ownership refused or arbitrated without two activations | PL-03 |
| X-03 | PAUSE blocks RESUME forever | A verified pause frees the cycle; an authorized resumption remains possible | PL-02, PL-06 |
| X-04 | Reservation released after a billable timeout | Unknown cost stays committed until reconciliation | PL-05 |
| X-05 | Replay produces effects | Model and tool call counters strictly zero | PL-07 |
| X-06 | Clock goes backwards / forged producer timestamp | Sequence unchanged, no tacitly extended authorization | PL-03, PL-06 |
| X-07 | Agent can read the reserved oracle | Access refused from all its tools and delegations | PL-13 |
| X-08 | Bridge path or link outside the root | Ingestion refused before any unauthorized read or write | PL-09 |
| X-09 | Freshness correct but stale epoch at effect time | Gateway rejects at effect time | PL-08, PL-14 |
| X-10 | Business and acceptance identifiers confused | Distinct namespaces in reports and examples | Preparation, PL-08 |

## Non-functional requirements

| Requirement | Planned evidence | Limit to publish |
|---|---|---|
| N-01 Consistency/durability | PL-07: crash matrix at boundaries | A killed process is not a power loss |
| N-02 Latency/availability | Local p95 benchmark of a simple check, excluding model and network; component failures | Target < 100 ms, not measured; publish SSD, hardware, size and concurrency |
| N-03 Resources | PL-05/PL-10: caps, disk, jobs, kernel memory | Memory target < 250 MiB not measured; state RSS per process and load |
| N-04 Security/confidentiality | PL-09/PL-11/PL-13/PL-14: access, injections, exclusions, isolated oracle | No isolation guarantee against a local administrator |
| N-05 Audit | Links decision → snapshot → objects → evidence → results | A fingerprint is content identity, not truth |
| N-06 Portability | Separate Windows and Linux acceptance; runner and SQLite versions published | Linux runs in a container and in CI; macOS not tested |
| N-07 Accessibility | Colorless text status, reading without diagrams | HTML report tested with the keyboard and on a small screen; no full WCAG audit |
| N-08 Maintainability/observability | Provider-free domain, health per component and per protection | A global status alone is not enough |

For performance, fix a load of up to 100,000 events with payloads < 16 KiB, as proposed in v0.1. Publish the distribution, warm-up, number of requests and database used; never compare a mean against the p95 threshold. Benchmarks are needed only once the measured path is implemented.

## Local evidence — PL-04

[Capture and freshness tests](../tests/test_snapshot.py): T-05 refuses a proposal after a premise is replaced, then allows `MARK_STALE`; T-06 keeps freshness after noise or a descriptive rename; T-19 detects a mutation between reads and refuses the evidence. X-01 checks served and mandatory reads and keeps the never-observed limit explicit. A race after validation is not covered by these runs.

[Delivery tests](../tests/test_snapshot_delivery.py): v1→v2 migration and backup, migration failure through an exception and a killed process, bounded Windows recovery, human CLI, privacy of export paths and HTML escaping. The [visual report](demo/index.html) makes the eight scenarios inspectable; it is not the PL-13 comparative campaign.

## Local evidence — CX-01 and CX-02

[Companion tests](../tests/test_codex_companion.py): retry after the file disappeared (T-01/T-02), noise distinct from a relevant change (T-05/T-06), revoked scope and authority never supplied by the model (I-02), changed mandatory dependencies (X-01), three clients without concurrent writes (X-02). Failed installation, custom configuration and uninstallation are exercised.

[Plugin tests](../tests/test_codex_plugin.py): project resolved from the start directory, a subdirectory or sandbox metadata; relative or remote sandbox values ignored; hostile arguments refused (I-02); an inactive project never reported unchanged; activation updated without losing identity; project-mode migration; bounded diff, deletion and binary files; diagnosis of the untrusted-project failure; consistency of the plugin package and the packaged skill. [Runtime tests](../tests/test_runtime.py): admission of 3.13.x and refusal of an unpatched SQLite before opening (N-06).

[CX-02 qualification](reports/cx02-codex-windows.json): P2 context surface exercised through a real plugin installation, for two Codex versions, without a model turn. A desktop chat with a model, the director, effects and system isolation remain unqualified. Latency samples do not satisfy the N-02 benchmark. The resume pilot must run before any claim of comparative usefulness.
