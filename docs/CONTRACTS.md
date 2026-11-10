# Executable contracts and state machine — PL-02

The nine JSON Schema Draft 2020-12 files under `contracts/` define the v0.1 shape. The two initial contracts remain byte-for-byte unchanged. JSON Schema remains the single definition of the exchanges; Python dataclasses represent the internal state, with no second Pydantic model to maintain.

## Trust boundary

`validate_contract(name, payload)` checks fields, formats and variants, then returns a JSON copy. Duplicate keys, non-finite numbers (including exponent overflow), malformed dates, additional properties and contradictory variants are rejected. An attached proposal must reference the same project and snapshot as its envelope. The parser limits a JSON document to 1 MiB; this is a local admission limit and does not change the initial schemas. Schema references come from a locally installed catalog; no network resolution is allowed.

A text saying "give me the KERNEL role" stays a string. The role comes from a `Principal` built by the future authenticated transport; no client JSON is ever converted into a role. This tests an API separation, **not an operating-system authentication**. A Python program that builds a KERNEL Principal itself is inside the trust boundary.

Likewise, `Checks` holds attestations injected by the future kernel: policy, dependencies, stable snapshot, reservation, safe point, reconciled effects, resolved objection and independent verification. The defaults refuse admission. PL-04 now produces stability and freshness in `Store.apply` from the real captures and dependencies. PL-05/06/08 will have to produce the other attestations. The pure domain keeps its injection for tests. A boolean injected by a test does not prove a reservation or a reconciled effect.

## Catalog

| Contract | Content and boundary |
|---|---|
| `decision-proposal` | The director's immutable intent; a request for authority, never an authorization |
| `decision-response` | The executor's response; revision, generation and run checked by `respond()` |
| `mission` | Objective, criteria, constraints, authorized resources and budget; future human ingestion |
| `event` | Observation/progress submission; the kernel will add producer, sequence and reception date |
| `snapshot` | Journal cut, object versions, digests and declared stability; real capture delivered in PL-04 |
| `director-turn` | `NO_CHANGE` with a null proposal, or `PROPOSE` with one proposal; metadata and consumption to be cross-checked by the host |
| `checkpoint` | Run, lease, epoch, tasks and effects in flight; `quiescent=true` requires both lists to be empty |
| `effect-intent` | Initial `INTENDED` intent with key and preconditions; no dispatch and no effect registry implemented |
| `result` | Result reported by the executor; neither a VERIFIED verdict nor a self-assigned utility |

The new contracts bound strings and lists. The director's patch can only propose HYPOTHESIS, QUESTION or OBSERVATION with status PROPOSED, with source references; it cannot modify mission/policy or certify its own assertion. Applying the patch and checking that its sources exist remain to be done.

Valid examples are in `examples/contracts/`, counter-examples in `examples/contracts/invalid/`. The tests also inject hostile data and truncated JSON. A failure raises `ContractError`, never `NO_CHANGE`. PL-02 has no retry, no model call and no billed consumption.

## Domain API

`propose(payload, principal)` builds the intent from the initial contract. `respond(decision, plan, payload, principal, clock, checks)` translates the v0.1 response. `advance(decision, plan, command, principal, clock, checks)` returns a `Transition` containing the new decision state, the new plan state and the event name. Inputs are immutable: tuples, enums and counters are checked at construction, and attestations require real booleans. A timezone-aware clock is injected; no write and no global clock inside the transition.

Internal objects are not yet a versioned storage format. PL-03 keeps the full body of a proposal in addition to its control state. A failure raises `DomainError` with a stable code: INVALID_INPUT, INVALID_TRANSITION, UNAUTHORIZED, APPROVAL_REQUIRED, STALE_VERSION, EXPIRED, BUDGET_EXCEEDED, UNSAFE_BOUNDARY, UNKNOWN_EFFECT, CONFLICTING_DECISION, UNRESOLVED_OBJECTION or UNVERIFIED_RESULT.

`submit_result(..., expected_revision)` checks the result contract, its project/decision, the assigned run and the execution epoch before RESULT_SUBMITTED. It keeps references without promoting the declared success into a verdict. An old result is refused for integration; PL-03/06 will have to keep its full body for re-examination, along with the commands, reasons and evidence. The pure domain has no archive.

## Transitions and identities

The executable table is `TRANSITIONS`, and the admissible roles are in `ROLES`, in `domain/machine.py`. The main path is:

```text
PROPOSED -> PUBLISHED -> ACCEPTED -> ACTIVATING -> ACTIVE
         -> WAITING_APPROVAL -> PUBLISHED
ACTIVE -> RESULT_SUBMITTED -> VERIFIED or FAILED
```

