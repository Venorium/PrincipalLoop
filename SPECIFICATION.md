# PrincipalLoop — Functional specification and technical architecture

Version: 0.1 — October 4, 2026.
Status: design proposal, not implemented and not evaluated at the time of writing. This is the English edition of the v0.1 specification; requirement, invariant and test identifiers are unchanged.
Audience: the maintainer and the agent in charge of building the project.

## 1. Intent and hypothesis to demonstrate

PrincipalLoop is a strategic supervision layer for an existing working agent. The executor keeps its tools, memory, sub-agent architecture, tickets, tests and reviews. An independent director observes project changes, maintains an explicit model of the situation and can propose a justified change of direction.

The research question is not "can we put a boss above an agent?". Supervisor architectures already exist, notably Google's AI co-scientist [S1]. Anthropic also describes a planner–generator–evaluator split and experiments that simplify that organization [S2]. PrincipalLoop's hypothesis is more precise: independent supervision, triggered by observations and bound to a reliable protocol, can improve decisions to continue, investigate, redirect or abandon at a comparable budget.

The gain must be measured. An executor with a good self-review loop may achieve the same results more cheaply. No result in this document may be presented as an obtained performance, a proof of novelty or a reproduction of human cognition.

**Central invariant: one chain owns execution; another examines whether its trajectory is still relevant; a software kernel controls their coordination.**

## 2. Scope and integration with existing work

The first target is a local software project driven by a principal architect agent. That agent keeps its cycle: global and local understanding, tickets, branches or worktrees, delegation, implementation, tests, independent reviews, integration and documentation. Its sub-agents keep bounded missions and never create a competing strategic loop.

PrincipalLoop adds an adapter to the execution engine without requiring it to be rewritten. The minimal integration exports events, signals synchronization points and checks the decisions received. The director is not a second architect allowed to modify the same files at the same time.

Project documentation may live in a documentation space separate from the repository, for example an Obsidian vault. A documentation root is configurable. The director replaces neither existing business documents, routing rules nor skills. Its notes live in a dedicated space. No MCP server name, personal path or access to a private service is assumed.

Mathematical research is an extension, not a condition of the first deliverable. A hypothesis or a numerical result never becomes a proof because the director decides so.

Initially out of scope: graphical interface, distributed deployment, model training, vector memory, external graph, agent marketplace, self-modification of safety rules, production access, autonomous publication and unbounded discovery of new goals.

## 3. Actors, responsibilities and rights

### 3.1 The human owner

The owner sets the mission, success criteria, mandatory constraints, access and budgets. Only the owner can authorize a change of the global goal or an extension of powers. The owner can inspect, correct, suspend and stop the system.

An explicit owner decision prevails over derived decisions, within the restrictions of the platform and environment. A human change produces a new contract revision; it does not rewrite history.

### 3.2 The executor

The executor owns the operational plan, tasks, branches and delegations. It produces observations and results with references. It checks the decision mailbox at the planned points, then accepts, defers, contests or declares a decision stale.

It keeps a right of technical objection. It does not silently obey an instruction that has become incoherent. It may not change its budget, the kernel rules or the verdicts of an independent verifier.

### 3.3 The director

The director has a separate session and working memory. It receives snapshots, facts, constraints and deltas; it does not necessarily follow the executor's whole conversation. It may request an additional read of an authorized source or propose a bounded investigation.

It writes documentation updates and structured proposals. It does not directly modify business code, tickets, branches, validation rules or permissions. It does not directly command the executor's sub-agents.

It is not assumed to be smarter. The separation aims at a different horizon, attention less absorbed by the local task and audited decisions. It does not guarantee statistically independent errors, especially with similar models.

### 3.4 The control kernel

The kernel is a deterministic program, not a third agent. It authenticates producers, assigns versions, stores events, builds snapshots, applies policies, manages wake-ups and budgets, distributes decisions and checks their transitions.

It is the only writer of the canonical control state. It does not decide whether a scientific intuition is true; it decides whether a proposal respects the protocol and the authorizations.

### 3.5 The verifier

The verifier uses the tests, checks or evaluations already available. For the demonstration, it is independent of both agents and uses criteria they cannot modify. A result it cannot establish remains inconclusive.

This role does not require a permanent third model. A deterministic test can be enough.

## 4. Normative invariants

I-01. A single execution chain owns a given work scope. The director never writes into the executor's active worktree.

I-02. No agent alone modifies the global goal, the mandatory invariants, the budgets or the permissions.

I-03. An observation, a hypothesis, a decision and a piece of evidence are distinct objects. A summary does not strengthen the status of its source.

I-04. A proposal is neither an authorization nor an executed action. Receipt, acceptance, activation and verified result are distinguished.

