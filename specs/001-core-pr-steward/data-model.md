# Data Model: Core PR Steward

**Spec**: [spec.md](spec.md) | **Research**: [research.md](research.md)

Storage is one Postgres instance with a schema per implementation (`langgraph`, `claude_agent_sdk`, `mastra`, `pydantic_ai`) plus `toolserver`. The tables below are the **contract-level** shape every implementation MUST provide so the conformance harness can query them identically. Frameworks' own storage (checkpoints, memory internals) lives beside these tables in the same schema and is not specified here.

Column types are indicative; `id` values are UUIDs unless noted. All timestamps are UTC.

## Migrations

Migrations are numbered files in `shared/db/migrations/`, each starting with a `-- target: implementation` or `-- target: toolserver` header. The `shared/db` runner applies only pending files for the target schema and records them in `<schema>.schema_migrations`.

| File | Target | Owner | Tables |
|---|---|---|---|
| `0001_contract_tables.sql` | implementation schemas | this spec (001) | `events`, `work_items`, `pr_summaries`, `digests`, `agent_runs`, `run_steps` |
| `0002_toolserver.sql` | `toolserver` | this spec (001) | `records`, `calls` |
| `0003` | implementation schemas | spec 002 | `reviews`, `findings`, `approval_requests`, plus the per-kind dedupe change to `events` |
| `0004` | implementation schemas | spec 003 | `memory_facts`, `tool_grants`, `sandbox_runs` |

Spec 004 adds any evaluation tables it needs in a later numbered file. The enumerations that name later specs' kinds (`work_items.kind`, `agent_runs.kind`, `run_steps.kind`) are declared in full in `0001`, so later migrations add tables and never change these enums.

## Per-implementation tables (migration 0001)

### `events` (Pull Request Event; dedupe unit; written by the worker, not the webhook handler, because the database may be paused)
| Field | Notes |
|---|---|
| `delivery_id` (PK, text) | GitHub `X-GitHub-Delivery`; unique constraint enforces at-most-once (FR-010) |
| `event_type`, `action` | e.g. `pull_request` / `opened`, `issue_comment` / `created` |
| `repo`, `pr_number` | nullable for non-PR events |
| `received_at`, `status` | `accepted` -> `enqueued` -> `done` / `failed` / `ignored` |
| `payload_sha256` | for audit; the payload itself is not stored (secrets/PII, FR-021) |

State: the worker inserts the row with `accepted` on first sight of a `delivery_id` (`ON CONFLICT DO NOTHING`), sets `enqueued` once it has created the work item, then `done`, `failed`, or `ignored`. A redelivery with an existing `delivery_id` was already answered 202 by the webhook handler (which never reads the database); the worker's insert conflicts, so it drops the message and changes nothing.

Dedupe key note: `delivery_id` alone is the primary key in this spec. That is sufficient only because `pr_summary` is the only work-item kind created from a webhook delivery. Spec 002 creates `pr_review` from the same delivery and MUST replace the key with one per work-item kind (for example `(delivery_id, kind)`) in migration 0003 and change the worker accordingly.

### `work_items` (mirror of the SQS message for traceability)
`id`, `kind` (`pr_summary`, `pr_review`, `digest`, `chat`, `approval_sweep`, `approval_decision`; only `pr_summary` and `digest` are created in this spec), `subject_key` (idempotency key, e.g. `pr:owner/repo#12@<head_sha>` or `digest:2026-09-27`), `event_delivery_id` (nullable), `attempts`, `status`, `enqueued_at`, `finished_at`. `(kind, subject_key)` is unique for kinds that must not repeat (summary per PR head sha, digest per day).

### `pr_summaries` (PR Summary)
`id`, `repo`, `pr_number`, `head_sha`, `summary_text`, `sources` (Context Sources, JSON array), `condensed` (bool + note), `run_id`, `tool_server_record_id`, `created_at`. Unique `(repo, pr_number, head_sha)` -> edits to the same head do not duplicate (User Story 1 scenario 3).

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
`id`, `run_id`, `seq`, `kind` (`model_call`, `tool_call`, `tool_load`, `delegation`, `delegation_result`, `memory_read`, `memory_write`, `retrieval`), `agent`, `parent_agent`, `framework` (for cross-framework hops), `name` (tool/agent), `started_at`, `duration_ms`, `input_tokens`, `output_tokens`, `outcome` (`ok`, `error`, `refused`, `timeout`; declared in 0001 so later specs add no ALTER), `detail` (scrubbed JSON). This is what "who delegated what to whom" (FR-007) and tool-load records (FR-034) are read from.

In this spec only `model_call` and `tool_call` steps are written; the other kinds are written by specs 002 (`delegation`, `delegation_result`) and 003 (`tool_load`, `memory_read`, `memory_write`, `retrieval`). `run_steps.detail` is where context sources (spec 003) will live as inline JSON; there is no separate table.

## `toolserver` schema (Tool Server Record)
`records`: `id`, `kind` (`pr_summary|review|digest`), `implementation` (required label), `repo`, `pr_number` (nullable), `digest_date` (nullable), `head_sha` (nullable; set for `pr_summary`/`review`), `payload` (JSON), `payload_sha256`, `received_at`. Unique `(kind, implementation, repo, pr_number, head_sha)` and `(kind, implementation, repo, digest_date)` -> idempotent tool calls (FR-010).
`calls`: `id`, `tool`, `implementation`, `client_info` (MCP client name/version), `duration_ms`, `outcome`, `received_at` (the record of how each framework's MCP client behaved; input to the MCP evaluation in the report).

## Tables owned by later specs (not created here)

- Spec 002: `reviews`, `findings` (Consolidated Review, Review Finding), `approval_requests` (Approval Request).
- Spec 003: `memory_facts`, `tool_grants`, `sandbox_runs`.
- Context Source is held inline (`pr_summaries.sources`, `run_steps.detail`), not a table.

## Conformance artifacts (files, not database)

- **Fixture PR** (`shared/conformance/fixtures/<id>/`): `pr.json` (metadata, files, diff), `context/` (repo files, used from spec 003), `expected.yaml` (properties: must-mention topics, must-flag findings, forbidden content, expected sources), `tags` (`oversized`, `injection`, `risky`, `no-tests`, `binary-only`, `needs-context`). This spec provides `basic-feature`, `large-diff`, `binary-only`, `bot-author`, `draft-pr`; later specs add the rest with the same loader.
- The eval report and the comparison report are owned by spec 004.
