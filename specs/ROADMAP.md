# Agent Framework Comparison: Roadmap

The evaluator wants to judge four agent frameworks (LangGraph, Claude Agent SDK, Mastra, Pydantic AI) by building the same "PR steward" agent four times against one shared behavioral contract, deploying each to AWS, and comparing them. The single original spec (`001-agent-framework-comparison`, 15 user stories, 57 FRs, 174 tasks) was too large to analyze or implement, so it is now four specs built **one after another**. The original stays in git history (commit 9582882).

## Sequence

| # | Spec | Delivers | Original scope |
|---|---|---|---|
| 001 | [core-pr-steward](001-core-pr-steward/spec.md) | Webhook -> summary -> MCP tool server in all four frameworks; hosted on AWS with OpenTofu; daily digest; `up`/`down`/`pause`/`resume`/`status` | US1, US2, US3 |
| 002 | [multi-agent-safety](002-multi-agent-safety/spec.md) | Coordinator + specialists review; reliability and untrusted-input handling; human approval; conversational trigger with streaming | US4, US5, US6, US7 |
| 003 | [extended-capabilities](003-extended-capabilities/spec.md) | Repo retrieval; agent as MCP server; dynamic tools and permissions; long-context and memory; sandbox (optional); cross-framework A2A | US10, US11, US12, US15, US13, US14 |
| 004 | [evaluation-report](004-evaluation-report/spec.md) | Observability, cost and quality evaluation across everything built; the comparison report and Taskrabbit recommendation | US8, US9 |

Original FR, SC, US, task (T), spike (S) and decision (D) IDs are preserved across all four specs, so anything can be traced back to the original.

## How the specs chain (reconciliation)

Spec N+1 does not assume spec N was built exactly as written. Each of 002-004 starts with **Phase 0: Reconcile with the completed predecessor**:

1. Confirm the predecessor's checkpoint tasks are checked and its as-built deviations are recorded.
2. Diff the as-built code, contracts, and schema against this spec's "Depends on / Inherited from predecessors" list; record the result in `reconciliation.md` (Verified, Deviations found, Changes made, Open questions).
3. Update this spec's `spec.md`, `plan.md`, `tasks.md`, and contracts to match reality.
4. Run `/speckit-analyze` on the updated spec.

No story phase starts until Phase 0 is done. Work each spec on its own branch, created when the spec starts, from the tip of the previous spec's merged work.

## Decisions that hold across all four (do not reopen)

- Amazon Bedrock only for every model call; no Anthropic API fallback. Region `us-east-1` for infrastructure and `BEDROCK_REGION`. The S12 spike uses the owner's own AWS profile.
- No shared agent logic across frameworks; shared code is limited to contract, fixtures, DB migrations, stubs, tool server, conformance harness, and OpenTofu modules.
- Migrations run as a one-shot ECS migrate task defined in `infra/durable`. Each spec adds its own migration file.
- `destroy-all` leaves no snapshot unless `KEEP_FINAL_SNAPSHOT=1`, which `verify-clean` reports as a declared exception.
- The constitution (`.specify/memory/constitution.md`, v1.0.0) wins over any other guidance.
- Anything that spends money, writes to GitHub, or creates AWS resources needs explicit owner approval.

## Findings resolved by the split

- P3-01: condensed-summary check moved to 003; tool-server retry check moved to 002.
- P3-02: 002 defines a distinct dedupe key per work-item kind (001 dedupes `pr_summary` on `delivery_id` only).
- X03: `destroy-all` now force-deletes ECR repos and the artifacts bucket (001).

## Deferred on purpose (carried from the original analysis)

smoke `POST /internal/schedule` side effects; SNS subscription; digest "yesterday" backdating; SC-001/002 trial counts; quickstart scenarios without tasks; PAT scopes; FR-042 long-thread test; judge Bedrock client; digest `subject_key` normalization. The roughly 43 MEDIUM findings from the last per-phase analysis were never fixed or saved; rerun `/speckit-analyze` per spec instead.