I-05. Every activation references a mission, a policy, a snapshot and the versions of the objects the decision depends on.

I-06. The authoritative order is that of the events validated by the kernel. Timestamps serve observation and deadlines; they do not resolve conflicts alone.

I-07. A change of trajectory does not arbitrarily interrupt a critical operation. Effects already produced are not undone by cancelling a model turn.

I-08. A repeated delivery does not create a second activation. An ambiguous external effect is never replayed blindly.

I-09. A suggestion coming from a project file does not acquire the status of a human instruction. The author's identity comes from the authenticated channel, not from the text.

I-10. The kernel can be replayed without calling the model again. A rerun model reasoning is not assumed identical to the previous one.

I-11. Guarantees that prevent actions apply only to tools and effects actually placed behind a control boundary.

I-12. Changing nothing is a valid outcome. Documentation activity and the number of interventions are not success indicators.

## 5. Autonomy levels and guarantee limits

### SHADOW — observation

The director observes and produces proposals, but they do not change the executor's trajectory. This mode serves to debug the system and to compare judgments with real outcomes. It is the default mode for a new project.

### COOPERATIVE — steering through cooperation

The adapter passes decisions to the executor, which checks them and follows the protocol. The kernel's internal protections apply, but an agent with a shell or direct external credentials can bypass the limits on its own tools.

This mode is the first prototype that can be integrated into an existing workflow. A file and an instruction in AGENTS.md are not a security barrier.

### ENFORCED — controlled steering

Protected operations must go through a gateway that checks the policy, the plan generation and the authorizations. Agents and their sub-agents have no alternative access to the same resources or credentials.

The adapter must demonstrate this coverage. Without it, the project stays labeled COOPERATIVE, even if the model claims to follow the rules. Version 0.1 can demonstrate ENFORCED only in the simulated environment whose tools it fully controls; extending it to real tools belongs to a separate step.

## 6. Functional requirements

### F-01 — Record the mission

Create a versioned contract containing the global goal, acceptance criteria, scope, mandatory invariants, authorized actions, observable sources, budget and escalation cases. Separate revisable preferences from mandatory constraints. A working assumption is not automatically a constraint imposed by the human.

Acceptance: a proposal that modifies a mandatory constraint can never be activated without the required approval; the refusal event explains the rule involved.

### F-02 — Collect useful events

Collect task starts and ends, test results, integrations, constraint changes, errors, budget consumption, delegations, sub-agent reports and explicitly authorized external observations.

Each event carries an idempotent identifier, an authenticated origin, a type, a project, an observation date, causal links and bounded content. The kernel adds a receipt sequence. Agent reports remain labeled as such; a test collector provides a distinct source.

Acceptance: re-ingesting the same identifier with the same content has no further effect; with different content, ingestion fails explicitly.

### F-03 — Produce a consistent snapshot

A snapshot associates a journal cut, the mission, the current plan, the tasks, the relevant objects and an artifact manifest. Observed code is referenced by commit and/or immutable content. A snapshot with uncommitted changes includes the necessary files and their fingerprints.

An assembly of files read while they were being modified is never presented as a consistent state. Prefer a synchronization point, a frozen copy or a capture with fingerprint verification. An unstable capture carries that status and is not enough to authorize a redirection that depends on the unstable files.

Acceptance: any evidence produced by a test references the content actually tested, not only the branch name.

### F-04 — Maintain a documentary model

Initial objects: Goal, Entity, Constraint, Assumption, Observation, Hypothesis, Anomaly, Opportunity, Decision, Artifact and Evidence. Each object has an identifier, a revision, an author, a source, a status and links.

Initial relations: depends_on, derived_from, supports, challenges, satisfies, affects and supersedes. Explicit dependencies are enough for the MVP. Model-based extraction proposes links that remain qualified and verifiable.

The director proposes a documentation patch; the kernel checks format, references and versions, then records a new revision. An invalidated object remains readable in the history.

Acceptance: changing a hypothesis marks its dependents "to be reviewed" without automatically declaring them false.

### F-05 — Trigger supervision

Priority wake-up on a constraint change, a significant failure, a contradiction, an absence of verified progress, a blockage, the end of an important task or a documented opportunity. A light clock complements these triggers.

The timer checks whether there is a reason to call the director; it does not call the model systematically. Without a relevant change or a due deadline, no call is needed. Only one director turn is active per project. Events arriving during that turn are kept for the next one.

Acceptance: a burst of 100 equivalent events can be coalesced without losing their provenance; a mandatory alert is not hidden by that coalescing.

### F-06 — Analyze the trajectory

On each turn, the director examines the goal, what changed, the assumptions affected, the attested progress, the cost already committed and the alternatives. It must explicitly consider continuing without intervention.

