# Sources and provenance

Scope: the technical references that support implementation choices. This is not an exhaustive literature review or a prior-art search. Recheck references that may change before relying on them.

## Internal sources

- [SPECIFICATION.md](../SPECIFICATION.md): the v0.1 design, published in English with unchanged requirement, invariant and test identifiers. A documentation check pins its fingerprint.
- [JSON contracts](../contracts/): the two initial schemas are kept unchanged and seven were added in PL-02. [Examples](../examples/) are synthetic, with historical dates and fictitious evidence.
- [Prompts](../prompts/): preparatory role contracts, without an active runtime.
- Local state and reproducible checks: [VALIDATION.md](../VALIDATION.md). No evidence of a connected director, power loss or strategic usefulness is available.

## External references

| Ref. | Primary source | What it supports | What it does not establish |
|---|---|---|---|
| S1 | [Google Research — AI co-scientist](https://research.google/blog/accelerating-scientific-breakthroughs-with-an-ai-co-scientist/) | A supervisor allocating tasks and resources exists | PrincipalLoop's novelty or performance |
| S2 | [Anthropic — Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps) | Role separation and an evaluator whose value depends on task and model | A universal need for a director |
| S3 | [OpenAI — Codex App Server](https://learn.chatgpt.com/docs/app-server) | Documented steering and interruption methods; the specification's older URL redirects here | Local runner capabilities or cancellation of external effects |
| S4 | [LangChain — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) | Resumption may re-execute effects that preceded the interruption; idempotency is needed | Exactly-once delivery for every tool |
| S5 | [SQLite — Write-Ahead Logging](https://www.sqlite.org/wal.html) | Local WAL, one writer at a time, checkpoint constraints and the WAL-reset bug fixes | Qualification of this project's runtime |
| S6 | [SQLite — Atomic Commit](https://www.sqlite.org/atomiccommit.html) | Hardware assumptions and commit in rollback mode; WAL uses a different mechanism | Proof that PrincipalLoop survives a power loss |
| S7 | [Anthropic — Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | Progress artifacts used between sessions | Effectiveness of the proposed strategic supervision |
| S8 | [python-jsonschema — Schema Validation](https://python-jsonschema.readthedocs.io/en/stable/validate/) | Explicit activation of format checks and their dependencies | Validation of business policies by JSON Schema |

S5 mentions a fix in SQLite 3.51.3 and backports in 3.44.6 and 3.50.7. SQLite 3.50.4, for example, does not carry the fix. Check the fix for the branch actually used; never rely on a global "version ≥ 3.44.6" comparison.

Cadence parameters, thresholds, diagrams, tickets and protocol choices in the complementary documents are PrincipalLoop proposals. They are not attributed to any vendor.

## Storage references (PL-03)

[Python 3.13 — sqlite3](https://docs.python.org/3.13/library/sqlite3.html) for explicit transactions, read-only mode and the backup API; [SQLite — locking](https://www.sqlite.org/lockingv3.html) for database locks; [SQLite WAL](https://www.sqlite.org/wal.html) for local storage constraints. PrincipalLoop's lifetime lock is added on top of SQLite's transactional lock; its limits are described in [STORAGE.md](STORAGE.md).

## Build references (PL-01 and PL-02)

[Installing Python with uv](https://docs.astral.sh/uv/guides/install-python/), [uv environment variables](https://docs.astral.sh/uv/reference/environment/), [build constraints and cache keys](https://docs.astral.sh/uv/reference/settings/), [CPython 3.13.16](https://www.python.org/downloads/release/python-31316/) and [Hatch file inclusion](https://hatch.pypa.io/latest/config/build/). They justify the commands and packaging. The effective runtime qualification comes from executed checks, not from vendor documentation alone.

## Snapshot references (PL-04)

- [SQLite — Making Other Kinds Of Table Schema Changes](https://www.sqlite.org/lang_altertable.html): the official table rebuild procedure, used to extend the journal in migration 2, with a foreign-key check.
- [Python 3.13 — os.open](https://docs.python.org/3.13/library/os.html#os.open): open primitives and metadata; these checks are not a global file-system freeze.
- [W3C — Contrast Minimum](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html): contrast criteria used for the base colors. The report also honors forced system colors; no full WCAG audit is claimed.
- [SQLite — File control opcodes](https://sqlite.org/c3ref/c_fcntl_begin_atomic_write.html) and [Memory-Mapped I/O](https://www.sqlite.org/mmap.html): context on Windows specifics. They do not identify the precise cause of the transient error observed after a kill; the bounded recovery decision rests on local runs documented in VALIDATION.md.

## Codex integration (CX-01 and CX-02)

- [Codex MCP](https://learn.chatgpt.com/docs/extend/mcp?surface=cli): STDIO servers, trusted-project configuration and reloading. Does not prove that an already open chat is connected.
- [Codex skills](https://learn.chatgpt.com/docs/build-skills): discovery and invocation. Does not guarantee that a model follows every instruction.
- [Codex App Server](https://learn.chatgpt.com/docs/app-server): initialization, ephemeral threads, inventory and MCP calls. The qualification sends no `turn/start`.
- [MCP — transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports), [lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle), [tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools): normative rules for the tools-only transport delivered here. Not a general conformance certification.
- [Codex — Package your plugin](https://developers.openai.com/plugins/build/plugins) and [Submission](https://developers.openai.com/plugins/deploy/submission): `.codex-plugin/plugin.json`, `.mcp.json`, `skills/` and the `.agents/plugins/marketplace.json` catalog. Does not establish a future directory listing.
- [plugin.json and marketplace.json specification](https://github.com/openai/skills/blob/main/skills/.system/plugin-creator/references/plugin-json-spec.md): manifest and catalog entry fields, default prompt limits and image paths.
- Source code of [openai/codex](https://github.com/openai/codex), consulted November 10, 2026: `codex-mcp/src/plugin_config.rs` (reading `.mcp.json`), `rmcp-client/src/stdio_server_launcher.rs` (default start directory), `codex-mcp/src/sandbox_metadata.rs` (the `codex/sandbox-state` capability). These are implementation facts to recheck for every version, not a stable contract.
- Local runs: the `codex plugin` CLI and the App Server of Codex 0.166.0 (npm) and 0.167.0-alpha.3.2 (desktop app), recorded in the [CX-02 report](reports/cx02-codex-windows.json).
