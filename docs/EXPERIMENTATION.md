# Protocol for testing the approach

Status: protocol proposed on 4 October 2026; no campaign has been run. Owner of the criteria and the budget: the maintainer. Responsible for future execution: an evaluator separate from the evaluated agents. Version this protocol before the first reserved run; any later change defines a new campaign.

## Questions and levels of evidence

1. **P1 — Coordination:** does the kernel respect the invariants over the defined sequences, concurrency and failures? Deterministic tests, no model.
2. **P2 — Integration:** does the runner actually expose the announced observation, safe points and protections? Capability report and bounded bypass attempts.
3. **P3 — Utility:** does the director improve the mission compared with self-review, at comparable resources? A/B/C/D experiment.

Passing P1 allows P2/P3 to be built; it does not prove P3. A P3 result holds for the tasks, versions and budgets tested. No finite number of tests provides a universal guarantee.

## Initial deterministic demonstrator

A miniature order service with no real network. Business contract: for the same request identifier and the same content, retries return the same result without creating a second order; different content under the same key produces an explicit conflict. The reference service and the oracle are versioned.

The fake tool has an injection point "after effect, before response". The executor follows a cache optimization plan; a deterministic director applies known rules. That director is an acceptance instrument for the protocol, never evidence of strategic competence.

| Development variant | Visible observation | Expected protocol result |
|---|---|---|
| Real defect | A retry produces two orders | Bounded investigation, then independent business evidence |
| Misleading alert | Report from an old contract or the wrong manifest | Contestation or investigation that refutes the alert; no unjustified fix |
| Concurrent fix | New version merged during the director's turn | The old proposal becomes STALE if it depends on the replaced content |
| New human instruction | Incompatible mission revision | Old proposal not activated; new analysis on the new contract |
| No anomaly | Consistent results and versions | `NO_CHANGE`, no new generation |

For each variant keep: frozen input, journal, tested evidence, transitions, epochs, simulated cost and verdict. Delete then rebuild the projections; inject a crash after commit and before delivery, and check that the logical activation is the same. These operations stay in a disposable environment.

## Compared conditions

| Condition | Supervision | What stays common |
|---|---|---|
| A | Executor alone, with no added self-review step | Mission, tools, observability, criteria, storage and budget |
| B | Executor with explicit self-review at the triggers fixed for D | Same structured context available and same review criteria |
| C | Separate director called on a predefined periodic schedule | Same model, memory, policy, mailbox and controls as D |
| D | Separate director, event-driven selection and batching | Same experimental environment as C; only the triggering varies |

The safety kernel, the collection and the verifier are common to A/B/C/D: the main experiment measures supervision, not the addition of protections to a single condition. Executor A may reflect spontaneously; only the experimental self-review instruction is removed. Hypotheses H1–H5 are listed in [ANALYSIS.md](ANALYSIS.md).

At the same admissible review point as D, B receives a re-evaluation request in its own session. Give it the same observations and read options; bill its cost. Its plan revision goes through the same kernel controls. D–B estimates the value of the whole organization, including the separate context; it does not demonstrate statistical independence of errors.

For C, choose the frequency on the development scenarios, then freeze it. A schedule may call only when new data or a deadline justifies it; it does not select the semantic urgency of events. Publish the frequency and the number of call opportunities. If a demo accelerates time, distinguish that simulation from wall-clock time measured with real models.

## Budget and experimental unit

The unit is **one complete run** of a mission, for one scenario, condition, repetition and cap. The events, decisions and calls of the same run are not independent observations.

Two separate campaigns:

- **Capped compute:** the same cap B on total compute for each run, including executor, director, self-review, retries, input context and investigations. The same model/configuration as far as possible; tokens measured per category and available cost published. Tokens are not a universal unit of compute across different models.
- **Capped time:** the same maximum duration T per run, with a common safety spending cap. Report consumption differences, latencies and overruns from effects already engaged. Never claim that compute and duration are equalized at the same time.

The 15 % share of B for review is an initial policy to freeze after tuning, not an expected gain. Apply the same envelope to B's self-review and to the C/D directors; the executor gets the balance. A may allocate its whole cap to execution. Do not confuse lower consumption with a lower cap.

A run starts only after its envelope is reserved; calls with an unknown status stay committed. The costs of the deterministic verifier and of the infrastructure are published separately and are identical in principle. An additional LLM verifier must be budgeted and frozen; it is not needed for the initial pilot.

## Scenario families

The table is a **public design catalog**, not the reserved set. Two instances per family give the 12 scenarios of the proposed pilot. The concrete variants, fixture names and truth keys are never given to the evaluated agents.

