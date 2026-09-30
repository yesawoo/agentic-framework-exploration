# Data Model: Agent Framework Comparison

**Spec**: [spec.md](spec.md) | **Research**: [research.md](research.md)

Storage is one Postgres instance with a schema per implementation (`langgraph`, `claude_agent_sdk`, `mastra`, `pydantic_ai`) plus `toolserver`. The tables below are the **contract-level** shape every implementation MUST provide so the conformance harness and report can query them identically. Frameworks' own storage (checkpoints, memory internals) lives beside these tables in the same schema and is not specified here.

Column types are indicative; `id` values are UUIDs unless noted. All timestamps are UTC.

## Per-implementation tables

### `events` (Pull Request Event; dedupe unit; written by the worker, not the webhook handler, because the database may be paused)
| Field | Notes |
|---|---|
| `delivery_id` (PK, text) | GitHub `X-GitHub-Delivery`; unique constraint enforces at-most-once (FR-010) |
| `event_type`, `action` | e.g. `pull_request` / `opened`, `issue_comment` / `created` |
| `repo`, `pr_number` | nullable for non-PR events |
| `received_at`, `status` | `accepted` -> `enqueued` -> `done` / `failed` / `ignored` |
| `payload_sha256` | for audit; the payload itself is not stored (secrets/PII, FR-021) |

State: the worker inserts the row with `accepted` on first sight of a `delivery_id` (`ON CONFLICT DO NOTHING`), sets `enqueued` once it has created the work item, then `done`, `failed`, or `ignored`. A redelivery with an existing `delivery_id` was already answered 202 by the webhook handler (which never reads the database); the worker's insert conflicts, so it drops the message and changes nothing.

### `work_items` (mirror of the SQS message for traceability)
`id`, `kind` (`pr_summary`, `pr_review`, `digest`, `chat`, `approval_sweep`, `approval_decision`), `subject_key` (idempotency key, e.g. `pr:owner/repo#12@<head_sha>` or `digest:2026-09-27`), `event_delivery_id` (nullable), `attempts`, `status`, `enqueued_at`, `finished_at`. `(kind, subject_key)` is unique for kinds that must not repeat (summary per PR head sha, digest per day).

### `pr_summaries` (PR Summary)
`id`, `repo`, `pr_number`, `head_sha`, `summary_text`, `sources` (Context Sources, JSON array), `condensed` (bool + note), `run_id`, `tool_server_record_id`, `created_at`. Unique `(repo, pr_number, head_sha)` -> edits to the same head do not duplicate (User Story 1 scenario 3).

### `reviews` (Consolidated Review) and `findings` (Review Finding)
`reviews`: `id`, `repo`, `pr_number`, `head_sha`, `coordinator`, `missing_perspectives` (JSON array), `disagreements` (JSON array), `run_id`, `created_at`.
`findings`: `id`, `review_id`, `agent` (`summarizer` / `risk` / `tests` / remote name), `framework` (for cross-framework), `topic`, `severity` (`info|low|medium|high`), `evidence`, `created_at`.

### `digests` (Daily Digest)
`id`, `digest_date` (date), `repo`, `github_issue_number`, `pr_numbers` (int[]), `run_id`, `published_at`. Unique `(digest_date, repo)`; the GitHub issue title is `Daily PR digest <YYYY-MM-DD> (<implementation>)` so a rerun finds and reuses it (User Story 3 scenario 3; assumption "Digest destination").

### `agent_runs` (Agent Run; the comparable source of truth)
| Field | Notes |
|---|---|
| `id` (PK) | also the `run_id` in logs and traces |
| `work_item_id`, `kind`, `implementation`, `framework_version` | `kind`: `pr_summary`, `pr_review`, `digest`, `chat`, `approval_sweep`, `approval_decision`, `mcp_summarize`. `work_item_id` is null only for `mcp_summarize` (started by an MCP call, no queue item). |
| `status` | `running`, `succeeded`, `failed`, `waiting_approval`, `limit_exceeded`, `abandoned` |
| `started_at`, `finished_at` | |
| `input_tokens`, `output_tokens`, `cache_read_tokens`, `est_cost_usd` | estimate, not billing (research §3) |
| `steps`, `model_calls`, `tool_calls` | counters |
| `limit_reason` | set when a step/time/spend limit ended the run (FR-016) |
| `error` | scrubbed |

