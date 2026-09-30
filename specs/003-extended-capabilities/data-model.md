# Data Model: Extended Agent Capabilities

**Spec**: [spec.md](spec.md) | **Research**: [research.md](research.md) | **Base model**: spec 001 `data-model.md` (tables from migration `0001`/`0002`) and spec 002 `data-model.md` (migration `0003`)

This spec introduces three per-implementation tables in **migration `0004_extended_tables.sql`**, applied per implementation schema (`langgraph`, `claude_agent_sdk`, `mastra`, `pydantic_ai`) by the `shared/db` migrate runner after `0001` and `0003`. The original single migration `0001` is not edited. The rules of spec 001's data model apply unchanged: one Postgres instance, a schema per implementation, column types indicative, `id` values UUIDs unless noted, UTC timestamps, and framework storage (memory internals, checkpoints) living beside these tables and not specified here.

## Tables introduced by this spec

### `memory_facts` (Memory Fact; for implementations whose framework store does not expose this shape, this table is the admin-facing view, kept in sync)
`id`, `statement`, `source_repo`, `source_pr`, `source_ref` (comment/thread url), `learned_at`, `status` (`active|corrected|deleted`), `superseded_by`, `use_count`, `last_used_at`. Cap: `MEMORY_MAX_FACTS` active facts (default 200); eviction removes least-recently-used. Statements are secret-scrubbed on write and flagged `untrusted=true` on reuse (FR-045, FR-014). Contradictory facts are resolved by recency, with the source shown (T125 test). `DELETE /admin/memory/{fact_id}` sets `status='deleted'`; a deleted or corrected fact is never returned to the agent on the next run (FR-044).

### `tool_grants` (Tool Grant)
`tool_name`, `policy` (`allowed|requires_approval|denied`), `load_mode` (`initial|on_demand`), `group`. Loaded from `TOOL_GRANTS_FILE` at startup. Every load is written as a `run_steps` row with `kind='tool_load'`, and every refusal as a `run_steps` row with `outcome='refused'` (FR-034, FR-035). A `requires_approval` call creates an `approval_requests` row through the spec 002 flow.

### `sandbox_runs` (Sandbox Run; only where supported, FR-036)
`id`, `run_id`, `command`, `limits` (cpu/mem/time), `exit_code`, `output_excerpt`, `outcome` (`passed|failed|cut_off`). No secret is injected into the sandbox; `output_excerpt` is secret-scrubbed and size-bounded (`SANDBOX_MAX_OUTPUT_BYTES`).

## Constraints required in `0004` (checked by the `shared/db` CI test against this document)

- `memory_facts.status` in (`active`,`corrected`,`deleted`); at most `MEMORY_MAX_FACTS` active rows enforced by the application write path (the schema documents the default 200).
- `tool_grants.policy` in (`allowed`,`requires_approval`,`denied`); `tool_grants.load_mode` in (`initial`,`on_demand`).
- `sandbox_runs.outcome` in (`passed`,`failed`,`cut_off`); `sandbox_runs.run_id` references `agent_runs.id`.

## Tables and fields used but owned by predecessors

- `pr_summaries.sources` (Context Sources, JSON array) and `pr_summaries.condensed` (bool + note): spec 001. Written by retrieval (US10) and long-context handling (US15).
- `run_steps` kinds `retrieval`, `tool_load`, `memory_read`, `memory_write`, `delegation`, `delegation_result`, with `framework` set for cross-framework hops, and `outcome` in `ok|error|refused|timeout`: spec 001 (migration `0001` check constraints). If Phase 0 finds any value missing, a task adds an ALTER to `0004` and records a deviation.
- `agent_runs.kind = 'mcp_summarize'` with `work_item_id` NULL: spec 001. `summarize_pr` (US11) writes these rows.
- `reviews`, `findings`, `approval_requests`: spec 002 (`0003`). A2A findings are stored with `findings.framework` set to the remote's framework; `requires_approval` tool grants create `approval_requests`.
- `digests`: spec 001; read by `get_latest_digest`.

`context_sources` is not a table: it is held inline as JSON on `pr_summaries.sources` and `run_steps.detail` (`{path|pr, ref, why}`).

## Conformance artifacts added by this spec (files, not database)

Added under `shared/conformance/fixtures/<id>/` (same layout as spec 001: `pr.json`, `context/`, `expected.yaml`, `tags`):

- `memory-convention-a` and `memory-convention-b`: a two-run pair. In `a` a thread states a convention; `b` is a later, unrelated PR that touches it. Tags: `memory-convention`.
- `injected-convention`: PR content that tries to plant a false convention in memory. Tags: `injection`, `injected-convention`.
- `failing-test`: a PR with a failing test, plus variants that try to read secrets or reach internal hosts and one that produces unbounded output or never ends. Tags: `failing-test`, `sandbox`.
- `retrieval-injection`: a `context/` file containing instructions aimed at the agent. Tags: `needs-context`, `injection`.

Fixtures `needs-context`, `oversized-diff`, and `large-diff` come from spec 001. The eval report file format is spec 004's (`contracts/eval-report.schema.json` there).