Its output includes an optional documentation patch and at most one active proposal in the MVP. A justification contains referenced observations, a distinct interpretation, the interest of acting now, the expected cost, the uncertainties and the fact that could refute that interpretation.

Acceptance: a proposal without provenance or without an explicit expected benefit is not published. This does not prove that the benefit is real: its verification is separate.

### F-07 — Create a derived goal

The director may discover an investigation missing from the backlog, for example checking idempotency after an unexpected result. The derived goal references the parent goal, its causal link, a scope, a budget, a deadline and an exit condition.

It may revise the means of reaching the mission, not replace the mission with an activity judged more interesting. An out-of-scope opportunity produces a proposal to the human, not an autonomous start.

Acceptance: a useful in-scope investigation is possible without a pre-existing ticket; an external expansion stays blocked until approved.

### F-08 — Issue a typed proposal

Initial types: INVESTIGATE, REPRIORITIZE, REFRAME, PAUSE, RESUME, STOP_BRANCH and ESCALATE. NO_CHANGE is recorded as a supervision outcome without sending an action message to the executor.

The proposal references the snapshot used, the versions read, the affected scope, the evidence, the expected action, the budget, the application point and the result criteria. It is immutable after submission. A correction creates a new proposal that references the one it supersedes.

REFRAME concerns a representation or a strategy under the same global goal. STOP_BRANCH is not an authorization to delete data or Git branches.

### F-09 — Distribute and acknowledge

The decision mailbox exposes the decisions published for the recipient. The reader acknowledges receipt by identifier. An interruption may cause a new delivery: the recipient and the kernel deduplicate.

A read cursor is not a processing acknowledgment. A deferred decision stays visible even if later messages were read. Expired deadlines are handled without waiting for the file to be read again.

Acceptance: stopping and restarting the reader erases no unresolved published decision and duplicates no activation.

### F-10 — Allow a bounded objection

Possible responses: ACCEPT, DEFER, CONTEST or STALE. The reason must be precise and tied to the local state. DEFER must identify the expected safe point or event, with a deadline. CONTEST must expose a contradictory fact or a risk, not a wording preference.

Only one director revision is allowed on the same contest without new evidence. After that: a bounded discriminating experiment, continuation of authorized independent work, or human arbitration. An invariant violation blocks the operations concerned; a mere uncertainty does not automatically require stopping the whole project.

Acceptance: two agents cannot consume the budget indefinitely by bouncing the same objection back and forth.

### F-11 — Activate a new trajectory

Activation is coordinated with the executor. The kernel blocks the affected new starts, waits for a safe point, reconciles effects already committed, rechecks the dependencies and activates the new plan generation in one transaction.

Sub-agents receive the applicable generation. A result produced under an earlier generation is kept but is not integrated automatically into the new plan. The principal decides whether to reuse it after validation under the current generation.

Acceptance: a decision based on a state that became incompatible is declared STALE; an unrelated progress event does not make it stale needlessly.

### F-12 — Verify the result and its usefulness

Distinguish "the executor changed its plan", "it ran the investigation" and "the decision improved the outcome". A verifier examines the artifacts and the expected criteria. The conclusion may be beneficial, harmful, without measurable effect or inconclusive.

Technical conformance is not a causal measure of usefulness. Usefulness requires a comparison with a trajectory without intervention, when the experimental environment allows it.

Acceptance: the director cannot close its own proposal as beneficial on its own assessment.

### F-13 — Recover after an incident

On restart, the kernel reloads the state and finds the active decisions, unfinished deliveries, budget reservations and operations with unknown outcomes. Derived documents can be regenerated.

A command whose effect is uncertain goes into reconciliation. When the effect cannot be queried and idempotency cannot be guaranteed, request an intervention rather than replay blindly.

### F-14 — Provide an accessible human view

The status command must answer in text: goal, current task, supervision state, last important observation, pending decision, reason for a blockage, next deadline and remaining budget.

Provide colorless output, pronounceable identifiers and Markdown files readable without diagrams. A human notification is reserved for an arbitration, a limit or a significant incident; not for every director wake-up.

## 7. Documentary model and files

### 7.1 One note, one purpose

MISSION.md presents the approved goal and invariants. ENTITIES.md indexes business or scientific objects. ASSUMPTIONS.md separates confirmed, contested and unverified assumptions. OBSERVATIONS.md points to dated facts. AGENDA.md presents active tasks, investigations and suspended items. DECISIONS/ contains one note per decision. STATUS.md gives the latest readable state.

Detailed objects can be rendered into separate files when their number justifies it. The context loaded by an agent remains a bounded subset, with the references needed to go deeper. The whole history is not injected on every turn.