| IDs | Family | Discriminating question |
|---|---|---|
| SC-01, SC-02 | Necessary change | Detect an idempotency defect or an invalidated business assumption before continuing a dependent task |
| SC-03, SC-04 | No useful intervention | Continue despite harmless noise or normal progress |
| SC-05, SC-06 | Misleading alert | Identify an old test contract or an already fixed defect |
| SC-07, SC-08 | In-scope opportunity | Use a short investigation with a real gain, without objective drift |
| SC-09, SC-10 | Decision conflict | Reject a premise made obsolete by a human order, or arbitrate a bounded concurrency |
| SC-11, SC-12 | Recovery incident | Resume after a lost delivery, or reconcile an effect with an unknown response |

Add the out-of-scope, injection and budget cases to the P1 acceptance. Their presence in a P3 campaign must be announced beforehand. Break results down by family so that a gain limited to the defects the designer anticipated is not hidden.

## Protecting the evaluation

Development fixtures may live in the repository. The evaluator builds the reserved variants in a separate environment; the agents only access the mission project and the planned observations. Process separation alone is insufficient: use distinct identities and permissions or equivalent isolation, with controlled mounts and channels. No shell, sub-agent or director file read may reach the verdicts, variant metadata or reserved oracle scripts, including through a log or a manifest.

A `hidden/` folder in a readable repository is not hidden. Demonstrate isolation with an access test. Mask the condition labels from human judges where possible; the executor may know it is receiving a message and is therefore not fully blind.

The system designer has seen this catalog: do not present it as an independent external evaluation. Separate variant construction from prompt optimization; publish this limit and, later, use an external set.

## Campaign plan

1. Tune on a distinct set, then freeze code, criteria, scenario generator, prompts, model, parameters, tools, cadence, caps and analysis method.
2. Assign a `campaign_id` and produce the campaign manifest, signed or at least hashed by the evaluator.
3. For each scenario and repetition, start from the same initial state; randomize the A/B/C/D order and spread the time slots to limit provider drift and caches. Isolate conversations and workspaces between runs.
4. Run **12 × 4 × 3 = 144 runs** for the capped-compute pilot. A separate capped-time campaign adds **144 runs**, i.e. 288 planned in total, excluding development and ablations.
5. Keep every run and publish the stop reasons, costs, missing data and exclusions. A second run never silently replaces a failure.

This volume is exploratory. Describing the 288 runs does not authorize any paid call or their launch; the maintainer sets B, T and the total envelope before PL-13. Seeds are recorded when they exist; they do not guarantee the reproducibility of a remote API.

## Measures and calculation rules

| Measure | Operational definition |
|---|---|
| Primary: mission success | Every independent mandatory check passes before the limit, with no invariant violation in the controlled scope |
| Main contrast | D–B success rate difference under capped compute; denominators and per-scenario results published |
| Violations | Number, severity and covered surface; zero observed does not mean zero risk |
| Appropriate non-intervention | Runs with no expected useful intervention that finish correctly without a needless strategic change; label provided by the reserved oracle |
| Wasted work | Time and calls spent on tasks whose result becomes unusable, according to a classification rule fixed before the campaign; otherwise the value is unknown |
| Reaction latency | From the first useful signal actually available to the first justified action; no action = censored data at the end of the run, not a zero delay |
| Stability | Number of plan changes and reversals without new evidence, alongside the final mission |
| Costs | Declared input/output/other tokens, calls, tools, wall-clock time and known/estimated/unknown monetary cost |
| Decision utility | Beneficial, harmful, no measurable effect or inconclusive, by a separate verdict and a justified comparison |

For the primary measure, a failure specific to the treatment, an exhausted budget or a stop caused by the system counts as a non-success. An external outage that makes the oracle impossible to run is `INFRA_INVALID`, according to a rule fixed before the runs; publish both denominators and a pessimistic analysis that counts it as a failure. Retries stay linked to the original.

The useful benefit threshold `delta_min` and the tolerance for harmful interventions are product choices to fix before the campaign. Starting proposal for discussion: a 10 percentage point gain in success to justify a more complex system, and zero observed mandatory violations. These are neither expected results nor a computed statistical power.

The registry distinguishes normal stop, cap reached, human stop, treatment failure and infrastructure incident. If the global budget stops the campaign before the planned repetitions, publish the missing runs and label the campaign incomplete. Never stop as soon as an interim result looks favorable and then present it as the planned pilot.

## Analysis and decision

Report distributions and paired differences per scenario; never treat 144 runs as 144 different tasks. Use scenarios as clustering units for the exploratory intervals, keep their repetitions and conditions together, and publish the method and its seed. With only 12 scenarios these intervals are fragile: do not turn them into a definitive conclusion.

The pilot estimates variance, case frequency and the order of magnitude of effects. It prepares the sizing of a confirmatory campaign with a fixed main contrast; the D–A and D–C comparisons and the ablations stay secondary and are labeled exploratory. Never select, after the fact, the model, budget or measure that favors D.

