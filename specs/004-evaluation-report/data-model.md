# Data Model: Evaluation and Comparison Report

**Spec**: [spec.md](spec.md) | **Research**: [research.md](research.md)

## Tables introduced by this spec

None. Migration numbering is 0001 and 0002 from spec 001, 0003 from spec 002, 0004 from spec 003. Evaluation results are files, not rows, so no migration 0005 is planned. If Phase 0 reconciliation (T402) finds a needed table, it is added as `0005_*.sql` under `shared/db/migrations/`, documented here, and the schema/CI checks from spec 001 (T011 `db-ci.yml`) are extended in the same change.

## Tables read (owned elsewhere)

| Table | Owner | Read for |
|---|---|---|
| `agent_runs` | spec 001 | tokens, `est_cost_usd`, `steps`, `model_calls`, `tool_calls`, `limit_reason`, `status`, duration (cost and latency per fixture, SC-009) |
| `run_steps` | spec 001 | delegation and tool traces (multi-agent and tool-call evaluation), `tool_load`, `retrieval`, `memory_read`/`memory_write` |
| `pr_summaries`, `digests`, `events`, `work_items` | spec 001 | delivery correctness and linkage to `tool_server_record_id` |
| `reviews`, `findings` | spec 002 | multi-agent evaluation and finding attribution |
| `memory_facts`, `tool_grants`, `sandbox_runs` | spec 003 | capability evidence for the report |
| `toolserver.records`, `toolserver.calls` | spec 001 | delivery correctness per implementation; MCP client behavior per framework |

Column meanings are in `specs/001-core-pr-steward/data-model.md` (and the 002 and 003 data models for their tables).

## Artifacts (files, not database)

- **Fixture PR** (`shared/conformance/fixtures/<id>/`): `pr.json` (metadata, files, diff), `context/` (repo files the agent may need), `expected.yaml` (properties: must-mention topics, must-flag findings, forbidden content, expected sources), `tags` (`oversized`, `injection`, `risky`, `no-tests`, `binary-only`, `needs-context`). Created by spec 001 and extended by specs 002 and 003; this spec reads them and adds none unless a chapter needs one (recorded in `reconciliation.md`).
- **Eval report** (`shared/conformance/reports/<impl>/<timestamp>.json`): per-fixture scores, latency, tokens, cost, tool-server delivery correctness (`delivered`, `delivery_seconds`), and a separate `native_evals` section (tooling, results reference, seven FR-049 capabilities each with status and evidence path) per FR-050. Schema: [contracts/eval-report.schema.json](contracts/eval-report.schema.json). Every committed report records the `git_sha` of the revision under test.
- **Native eval result** (`shared/conformance/reports/<impl>/native-<timestamp>.json`): the framework's own eval output, referenced from `native_evals.results_ref`.
- **Comparison Report / Framework Scorecard / Suitability Criterion**: Markdown under `docs/report/` (see plan), not stored in the database. Report links are permalinks pinned to the tag `report-eval-1`.
- **Link verification record**: `docs/report/verification.md` (10-claim spot check, SC-019) and `docs/report/live-engagement.md` (T171).

## Validation rules

- Every report validates against the schema (`just report-check`); `implementation` is one of `langgraph`, `claude-agent-sdk`, `mastra`, `pydantic-ai`.
- `native_evals.capabilities` has all seven keys with `status` in `native|via_integration|manual|not_available` and a non-empty `evidence` path (SC-021).
- Scores `accuracy` and `coverage` are in [0, 1]; `injection_safe` and `secret_leak` are booleans or null.