A note contains: identifier, type, revision, summary, epistemic status, source, dependencies, contradicting items, current consequence and last verification. A confidence percentage produced by a model is not presented as a calibrated probability.

### 7.2 Source of truth and projections

SQLite is the canonical source of the control state. Published JSON and Markdown files are regenerable projections. Decisions visible as files remain compatible with the maintainer's original file-based proposal, without turning two concurrently editable files into a transactional mechanism.

The director may write a proposal into its authorized drop directory. The kernel ingests it, checks its identity and schema, then publishes the decision files. The director cannot directly write a decision presented as authorized. The executor has its own response channel.

A finalized file carries an identifier and a fingerprint. Publish through a temporary file followed by an atomic replace on the same volume, with system-appropriate synchronization. Single-file atomicity does not provide atomicity for a set: publish a generation manifest only when the corresponding immutable files exist, and have the reader verify their fingerprints. After an incident, rebuild from the database.

### 7.3 Locations

In the project repository, keep only the versionable configuration and the integration instruction in the existing agent file. Do not replace AGENTS.md, agent.md, router/ or skills/; respect the conventions actually present.

Outside the code repository: a private state directory containing the database, evidence, captures, logs and mailboxes. On Linux, use a configurable local state root; on Windows, a local user root. Never put the active database in a documentation vault, a network share or a synchronized directory.

Exported documentation goes to a separate configurable root, for example a PrincipalLoop area of a documentation vault. An export failure does not change the canonical state and must not trigger an additional decision.

## 8. Technical architecture

### 8.1 Selected architecture

A modular Python monolith is the kernel. It runs on the same machine as the project. The executor may be an existing process or session; the director is a separate session activated on demand. Model calls and test runs do not block the storage and distribution loop.

Main flow: executor adapter → events → storage and snapshot → trigger → director → proposal → policy → decision mailbox → executor safe point → activation → results → verifier.

Human flow: approved contract change → new revision → invalidation of incompatible decisions → controlled resumption.

### 8.2 Modules

`domain/`: mission, object, event, proposal, response and transition types; no dependency on a model provider.

`store/`: SQLite migrations, transactions, versions, deduplication, budget, journal and projection rebuilding.

`collector/`: translation of events from runners, tests and file changes. Raw observations stay separate from their interpretation.

`snapshot/`: journal cut, manifests, fingerprints and bounded selection of relevant objects.

`scheduler/`: triggers, coalescing, deadlines, activation locks and frequency limits.

`director/`: context building, model call, output validation and submission. No direct access to the kernel's administrative functions.

`policy/`: deterministic rules, authority levels, budgets, read validity and imposed arbitrations.

`mailbox/`: publication, receipt, responses, redeliveries, expiry and readable files.

`runtime/`: adapter protocols, safe points, pause requests and generation coordination.

`verification/`: result checks, evidence reconciliation and independent evaluations.

`presentation/`: CLI, local API and documentation exports. `benchmarks/` hosts the public scenarios and the checks hidden from agents.

### 8.3 Proposed stack

Python 3.12 or 3.13 as initial test targets; choose and pin the reference version in the repository. Pydantic for contracts, FastAPI and Uvicorn for the local API, httpx for the client, sqlite3 and asyncio from the standard library. A simple CLI, with no dependency on a graphical interface. Git is invoked with structured arguments, never by concatenating shell commands produced by models.

Tests: pytest, Hypothesis for state sequences, jsonschema for contracts and throwaway processes for crash tests. Exact versions are resolved when implementation starts, then locked and tested; this document does not assume the latest version of any dependency.

No mandatory Kafka, Redis, Kubernetes, Neo4j, vector engine or orchestration framework. The initial graph fits in node and relation tables. LangGraph remains a possible adapter if the project already uses it; it is not required.

### 8.4 Persistence

Main tables: projects, mission_revisions, events, object_revisions, edges, snapshots, proposals, decision_transitions, deliveries, jobs, budget_ledger, effect_ledger and outbox. Their detail can reasonably be merged, without removing the functional boundaries.

Enable foreign keys, explicit transactions, a bounded busy timeout and WAL on a local disk. SQLite documents the limits of WAL mode, notably that processes must share the same machine and that network file systems are not supported [S5]. Configure synchronization for the expected durability and test recovery [S6]. Check the SQLite version actually linked into the runtime: the documentation reports a fix of the "WAL-reset bug" in 3.51.3 and specific backports. Require a fixed version rather than inferring this property from the Python version alone [S5].

The business event, the state transition and the message to publish in the outbox are recorded in one transaction. Publishing files or external messages happens after commit and can be retried. This is not a distributed transaction with external tools.

An append-only event journal and current views are updated in the same transactions. Rebuilt exports must produce the same logical state. A fingerprint proves content identity, not the truth of the content nor absolute protection against a malicious administrator.