### `run_steps` (delegation and tool trace)
`id`, `run_id`, `seq`, `kind` (`model_call`, `tool_call`, `tool_load`, `delegation`, `delegation_result`, `memory_read`, `memory_write`, `retrieval`), `agent`, `parent_agent`, `framework` (for cross-framework hops), `name` (tool/agent), `started_at`, `duration_ms`, `input_tokens`, `output_tokens`, `outcome`, `detail` (scrubbed JSON). This is what "who delegated what to whom" (FR-007) and tool-load records (FR-034) are read from.

### `approval_requests` (Approval Request)
`id`, `run_id`, `repo`, `pr_number`, `proposed_action` (`post_comment`), `proposed_body`, `status` (`pending|approved|rejected|expired`), `decided_by`, `created_at`, `decided_at`, `expires_at`. State: `pending` -> (`approved` | `rejected` | `expired`); `approved` triggers exactly one comment post (guarded by `posted_comment_id` set in the same transaction as the status change).

### `memory_facts` (Memory Fact; for implementations whose framework store does not expose this shape, this table is the admin-facing view, kept in sync)
`id`, `statement`, `source_repo`, `source_pr`, `source_ref` (comment/thread url), `learned_at`, `status` (`active|corrected|deleted`), `superseded_by`, `use_count`, `last_used_at`. Cap: 200 active facts; eviction removes least-recently-used. Statements are secret-scrubbed and flagged `untrusted=true` on reuse (FR-045, FR-014).

### `tool_grants` (Tool Grant)
`tool_name`, `policy` (`allowed|requires_approval|denied`), `load_mode` (`initial|on_demand`), `group`. Loaded from config at startup; every refusal is written as a `run_steps` row with `outcome='refused'` (FR-035).

### `sandbox_runs` (Sandbox Run; only where supported, FR-036)
`id`, `run_id`, `command`, `limits` (cpu/mem/time), `exit_code`, `output_excerpt`, `outcome` (`passed|failed|cut_off`).

### `context_sources` (Context Source)
Held inline as JSON on `pr_summaries.sources` and `run_steps.detail` (`{path|pr, ref, why}`), not a separate table.

## `toolserver` schema (Tool Server Record)
`records`: `id`, `kind` (`pr_summary|review|digest`), `implementation` (required label), `repo`, `pr_number` (nullable), `digest_date` (nullable), `head_sha` (nullable; set for `pr_summary`/`review`), `payload` (JSON), `payload_sha256`, `received_at`. Unique `(kind, implementation, repo, pr_number, head_sha)` and `(kind, implementation, repo, digest_date)` -> idempotent tool calls (FR-010).
`calls`: `id`, `tool`, `implementation`, `client_info` (MCP client name/version), `duration_ms`, `outcome`, `received_at` (the record of how each framework's MCP client behaved; input to the MCP evaluation in the report).

## Conformance/eval artifacts (files, not database)
- **Fixture PR** (`shared/conformance/fixtures/<id>/`): `pr.json` (metadata, files, diff), `context/` (repo files the agent may need for US10), `expected.yaml` (properties: must-mention topics, must-flag findings, forbidden content, expected sources), `tags` (`oversized`, `injection`, `risky`, `no-tests`, `binary-only`, `needs-context`).
- **Eval report** (`shared/conformance/reports/<impl>/<timestamp>.json`): per-fixture scores, latency, tokens, cost, tool-server delivery correctness, native-eval results (separate section per FR-050). Schema in [contracts/eval-report.schema.json](contracts/eval-report.schema.json).
- **Comparison Report / Suitability Criterion**: Markdown under `docs/report/` (see plan), not stored in the database.