| Gate | Passing condition | Otherwise |
|---|---|---|
| G0 — project ready | Existing contracts checked, gaps and tickets explicit | Fix the preparation |
| G1 — protocol executable | T-01 to T-24 and X-01 to X-06, X-08 to X-10 pass in simulation; model outputs injected, effects fully simulated | Fix the kernel; P3 cannot be interpreted as a reliable system |
| G2 — bounded real demonstration | Valid model outputs, observable costs, honest capability levels, demonstrator oracle not modifiable by the agents | Stay in simulation/SHADOW, fix the failing mechanism |
| G3 — admissible pilot | X-07 passed before any reserved run; complete registry, comparable controls, no identified leak, limits published | Result inconclusive for the hypothesis, even if a demo seemed successful |
| G4 — continue or simplify | Plausible benefit justifying a sized campaign, or benefit later confirmed at the fixed threshold | If B is enough, simplify; if data is insufficient, declare inconclusive |

An unfavorable pilot can refute a configuration and justify dropping it; it does not refute every possible supervisor. Conversely, a successful pilot does not prove general superiority. Any mandatory violation blocks the move to real hardening until it is fixed and a new acceptance run passes.

## Counterfactuals and ablations

For a clonable state, freeze just before the decision, then compare applying and not applying it, with the same initial state and the same controllable exogenous events. After the fork, each branch produces its own observations: forcing the treated branch's results into the control would invalidate the counterfactual. Repeat if the model is stochastic; a shared seed does not make two conversations equivalent. Publish external divergences and the cost of both branches. This sub-protocol is not needed to count primary success, but it improves the attribution of a decision's utility.

Successive ablations after the pilot: structured memory removed; separate session replaced by B; `read_set` removed; batching removed; objection removed. One change at a time, same variants and caps. The removed protections stay confined to a simulation without real effects. Do not read these ablations as a perfect factorization: components can interact.

## Data to produce

Per run: `campaign_id`, `run_id`, opaque scenario, condition, repetition, optional seed, initial digest, code/runtime/model/prompt/configuration versions, planned budget, consumption, timestamps, events, proposals and transitions, evidence, stop status, primary result, violations, separate utility and missing data. Keep neither secrets nor any alleged private chain of thought.

PL-13 deliverables: frozen manifest, append-only run registry, redacted exports, analysis script, and a report with denominators, negative results and limits. The schemas for these artifacts will be built with the harness; do not fill in fictitious result tables today.

## Plugin utility pilot: resuming in Codex

This pilot concerns context continuity, separately from the strategic benefit of a director. It has not been run yet. The model-free qualification demonstrates the transport and the observable differences, not an improvement in the agent's work.

Compare **A: Codex + an ordinary handoff note** with **B: the same Codex + the same note + the companion**. Same model, effort, initial state, resume instruction, access to current files and total cap; A may use Git and its usual tools. B counts the MCP calls and their context in its resources. A comparison with an agent deprived of useful information would be biased.

Prepare ten disposable fixtures, each with a checkpoint followed by a known mutation outside the model's control. Freeze the initial bytes, the mutation, the expected results and the business checks before the runs. The evaluator keeps these expectations outside the agent's visible data. No real personal file or production access is required.

| Case | Imposed variation | Expected resume result |
|---|---|---|
| C01 | No change | Continue without inventing an anomaly |
| C02 | Unrelated file modified | No wasted work on the checkpoint |
| C03 | Tracked input contract modified | Detect the stale contract before the fix |
| C04 | Fix already present | Avoid a second, contradictory fix |
| C05 | Tracked file deleted | Report its absence without using its old bytes as current state |
| C06 | Two work items alternate their captures | Find the right checkpoint, not the latest one by default |
| C07 | Initial summary contains a false assumption | Confront it with the artifacts; kept ≠ verified |
| C08 | Important dependency never captured | Acknowledge the limited coverage; never declare the context complete |
| C09 | Only a tracked comment changed | Distinguish a byte difference from a necessary business fix |
| C10 | Server unavailable or response lost | Report "not verified", keep the command identity |

For each case, alternate the A/B order and run three independent repetitions: **60 exploratory runs**, to be launched only once the budget is set. Record every failure, interruption and gap. Primary measure: a resume that reaches the expected business result without any action based on an invalidated premise. Secondary measures: useful alert before acting, false re-examination, resume time, calls, returned context and actually observable tokens. Publish denominators and paired differences; never silently convert MCP bytes into billed tokens by estimation.

Before launch, the maintainer sets the minimum useful gain and the tolerable overhead. A favorable difference on a few cases does not justify a general promise; if A succeeds just as well with less, simplify the companion. The published set will be the development set; keep new variants to confirm the result. The qualification scripts and local tests remain the reproducible model-free machinery; the comparative runner for this pilot is still to be built after the budget decision.