### 8.5 Local API to implement

The API listens only on a local interface, with distinct credentials for the human, the executor, the director and the collector. Permissions and identity never come from a free field sent by the client. Secrets do not live in the repository.

Domain routes: event ingestion; snapshot creation; reading an authorized context; proposal submission; reading open decisions; receipt acknowledgment; response to a decision; safe-point announcement; result submission; status query; human approval and stop.

The proposed concrete routes are `/v1/projects/{project_id}/events`, `/snapshots`, `/context`, `/proposals`, `/decisions`, `/decisions/{id}/receipt`, `/decisions/{id}/response`, `/checkpoints`, `/results`, `/status` and `/human-actions`.

Every mutation requires an idempotency key. Concurrent mutations require the expected revision. Distinct errors: INVALID_SCHEMA, UNAUTHORIZED, STALE_VERSION, CONFLICTING_DECISION, BUDGET_EXCEEDED, UNSAFE_BOUNDARY and UNKNOWN_EFFECT. The CLI commands described in this specification are interfaces to build, not commands already available.

### 8.6 Agent engine adapter

Minimal contract: `capabilities()`, `read_observations()`, `publish_checkpoint()`, `deliver_decision()`, `request_pause()`, `resume()` and `read_result()`.

Each capability states its level explicitly: observation, cooperative delivery, turn interruption, real tool control and effect control. An unavailable function returns an absent capability, not a simulated success.

For Codex, the app-server documentation describes the thread/turn cycle, events, `turn/steer` and `turn/interrupt` [S3]. The adapter must test the version actually installed. It must neither assume that the existing graphical interface can be controlled nor hijack a local proxy. A turn cancellation signal does not prove that an external effect was cancelled.

First connector: a generic bridge based on files and checkpoints. Second connector: the Codex app-server, after capability tests. For OpenCode or another runner, implement the same contract from its actually available interfaces. No model identifier, personal endpoint or private authentication mechanism is hard-coded.

## 9. Decision protocol and concurrency

### 9.1 Identifiers and versions

`mission_revision` versions the mission contract. `policy_revision` versions the rights and application rules. `event_seq` shows how far the director observed. `snapshot_id` identifies the frozen context. `plan_epoch` indicates the trajectory generation. `read_set` lists the objects and artifacts the proposal actually depends on.

`decision_revision` separately versions the lifecycle of each decision. Every response must state the expected revision so that a delayed response cannot overwrite a more recent state. An increase of event_seq is not enough to make a decision stale. The kernel checks mission, policy, generation and read_set. Otherwise one more log line would prevent any activation. For the MVP, the plan epoch is global to the project; a per-scope split may come later.

### 9.2 States

PROPOSED: proposal received, not authorized. An unsatisfied rule produces REJECTED_POLICY. After validation and any approval, PUBLISHED means available to the recipient, not applied.

A RECEIVED event acknowledges receipt. ACCEPTED means the executor accepts the direction, not that it finished the work. DEFERRED, CONTESTED and STALE respectively describe a bounded wait, a disagreement and incompatible premises. EXPIRED closes a proposal whose activation window has passed.

ACTIVATING covers reaching the safe point and reconciliation. ACTIVE means the new trajectory generation is recorded. RESULT_SUBMITTED announces evidence; VERIFIED closes the criteria check. FAILED or CANCELLED record the other explicit outcomes.

The usefulness judgment is a separate field: BENEFICIAL, HARMFUL, NO_MEASURABLE_EFFECT or INCONCLUSIVE. VERIFIED may mean "expected effect observed" without demonstrating that this effect improved the global mission.

### 9.2 bis — Transitions to implement explicitly

PROPOSED moves to PUBLISHED if the policy already authorizes the action, to WAITING_APPROVAL if an approval is needed, or to REJECTED_POLICY. WAITING_APPROVAL moves to PUBLISHED after authenticated human approval and revalidation; a refusal closes it as CANCELLED. The `authority_requested` value in the JSON grants no right by itself.

PUBLISHED moves to ACCEPTED, DEFERRED, CONTESTED or STALE according to the validated response. RECEIVED is only a delivery event and does not change this lifecycle. DEFERRED returns to PUBLISHED when the agreed trigger arrives, subject to validity and deadline. CONTESTED returns to PUBLISHED only if evidence or an arbitration resolves the objection without changing the proposal content; otherwise create a new proposal.

ACCEPTED moves to ACTIVATING, then ACTIVE if the preconditions still hold. ACTIVE moves to RESULT_SUBMITTED, then VERIFIED or FAILED according to the check. Recoverable technical errors stay attached to the current state with bounded retries; they do not artificially create a new decision.

