# Critical analysis and hypotheses

Status: framing proposed on October 4, 2026. Readers: maintainer, architect, developer and evaluator. Goal owner: the maintainer. Revise this analysis when the mission changes or an experimental result contradicts it.

## Framing conclusion

The approach is coherent as an **experimental supervision instrument**, under three conditions: keep a single execution chain, make interventions revisable from evidence, and compare their value with a well-equipped self-review. Its superiority is not established.

The first question is: "does a separate session lead to better decisions than a comparable self-review, and does the protocol apply those decisions without causing more damage?" The next useful result is a falsifiable deterministic demonstrator, then a comparative pilot; prompt length does not settle this question.

## Available facts and coverage

This table describes the **initial preparation state**. PL-01 and PL-02 have since added Git, a qualified runtime and the tested domain; see [VALIDATION.md](../VALIDATION.md) for the current state.

| Finding | Status and consequence |
|---|---|
| 12 initial files: specification, instructions, declared validation, 2 schemas, examples and prompts | Verified in the workspace; no kernel and no product test suite |
| No Git repository initialized | Verified; the implementation had to establish version tracking |
| A global Python 3.14.2 with SQLite 3.50.4 available | Verified locally; suitable for documentation checks, not a qualified product environment |
| Python 3.12/3.13 targets and a patched SQLite required by the specification | Initial requirement; selection and locking still to do at the time |
| 15 validations announced in the initial folder | Historical declaration without a script; replaced by reproducible checks in [VALIDATION.md](../VALIDATION.md) |
| Real runner, permissions, tool control, director time and cost | Untested; no integration or cost guarantee |

The internal sources inspected were all initial files, without private services or a documentation vault. No additional team standard, remote ticket or pipeline was provided. External references are scoped in [SOURCES.md](SOURCES.md); they do not establish PrincipalLoop's effectiveness.

## Local model of the problem

| Object | Useful relation | Limit |
|---|---|---|
| Mission and policy | Fix the domain of admissible decisions | An incorrect mission can be executed faithfully |
| Project state | Produces dated, versioned observations | Observations may be incomplete or misleading |
| Executor | Transforms the project and produces evidence | Its narrative is not an oracle |
| Director | Connects changes, hypotheses and alternatives | A separate session can reproduce the same error |
| Kernel | Arbitrates protocol, rights and generations | It does not know whether an idea is scientifically true |
| Verifier | Establishes criteria on identified artifacts | Its independence depends on its access and its oracle |

Candidate causal chain: available signal → useful context selected → trajectory error detected → valid proposal → safe activation → work changed → better mission outcome. Each arrow can fail; the protocol demonstrates only some of them.

Evidence levels are distinct: **P1**, kernel conformance on the tested cases; **P2**, technical coverage of the connector; **P3**, strategic benefit over a defined population of scenarios. None replaces the other two.

## Competing hypotheses to separate

| ID | Hypothesis | Result that would challenge it |
|---|---|---|
| H1 | Session separation adds value at a comparable budget | D does not outperform B on the reserved variants |
| H2 | Event-driven triggering uses the budget better than periodic review | C does as well as or better than D under the same caps |
| H3 | Structured memory makes observations more usable | Removing that memory degrades neither result nor cost |
| H4 | Freshness, contest and generations prevent harmful interventions | Protections fail on the targeted faults or systematically block progress |
| H0 | Self-review or better tests are enough | B matches D with less operational complexity |
| H5 | The apparent benefit comes from more compute, better context or a leaked oracle | The advantage disappears once these factors are controlled |

H1 to H3 belong to an experiment; H4 contains deterministic properties and usefulness effects to measure separately. "Not rejecting H0" does not prove equivalence. Comparisons are detailed in [EXPERIMENTATION.md](EXPERIMENTATION.md).

## Structural invariants and conventions

Structure: single ownership of work; separation of authorities; atomic activation; preserved provenance; no blind repetition of an unknown effect; an oracle distinct from the evaluated agents. The twelve normative invariants I-01 to I-12 remain those of the specification.