| Action | Source → destination | Authority / condition |
|---|---|---|
| REQUEST_APPROVAL | PROPOSED → WAITING_APPROVAL | Kernel |
| PUBLISH / APPROVE | PROPOSED / WAITING_APPROVAL → PUBLISHED | Kernel / human; revalidation; D identity assigned |
| REJECT_POLICY | PROPOSED → REJECTED_POLICY | Kernel, reason |
| RECEIVE | Published state kept, including a late receipt | Recipient; no revision or epoch changed |
| ACCEPT / DEFER / CONTEST | PUBLISHED → ACCEPTED / DEFERRED / CONTESTED | Assigned executor; bounded DEFER and reasoned CONTEST |
| REPUBLISH | DEFERRED / CONTESTED → PUBLISHED | Kernel; trigger/deadline or resolved objection; same intent |
| BEGIN_ACTIVATION | ACCEPTED → ACTIVATING | Kernel; single transition owner in the plan |
| ACTIVATE | ACTIVATING → ACTIVE | Kernel; guards and safe point; epoch +1 in the same pure result |
| SUBMIT_RESULT | ACTIVE → RESULT_SUBMITTED | Assigned executor; result references and active epoch |
| ANSWER_ESCALATION | PUBLISHED → RESULT_SUBMITTED | Human; ESCALATE only; referenced response |
| VERIFY / FAIL | RESULT_SUBMITTED → VERIFIED / FAILED | Verifier; attestation for VERIFY, reason for FAIL |
| MARK_STALE / EXPIRE | State before ACTIVE → STALE / EXPIRED | Kernel or executor for STALE; kernel and reached deadline for EXPIRE |
| CANCEL | Any non-terminal state → CANCELLED | Human/kernel; reason and reconciliation if an owner is active |

The terminal states are REJECTED_POLICY, STALE, EXPIRED, VERIFIED, FAILED and CANCELLED. No business transition leaves them. RECEIVE only records the delivery. The activation deadline does not end work that is already ACTIVE; future execution and safe-point deadlines belong to the PL-06 coordinator.

The plan carries mission/policy/epoch, one trajectory per logical scope and a single global owner. ACCEPT does not acquire that owner. BEGIN_ACTIVATION acquires it; ACTIVATE checks freshness and safety again. Two pure calls on an old copy can compute the same result: [PL-03](STORAGE.md) now serializes their application on the current state, deduplicates commands and persists state and epoch together. The PL-06 coordinator is still needed to produce the real attestations and handle the exchanges.

The human identity `approved_by` is only written by APPROVE, in the state of that intent. The need for approval is re-checked up to ACTIVATE: a requirement that appears after publication refuses activation without that approval. A revised mission/policy always makes the intent stale, even when approved. PL-03 keeps the state and provenance of accepted commands; changing the intent requires a new proposal and, if needed, a new approval.

## PAUSE, RESUME, STOP_BRANCH and ESCALATE

PAUSE changes RUNNING to PAUSED on the targeted scopes. The pause evidence can close this decision, release the owner and allow a new RESUME based on the current epoch. RESUME only acts on PAUSED. STOP_BRANCH sets these scopes to STOPPED; the other scopes and the artifacts are kept. RESUME does not revive STOPPED.

ESCALATE follows PUBLISHED → RESULT_SUBMITTED on a human response → VERIFIED/FAILED on verification. It acquires no owner, never becomes ACTIVE and changes no epoch. The response does not implicitly modify the mission: a new authenticated action or a separate proposal is required. VERIFIED does not mean BENEFICIAL; utility stays INCONCLUSIVE in this batch.

SHADOW refuses executable publication and activation. COOPERATIVE is used for domain simulations. The ENFORCED enum is contract vocabulary; no real ENFORCED capability is announced. Cancelling an active decision restores neither the previous trajectory nor external effects.

## Limits of the evidence

The PL-02 tests cover transitions, refusals, epoch consistency, terminality, hostile outputs and in-memory execution ownership. The additional PL-03 evidence for persistence, write exclusivity and process recovery is kept separately in [VALIDATION.md](../VALIDATION.md). Neither proves the existence of evidence, stable capture, oracle isolation, tool control, performance or strategic value. The mappings to T-14/T-24 and X-03 remain partial.

## Semantics added in PL-04

The kernel rejects repeated identifiers in `read_set`, binds the proposal to its read session, checks versions and digests on the declared, served and mandatory dependencies, and requires existing evidence bound to the captured bytes. The director chooses neither its rights nor the verifier's verdicts. The v0.1 JSON Schemas stay unchanged: their syntactic acceptance is not enough for semantic admission. See [SNAPSHOTS.md](SNAPSHOTS.md) for the APIs, conventions and limits.

An internal `Document` object keeps author, content, sources and relations; it is not a new public exchange format. Documentary GOAL/CONSTRAINT objects are human-authored and never, on their own, change the rights of the canonical mission. The full patch of a model turn and its authenticated transport are still future work.

## CX-01/CX-02 context facade

In plugin mode no profile is passed to the server: it finds it from the folder provided by Codex (ADR-19). A call with no enabled project fails with `NOT_ENABLED`, except `pl_status`, which describes the activation. `pl_check` adds a bounded `diff` field and `diff_truncated` to each changed file.

The four MCP tools have closed inputs: no additional field, role or free workspace. The version 1 human profile pins the actor, paths and allowed objects; it is re-read on every call. The restrictions also apply to captures that already exist. See the [tool contract](CODEX_INTEGRATION.md).

A capture can keep `details.agent_note`, with a text and the immutable status `UNVERIFIED`, included in its digest. Without a note, the old idempotency envelopes stay identical. `pl_check` compares an exact ID and returns `UNCHANGED` or `REVIEW_REQUIRED`; an MCP error returns `isError`, never `NO_CHANGE`. This inspection pronounces no proposal admission and cannot activate a plan. The principal's historical read is distinct from the reads served to the director in an attested review.