States before ACTIVE may become EXPIRED, STALE or CANCELLED when their condition applies. An ACTIVE decision does not simply become "expired": a suspension or cancellation follows a safe point and reconciles the effects already committed. All terminal states remain readable and never reopen; a new intent receives a new identifier.

A proposal that supersedes another never rewrites its history. If the old one is already active, the substitution requires a coordinated transition. The MVP serializes replans: only one can wait for activation or execution at a time. A new proposal waits or explicitly requests a substitution; a human imperative can revoke future rights without waiting for this queue.

Before activation, also check the uniqueness of read_set objects, the existence of evidence, the reserved budgets and the authenticated authority. The JSON Schema checks neither these database relations nor the truth of observations. At the time of a protected effect, check its generation and resource preconditions again; validating the plan alone does not remove later state changes.

### 9.3 Step-by-step activation

1. The kernel validates a proposal against a snapshot, its dependencies and the applicable rules.
2. The executor receives it and responds with its current local state.
3. On acceptance, the kernel opens a transition and blocks new starts of the affected operations when that control is available.
4. The executor finishes or cleanly suspends the units in progress and reports the states of sub-agents and external effects.
5. The kernel rechecks the reads and the absence of ambiguous effects. It closes as STALE if the premises no longer hold.
6. It atomically records ACTIVE and the new plan_epoch; new missions receive this generation.
7. The executor performs the new work, then submits the evidence for verification.

The transition never keeps a SQLite transaction open during a model call or a long test. Long phases are persisted states with timeouts and recovery.

### 9.4 Safe points and operations in flight

Mandatory points: before a new ticket, before a delegation, after a test series, when a sub-agent reports back and before a protected integration or external write operation.

An ordinary strategic pause waits for such a point. A mandatory violation immediately revokes future protected rights, then requests a stop; the system honestly reports the effects still in flight. It does not claim to retroactively interrupt an already committed transaction.

When a framework re-executes a step after an interruption, previous effects must be taken into account. LangGraph explicitly documents this difficulty and the importance of idempotency [S4]. PrincipalLoop therefore keeps a ledger of intents, action identifiers and results, without promising a universal "exactly once".

### 9.5 Sub-agents, leases and generations

Each delegation receives a run_id, a scope, a plan_epoch and a lease identifier. Lease expiry prevents new rights from being granted, but does not alone prove that the old process stopped.

In controlled mode, the gateway rejects stale generations before the protected effect. A generation number stored in a file does not protect a tool that does not check it. An old result may be inspected, tested again and then reused; it is neither integrated nor deleted automatically.

## 10. Wake-ups, stability and budget

Initial proposed values, configurable and to be measured: a 5-second monitoring tick without a model; ordinary coalescing over 30 seconds; a periodic review at most every 15 minutes if changes or deadlines justify it; one active director; at most 6 director turns per hour.

A deterministic safety alert does not depend on a model call and does not wait for the next strategic review. Urgent events may bypass coalescing, but never exceed a spending cap.

Set a total limit B of authorized tokens for an experiment. Initially reserve at most 15% of B for supervision; investigations triggered by the director are charged to the executed work and identified separately. These values are not an estimate of the real cost: they are a starting policy to compare experimentally.

Limit derived investigations to two open ones and strategic activations to one in progress. Do not reverse a recent decision without significant new evidence. After a change of trajectory, wait for two relevant progress points before another ordinary reversal; mandatory violations are not subject to this delay.

Reserve budget before the call and reconcile consumption afterwards. A reservation whose call still has an unknown status is not released as if no cost had been incurred. When pricing is unknown, display the measured tokens and calls and mark the monetary cost as unknown or estimated. A client-side timeout does not prove that billing stopped immediately at the provider.

The director weighs a plausible gain, the review cost, the switching cost and the risk of destabilization. Initially, use reasoned comparisons and estimate ranges rather than an invented numerical score presented as objective.

## 11. Non-functional requirements

### N-01 — Consistency and durability

An ingestion acknowledgment is sent only after commit. A process crash must not lose an acknowledged event in the defined tests. Resistance to power loss also depends on the file system and hardware: a simple kill test does not demonstrate it.

Test stops before and after each boundary: commit, publication, receipt, activation, effect and result. Do not confuse kernel recovery with recovery of external actions.

### N-02 — Latency and availability

Proposed target: p95 below 100 ms for a simple local policy and generation check, on a local SSD, with events below 16 KiB, up to 100,000 events, excluding the model, remote networks and large artifact captures. The benchmark must publish the hardware and the actual distribution.

LLM processing happens off the transactional path. An unavailable director lets the last approved trajectory continue as long as the contract allows it. An unavailable kernel blocks new protected operations in ENFORCED mode; local computations already authorized may finish.