Revisable conventions: Python, SQLite, file names, a 5-second tick, 30-second coalescing, 6 calls per hour, a 15% supervision share, rendering types. Changing them can affect performance or cost; it does not replace the invariants. Changes are versioned before any comparison.

## Structural tests

| Test | Case examined | Design consequence |
|---|---|---|
| Inversion | The executor is right and the director is wrong | The right to contest and control B are essential |
| Inversion | The right decision is to continue | `NO_CHANGE` and no-intervention scenarios must be rewarded by the final outcome |
| Reductio | Any increase of `event_seq` makes a proposal stale | A busy journal would make every activation impossible: compare the relevant dependencies |
| Reductio | "Accepted" means "applied successfully" | A failure between acceptance and effect would make two opposite states indistinguishable: separate the steps |
| Reductio | The model alone assesses its own usefulness | Any convincing error could self-certify: independent oracle and counterfactual |
| Edge case | Zero useful signal or a zero budget | No mandatory strategic call; explicit status and unchanged authorized trajectory |
| Edge case | An old worker still alive after expiry | An expired lease is not enough; check at the time of the protected effect |
| Edge case | A real dependency is missing from `read_set` | Validating only declared references can accept an obsolete decision |

## Material gaps to close

| ID | Observed gap | Proposed treatment | Ticket |
|---|---|---|---|
| GAP-01 | Only the proposal and the response had a schema | Define mission, event, snapshot, director turn, checkpoint, effect and result | PL-02 |
| GAP-02 | `read_set` is self-declared and the schema does not guarantee unique IDs | Union of served reads and declared references, kernel-mandated dependencies, atomic comparison of expected versions | PL-04 |
| GAP-03 | Pause, resume, escalation and replacement may have different lifecycles | Separate decision state, trajectory state and usefulness judgment | PL-02 |
| GAP-04 | A file bridge alone does not provide a reliable identity | Controlled paths and transport identity; stay COOPERATIVE if the same account can modify everything | PL-09 |
| GAP-05 | No isolated oracle and no convention for experimental results | Public development fixtures, reserved variants out of the agents' reach, run registry | PL-08, PL-13 |
| GAP-06 | "Comparable budget" does not fix which compute is actually counted | Shared ledger: executor, director, self-review, investigations and retries | PL-05, PL-13 |
| GAP-07 | "Replay" can be confused with re-executing effects | Replay validated events into state; no model or tool is called | PL-03, PL-07 |
| GAP-08 | A business example named `T-17`, already used for budget exhaustion in the acceptance suite | `ORD-IDEMPOTENCY-01` namespace for the business test, T-xx reserved for acceptance | Preparation |

## Priority risks

1. **False freshness.** A forgotten implicit dependency → an obsolete decision activated. Recorded reads reduce the risk without proving semantic completeness; test a deliberate omission.
2. **False independence.** Same model, same information and correlated errors → misleading agreement. Measure outcomes against an oracle; never use agreement as a measure.
3. **Oracle leak.** An agent with a shell in the evaluation repository → reserved criteria accessible. Really isolate the evaluator; a folder name or `.gitignore` protects nothing.
4. **Correct kernel, uncontrolled action.** A direct write bypassing the gateway → an unjustified guarantee. P2 tests the coverage of access paths, sub-agents included.
5. **Biased measurement.** More context or budget for D → a benefit wrongly attributed to separation. Share observation and accounting, freeze the variants and the analysis.
6. **Overly costly supervision.** Repeated revisions, latency or cluttered memory → less final work. Measure total consumption and non-intervention; propose a simplification if B is enough.
7. **Unqualified base.** An off-target local runtime and an unpatched SQLite → recovery evidence not admissible. Resolve before persistent kernel tests (done in PL-01).

Probabilities are not estimated for lack of data. The order reflects the impact on the project's validity, not a supposedly calibrated risk score.

## First decision made possible

Start with PL-01 and PL-02, then a vertical slice without a model: event → proposal → contest or acceptance → safe point → single activation → independent result. Present three outcomes: justified investigation, justified non-intervention, stale proposal. No external access is needed.

Defer the provider choice, the real connector and any paid budget until this P1 evidence exists. Open decisions have an owner and a resolution deadline in [DECISIONS.md](DECISIONS.md).
