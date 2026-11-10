# Decisions and open questions

Status: November 10, 2026. This page separates inherited requirements from implementation choices. It is not a human approval of any budget or access. Every revision states its reason, its source and its consequences for the experiments.

## Reference choices

| ID | Choice and status | Rationale / alternative | Revisit when |
|---|---|---|---|
| ADR-01 | Inherited: local Python monolith, canonical SQLite | Reduces distributed boundaries; projections stay regenerable | A real constraint requires several hosts |
| ADR-02 | Inherited: one owning executor and a director without business writes | Avoids competing plans; self-review remains a viable control | P3 shows a separate session adds nothing |
| ADR-03 | Inherited: private state outside the repository and synchronized folders, separate exports | Avoids using a vault or shared file as a transactional database | A new storage medium is tested |
| ADR-04 | Implemented PL-02: in-memory domain before a local API | Pure transitions tested; FastAPI may come with the bridge | PL-09 requires a multi-process interface |
| ADR-05 | Qualified PL-01: CPython 3.13.16, SQLite 3.53.1, Windows x64, uv 0.12.23; Linux exercised in a container and in CI | Diagnosis of the linked library and rebuild from the lock; admission refined by ADR-20 | Runtime update or new platform |
| ADR-06 | Implemented PL-04: recorded reads + mandatory dependencies + declared `read_set` | Reduces omissions; does not claim to prove semantic completeness | X-01 and measurement of false invalidations |
| ADR-07 | Proposed: oracle out of the agents' reach, kernel shared by A/B/C/D | Makes the evaluation easier to interpret; isolation cost to accept | Any leak or observation asymmetry |
| ADR-08 | Retained: keep v0.1, add traceable complements; the specification is published in English with unchanged identifiers | Preserves provenance and the compatibility of both schemas | A future consolidated, versioned specification |
| ADR-09 | Implemented PL-02: JSON Schema for exchanges, immutable dataclasses for state | Reuses the initial contracts; avoids a second, diverging Pydantic definition | Proven need for type generation or maintenance cost |
| ADR-10 | Implemented PL-02: per-scope trajectory, global epoch and owner; ESCALATE as the human path | A closed pause keeps RESUME possible; escalation activates no plan | PL-06 reveals a case it cannot represent |
| ADR-11 | Implemented PL-03: SQLite format 1, explicit transactions and durable outbox | The receipt follows the joint commit; SQL constraints complement the domain | New migration or PL-07 recovery work |
| ADR-12 | Implemented PL-03: OS lock per database for the kernel's lifetime; separate readers | Process death frees ownership without interpreting a PID file; no concurrent conforming writers | PL-09 multi-process service; the same account can bypass the API |
| ADR-13 | Codex target: principal through MCP, separate director through App Server, single coordinating service | CX-01 and CX-02 deliver the MCP context surface; the director and its authorizations remain future work | Full PL-12 qualification |
| ADR-14 | Implemented PL-04: immutable SQLite BLOBs and a bounded double read | Atomic manifests and bytes; no global freeze of the workspace | Loads above 8 MiB or capture through a frozen file system |
| ADR-15 | Implemented PL-04: standalone interactive read-only HTML | Explicit maintainer request; one shareable file for synthetic data, private reports for real data | Proven need for a live multi-process view |
| ADR-16 | Implemented PL-04: every captured file is a mandatory dependency | Omission impossible for those files; conservative invalidations possible | X-01 measurement and PL-13 noise costs |
| ADR-17 | Implemented CX-01: context companion before the director | Explicit maintainer request after PL-04; usage benefit measured separately from P3 | Resume pilot, noise or excessive cost |
| ADR-18 | Implemented CX-01: short exclusive owner for captures, separate readers | Three concurrent clients exercised; no scheduler or effect in flight. Refines ADR-12/13 without allowing two simultaneous writers | PL-09: clients go through the permanent service |
| ADR-19 | Implemented CX-02: distribution as a Codex plugin; project identified by the start directory or `codex/sandbox-state`, nearest enabled ancestor | Codex ignores a project configuration unless the project is trusted; the Codex channel avoids any workspace supplied by the model. Project mode kept | Codex exposes another identity channel or changes STDIO launching |
| ADR-20 | Implemented CX-02: admission of CPython 3.13.x with a patched SQLite; 3.13.16 remains the qualified reference | Refusing a patch release made the tool unusable after a uv update; safety relies on SQLite's WAL fix | New Python series or a defect tied to a patch release |
| ADR-21 | Implemented CX-02: English MCP surface, skill, commands and documentation; reports in English by default and French on request | International publication; the model answers in the user's language; kernel messages are translated by code | Usage feedback or a new language |

These choices prove neither originality nor performance. The product runtime is locked, qualified on Windows and exercised on Linux; evidence is in [VALIDATION.md](../VALIDATION.md).

## Questions to resolve at the last useful moment

| ID | Question | Current proposal | Owner / deadline |
|---|---|---|---|
| Q-01 | Which Python distribution and which patched SQLite? | Resolved: uv-managed CPython, 3.13.16 / SQLite 3.53.1; [qualification](DEVELOPMENT.md); admission ADR-20 | Delivered in PL-01; Linux exercised in a container and CI |
| Q-02 | Exact format of the missing contracts? | Resolved: seven additional JSON Schemas, [catalog and boundaries](CONTRACTS.md) | Delivered in PL-02 |
| Q-03 | Detailed PAUSE/RESUME/ESCALATE semantics? | Resolved: per-scope trajectory and human arbitration without implicit activation | Delivered in PL-02; persistence PL-03/06 |
| Q-04 | Which deterministic local caps? | 100,000 simulated tokens as an illustration; injectable counters | Developer, PL-05 |
| Q-05 | Which model/provider and which transmissible data? | Configurable adapter; start in SHADOW | Maintainer, before PL-11 with an external service |
| Q-06 | Which real runner and which version? | Codex: plugin qualified with CLI 0.166.0 and the 0.167 desktop build; [design and limits](CODEX_INTEGRATION.md) | Full PL-12 qualification; no ENFORCED capability inferred |
| Q-07 | Which B, T, total envelope and `delta_min`? | Threshold proposal in the protocol; no paid budget granted here | Maintainer, before PL-13 |
| Q-08 | Where to isolate the reserved oracle? | Distinct identities and permissions or equivalent isolation; a process alone is not enough | Evaluator, before the first reserved variant |
| Q-09 | Where to export operational documentation? | Configurable local export; no vault write needed for the demonstrator | Maintainer, if an external export is requested |
| Q-10 | What real ENFORCED coverage? | Only the simulator at first; inventory of resources and access paths | Integration owner, PL-14 |

Q-05 to Q-10 do not block the first deterministic tickets. Resolve them with a concrete decision once their dependencies are ready, without installing a presumed integration.

## Rule for resolving contradictions

Invariants and the human scope prevail over a library choice. Schemas describe the shape of their version; the executable policy adds the semantic constraints. A complement incompatible with v0.1 remains a proposal until an explicit revision. Neither a green test nor this page can change the human goal.