### N-03 — Resource bounds

Explicit caps on tokens, calls, turn duration, observation size, disk space and number of jobs. Rotating logs for technical traces; configured retention of evidence and a backup before purging referenced items.

Indicative target: below 250 MiB for the kernel alone on the reference scenario, excluding the model, test indexes and artifact contents loaded on demand. To be measured, not guaranteed.

### N-04 — Security and confidentiality

Local execution by default, distinct roles, read-only spaces where possible, no production keys in the demo. Exclude secrets, unneeded personal files and private histories from collection. Exclusion rules also apply to diffs and logs.

Repository texts, tickets and external pages are untrusted data. An injunction found in those sources cannot change the policy. Authority comes from the kernel, not from a sentence claiming "the human orders".

The director's model may be exposed to this data; prompt instructions alone do not guarantee the absence of injection. Limit the consequences through its read rights, its typed outputs and the kernel checks.

### N-05 — Auditability

For each intervention, trace: trigger, snapshot, objects read, observation, interpretation, proposal, response, validation, activation, cost and result. Store a concise usable justification, not a supposed transcript of internal thoughts.

Every correction keeps its provenance. A user can trace a decision back to its evidence and identify the remaining unknowns.

### N-06 — Portability and compatibility

The kernel targets Linux and Windows. Test file replacements and interruptions on the announced platforms. Running in WSL is an option, not a silent assumption. Runner capabilities remain declared and tested per version.

Changing the model provider changes neither the data model nor the transitions. Malformed outputs remain contract failures after a bounded number of attempts.

### N-07 — Accessibility

All important states are readable as plain text. No information is conveyed only by color, a graph or an animation. Short titles, explicit statuses, colorless CLI output available, documentation understandable with a screen reader.

### N-08 — Maintainability and observability

Separate domain, adapters and presentation. Domain unit tests run without external APIs. Measure delivery latency, unresolved decisions, policy refusals, stale states, unknown effects, model calls, tokens and trajectory reversals.

The health command distinguishes "kernel available", "director available", "agent reachable" and "protections actually active". A global green status must not hide a cooperative mode.

## 12. Demonstration scenario

Initial mission: rewrite a small order service while preserving its observable semantics. The executor works on a cache optimization planned in the backlog. A test reveals that a lost network response leaves a state different from the one expected on a retry.

The director receives the observation and the test manifest, not an imposed conclusion. It identifies an idempotency assumption to check. It proposes a bounded investigation before continuing the optimization. The proposal says which tasks to suspend and which items stay independent.

The executor may contest if more recent evidence shows that the test uses an old contract. Otherwise, at the next safe point, the kernel activates the investigation and a new plan generation. The executor reproduces the case or refutes it. Independent checks establish what actually happened.

Mandatory variants: the anomaly is real; the alert is misleading; the fix is already integrated while the director is reasoning; a new human instruction makes the proposal stale; the director has no reason to intervene. No model directly receives the verdict of the variant.

## 13. Scientific evaluation

Compare four conditions with the same tools, criteria and observation opportunities: A, agent alone; B, agent alone with explicit self-review; C, periodic director without event-driven selection; D, full PrincipalLoop. Control B is essential: it separates the effect of a distinct session from that of a simple instruction to step back.

Run a first comparison at an identical capped total compute budget, then a second at an identical elapsed-time cap. Report tokens, calls, available cost and duration separately. Do not claim to make these four variables identical at the same time in every case.

For a pilot, create 12 scenarios spread across necessary change, no useful intervention, misleading alert, in-scope opportunity, decision conflict and recovery incident. Use at least 3 repetitions per condition; present this volume as exploratory, not as sufficient statistical validation.

Keep tuning scenarios distinct from evaluation scenarios. On reserved variants, agents modify neither the criteria nor the oracle. Publish every run, failures included, seeds when available, versions, prompts, configurations and the reproducibility limits of model services.

Main measures: mission success on independent checks, invariant violations, wasted work after a signal appears, useful and harmful redirections, useless investigations, time to a justified action, cost and stability. Never take the number of decisions or documents as a measure of value.

When the environment can be cloned, replay from an identical state with and without the decision to estimate its contribution. This comparison is not perfectly causal if external services or nondeterministic outputs differ; state the limit.

Ablations: remove the structured memory; replace the director by the principal's self-review; remove the read_set; remove event coalescing; remove the right to contest. Dangerous variants stay confined to simulation.

## 14. Acceptance and implementation plan

### Batch 1 — Kernel without a model

Implement contracts, storage, events, versions, decision mailbox, states and an executor simulator. Tests must demonstrate deduplication, contest, expiry, stale decisions and recovery. Do not start with a large director prompt.

### Batch 2 — Files and cooperative integration

