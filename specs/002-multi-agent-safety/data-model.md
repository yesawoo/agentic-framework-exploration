# Data Model: Multi-Agent and Safe Interaction

**Spec**: [spec.md](spec.md) | **Research**: [research.md](research.md) | **Predecessor**: [../001-core-pr-steward/data-model.md](../001-core-pr-steward/data-model.md)

Storage is the Postgres instance from spec 001 with a schema per implementation (`langgraph`, `claude_agent_sdk`, `mastra`, `pydantic_ai`) plus `toolserver`. This spec introduces the tables below in **migration `0003_multi_agent.sql`**, applied to each implementation schema by the `shared/db` migrate runner (locally by the compose `migrate` service, on AWS by the durable one-shot migrate task). Tables from `0001` and `0002` (events, work_items, pr_summaries, digests, agent_runs, run_steps, and the `toolserver` schema) are owned by spec 001 and are not restated except where `0003` changes them. Migration `0004` (memory_facts, tool_grants, sandbox_runs, context_sources) belongs to spec 003.

Column types are indicative; `id` values are UUIDs unless noted. All timestamps are UTC.

## New tables (per implementation schema)

### `reviews` (Consolidated Review)
`id`, `repo`, `pr_number`, `head_sha`, `coordinator`, `missing_perspectives` (JSON array), `disagreements` (JSON array), `run_id` (references `agent_runs.id`), `created_at`. Unique `(repo, pr_number, head_sha)` so a redelivered or retried review does not duplicate (the tool server enforces the same natural key with `(implementation, repo, pr_number, head_sha)`).

### `findings` (Review Finding)
`id`, `review_id` (references `reviews.id`), `agent` (`summarizer` / `risk` / `tests` / remote name), `framework` (for cross-framework findings, populated by spec 003; null or the local framework name for in-framework specialists), `topic`, `severity` (`info|low|medium|high`), `evidence`, `created_at`.

### `approval_requests` (Approval Request)
`id`, `run_id`, `repo`, `pr_number`, `proposed_action` (`post_comment`), `proposed_body`, `status` (`pending|approved|rejected|expired`), `decided_by`, `created_at`, `decided_at`, `expires_at`, `posted_comment_id` (nullable text; the id of the comment the approval caused).

State: `pending` -> (`approved` | `rejected` | `expired`); `approved` triggers exactly one comment post, guarded by `posted_comment_id` set in the same transaction as the status change. (The original data model described this guard but omitted the column from the field list; it is listed here.) Only `OWNER_LOGIN` decisions are applied. `expires_at` is `created_at` plus 24 hours; the `approval_sweep` work item expires overdue rows.

## Changes to spec 001 tables (in `0003`)

### `events`: dedupe key becomes `(delivery_id, kind)` (research D5a)
- Add `kind` (text, not null; the work-item kind the row dedupes, e.g. `pr_summary`, `pr_review`, `chat`, `approval_decision`), defaulting to `pr_summary` for existing rows.
- Replace the primary key on `delivery_id` with a primary key or unique constraint on `(delivery_id, kind)`. Everything else about `events` is unchanged: the worker (not the webhook handler) inserts with `ON CONFLICT DO NOTHING` and drops the message on conflict; `status` flow `accepted` -> `enqueued` -> `done` / `failed` / `ignored`.
- The migration runs in one transaction and must be re-runnable against a schema that already holds spec 001 data.
- If the as-built 001 `events` shape differs (Phase 0, T203), the migration follows the as-built shape and this file is updated.

### Enum widening, only if Phase 0 finds `0001` too narrow
If a CHECK constraint in `0001` does not admit `work_items.kind` in (`pr_review`, `chat`, `approval_sweep`, `approval_decision`), `agent_runs.kind` in (`pr_review`, `chat`, `approval_sweep`, `approval_decision`), `agent_runs.status` in (`waiting_approval`, `limit_exceeded`, `abandoned`), or `run_steps.kind` in (`delegation`, `delegation_result`), `0003` widens it. The original single migration created all of these, so this is expected to be a no-op.

## `toolserver` schema

No change in this spec. `toolserver.records` already accepts `kind = review` with the unique `(kind, implementation, repo, pr_number, head_sha)` from spec 001's `0002`; `record_review` is exercised here.

## How the trace is stored (existing tables, used by this spec)

- Delegation trace: `run_steps` rows of kind `delegation` and `delegation_result` with `agent`, `parent_agent`, `framework` (null in-framework), `name`, `outcome` (`ok|error|refused|timeout`), scrubbed `detail`. This is what "who delegated what to whom" (FR-007) is read from through `GET /admin/runs/{id}`.
- Approvals: run status `waiting_approval` while pending; `approval_requests.run_id` links the request to the suspended run.
- Chat: `agent_runs.kind = 'chat'`; `work_items.kind = 'chat'`; conversation context is keyed by `thread_id` in framework-native storage (not a contract table in this spec).

## Conformance artifacts (files, not database)

- Fixtures used here (`risky-no-tests`, `prompt-injection`, `secret-in-diff`, and the multi-turn chat script) are created by spec 001 or added to `shared/conformance/fixtures/` by tasks in this spec; `expected.yaml` properties (must-flag findings, forbidden content) are the basis for the US4 and US5 assertions.
- Stub scenarios in `shared/conformance/stubs/stub_bedrock.py` are code, not data.