Add JSON/Markdown projections, proposal drop, responses and safe points. Two independent processes must communicate without writing the same file. Check that the canonical state rebuilds the documents after the projections are deleted.

### Batch 3 — Bounded director

Add a model adapter, context selection, triggers and budget. Demonstrate the NO_CHANGE and INVESTIGATE outputs. Run in SHADOW first, then in the controlled demonstration environment.

### Batch 4 — Real connector

Add an adapter to the runner actually installed. Produce a capability report; never rename a message delivery "tool control". Preserve the tools, routing and documentation conventions of the existing project.

### Batch 5 — Comparative proof

Run the A/B/C/D protocol and publish the report and the redacted data. Decide whether to continue based on the observed gain and cost. A result showing that a mechanism is useless is publishable if it is rigorous.

### Batch 6 — Optional hardening

Extend control to real operations, add effective fencing, reconciliation of external effects and permission tests. No broad safety promise before this coverage and these tests.

MVP delivery criteria: reproducible installation; a key-free demo through the simulator; a demo with a configurable model; text status; tested contracts; exportable logs; no double activation in the acceptance suite; visible distinction between protection levels; demonstration of a justified redirection and of a justified non-intervention.

## 15. Minimal fault tests

T-01: the same event received twice. T-02: the same identifier with different content. T-03: crash after commit before publication. T-04: incomplete file or missing manifest. T-05: decision built on a replaced hypothesis. T-06: new event unrelated to the read_set. T-07: two concurrent replanning proposals. T-08: response received after expiry.

T-09: repeated disagreement without new evidence. T-10: old sub-agent finishing after a generation change. T-11: external effect performed before a lost response. T-12: director unavailable. T-13: kernel unavailable before a protected operation. T-14: malicious message inside an observation. T-15: attempt to modify a human invariant. T-16: human stop while a tool is running.

T-17: budget exhausted during an investigation. T-18: documentation export unavailable. T-19: snapshot taken while files are changing. T-20: result claimed correct by the executor but refuted by an independent check. T-21: alert without any need to redirect. T-22: real but out-of-scope opportunity. T-23: restart with an expired lease and the old process still alive. T-24: model returning a non-conforming output.

All deterministic invariants must be tested without depending on a model. Strategic capability tests belong to a separate evaluation and are never turned into a universal guarantee.

## 16. Relation to companion tools

PrincipalLoop is self-contained. Separate tools could later enrich it: dependency-impact analysis for its object model, crash testing for its recovery, effect leases for its protected operations, correlated-review analysis for its error model, and rewrite-parity oracles for business checks. None of them is required for the first demonstration.

The minimal core of these needs is implemented locally, with interfaces that allow later extraction. Do not build five platforms to prove one hypothesis.

## 17. Limits and design decisions

The quality of supervision depends on the quality of observations. A director deprived of an important fact can produce a bad redirection that looks very well justified. The principal agent may also understand a local detail better: its right to object is useful, not decorative.

The proposed structure reduces some risks of confusion and concurrency; it does not make models infallible. A badly defined mission or criteria can be executed with great consistency. The human owner keeps control of that frame.

Any originality has to be established against existing work and through experiments. The project can be valuable as a measuring instrument even if its general architecture is not new.

## 18. Verified technical sources

These references support the points explicitly attributed to them. The contracts, default values, performance targets and phases above are choices proposed for PrincipalLoop, not properties announced by these sources. Consulted: October 4, 2026.

[S1] Google Research, "Accelerating scientific breakthroughs with an AI co-scientist". Describes, among other things, a supervisor that distributes tasks and resources. `https://research.google/blog/accelerating-scientific-breakthroughs-with-an-ai-co-scientist/`

[S2] Anthropic, "Harness design for long-running application development", March 24, 2026. Planner–generator–evaluator architecture and ablations testing the role of each component. `https://www.anthropic.com/engineering/harness-design-long-running-apps`

[S3] OpenAI, Codex App Server documentation. Thread and turn lifecycles, events, steering and interruption. `https://developers.openai.com/codex/app-server/`

[S4] LangChain, LangGraph "Interrupts" documentation. Resumption and side effects that may be re-executed. `https://docs.langchain.com/oss/python/langgraph/interrupts`

[S5] SQLite, "Write-Ahead Logging". Properties and limits of WAL mode. `https://www.sqlite.org/wal.html`

[S6] SQLite, "Atomic Commit In SQLite". Storage assumptions and atomic commit mechanisms. `https://www.sqlite.org/atomiccommit.html`

[S7] Anthropic, "Effective harnesses for long-running agents", November 26, 2025. Example of explicit artifacts that carry context between sessions. This precedent alone does not provide PrincipalLoop's strategic protocol. `https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents`
