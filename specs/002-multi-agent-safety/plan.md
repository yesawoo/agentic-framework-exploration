# Implementation Plan: Multi-Agent and Safe Interaction

**Branch**: `001-agent-framework-comparison` | **Date**: 2026-09-30 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-multi-agent-safety/spec.md`

**Predecessor plan**: [../001-core-pr-steward/plan.md](../001-core-pr-steward/plan.md) holds the shared technical context (full dependency list, infrastructure layout, storage, testing tiers, risks R1-R13). This plan does not copy it; it restates only what a reader needs to work from this spec alone and lists what changes.

## Summary

On top of the single-agent loop and hosting from spec 001, add to each of the four implementations: a coordinator with three specialists and a delegation trace (US4); reliability and hostile-input handling, including a per-kind dedupe key, backoff, resume, and a Postgres `SessionStore` for the Claude Agent SDK (US5); a human approval gate over a PR comment (US6); and a conversational `@steward` trigger with streamed progress and `POST /chat/stream` (US7). Everything about how each agent delegates, suspends, resumes, and streams is written in the framework's own idiom and is not shared. Shared code is limited to one new migration (`0003`), the conformance tests and stub scenarios, and two contract additions.

Technical approach (alternatives in [research.md](research.md)):

- **Multi-agent**: one coordinator and three specialists (summarizer, risk/security, test-coverage) per framework, using its native delegation (LangGraph subagents-as-tools with `Send` fan-out, Claude Agent SDK `AgentDefinition` subagents, Pydantic AI agent-as-tool with `usage=ctx.usage`, Mastra supervisor `agents`). Findings are structured (`severity` in info|low|medium|high) and merged into `reviews`/`findings`; disagreements and missing perspectives are explicit; every hop is a `run_steps` row.
- **Reliability**: the worker dedupe key becomes `(delivery_id, kind)` (research D5a, amends D5) so one delivery can produce `pr_summary` and `pr_review`; backoff for model/GitHub/tool-server errors; resume through native durability (LangGraph Postgres checkpointer, Mastra `@mastra/pg` snapshots, Claude Agent SDK `SessionStore`, Pydantic AI message history with idempotent tools); `limit_exceeded` is terminal and not retried.
- **Safety**: PR content is delimited and treated as data, a secret scrubber runs on every output, log line, and tool-server payload, and each run has a tool allowlist.
- **Approval** (research D10): proposed comment stored as an approval request; owner replies `/approve <id>` or `/reject <id>`; 24 hour expiry through the existing `approval_sweep` schedule; each framework suspends with its native mechanism.
- **Streaming** (research D11): `@steward` comments run through the same queue; progress edits one PR comment at most every 2 seconds; `POST /chat/stream` exposes the framework's native stream shape as SSE.

## Technical Context

Delta against spec 001; the rest is inherited.

**Language/Version**: Python 3.13 (LangGraph, Claude Agent SDK, Pydantic AI, shared harness, `shared/db`); TypeScript on Node 22 LTS, `tsc` strict (Mastra). No new language or runtime.

**Primary Dependencies**: no new packages are planned. Uses the pins from spec 001 (verified 2026-09-28): `langgraph` 1.2.x with `langgraph-checkpoint-postgres`; `claude-agent-sdk` 0.2.x (Bedrock mode); `@mastra/core` 1.x with `@mastra/pg`; `pydantic-ai` 2.x with `pydantic-graph`. Any dependency this spec adds (for example an SSE helper) is justified in the task that adds it and recorded in the component `CLAUDE.md` (Constitution VII).

**Model provider**: Amazon Bedrock for every model call in all four frameworks (spec FR-023); Claude Sonnet 5.5 for agents, Opus 5.5 for the judge, Haiku 4.5 for helpers; access through each ECS task role, no model API key, no Anthropic API fallback. Global inference-profile IDs are pinned by spec 001's spike S12 and read from `BEDROCK_MODEL_*`. **Region**: `us-east-1` for all infrastructure and `BEDROCK_REGION` (research D6a of spec 001).

**Storage**: the Aurora Serverless v2 database from spec 001. New tables `reviews`, `findings`, `approval_requests` and a change to the `events` dedupe key, in migration `0003` ([data-model.md](data-model.md)). Framework-owned tables (LangGraph checkpoints, Mastra workflow snapshots, the Claude `SessionStore` table) are created by the frameworks or the adapter in the implementation's schema, as in 001.

**Testing**: `pytest` and Vitest as in 001; contract-tier tests against the stub Bedrock and stub GitHub servers, so no model spend in CI; live tier is run by `just scenario` with owner approval.

**Target Platform**: unchanged (ECS Fargate behind ALB and CloudFront, local docker compose).

**Performance Goals**: webhook acknowledged within 2 s (unchanged); chat progress comment edited at most every 2 s; review duration and cost recorded per run, not optimized.

**Constraints**: no shared agent logic across frameworks; secrets never in the repo; live tasks that write to GitHub, spend on models, or apply infrastructure need owner approval; the core review (FR-007) MUST NOT depend on cross-framework calls.

**Scale/Scope**: one test repository; low traffic; four implementations.

## Constitution Check

*GATE: Must pass before Phase 0 of tasks. Re-check after reconciliation.* Constitution v1.0.0 (`.specify/memory/constitution.md`), Principles I-IX.

| Principle | Status | How this spec satisfies it |
|---|---|---|
| I. Test Discipline | Pass | Contract-tier tests for US4-US7 in `shared/conformance/tests/`, unit tests per implementation, `ruff`/`tsc --noEmit` in CI; independent reproduction by CI and a second session per quickstart |
| II. Scripted, Reproducible Deployment | Pass | No new deploy path. Migration `0003` reaches AWS through the existing `just deploy` (migrate task rebuilt when the `shared/db` source digest changes). Live checks use `just deploy/smoke/scenario`; nothing is created by hand |
| III. Repository Conventions | Pass | Each touched component `CLAUDE.md` updated (T215); spikes under `specs/002-multi-agent-safety/spikes/`; temp files via `$TMPDIR` |
| IV. Infrastructure as Code | Pass | No infrastructure change planned. If reconciliation finds that 001's module lacks something this spec needs (for example the `approval_sweep` schedule or a queue visibility timeout for long reviews), the fix is an OpenTofu change with plan review, recorded in `reconciliation.md` |
| V. Security by Default | Pass | Untrusted-data delimiting and a secret scrubber (US5); owner-only approvals and commands; approval decisions authenticated by the GitHub webhook signature plus `OWNER_LOGIN`; no new secrets |
| VI. Observability by Default | Pass | Delegation and tool steps in `run_steps`; existing EMF metrics; each component `CLAUDE.md` documents what is logged, emitted, and alerted; approvals and reviews carry `run_id` |
| VII. Prefer Maintained Client Libraries | Pass | Frameworks' own delegation, interrupt/suspend/defer, and streaming APIs; PyGithub/Octokit for comments; official `mcp` SDK; no hand-rolled Bedrock wrapper |
| VIII. Verification from a Clean State | Pass | Quickstart begins by assuming spec 001's quickstart passes from clean state, then runs this spec's additions; commands and outputs recorded |
| IX. CI Before Completion | Pass with risk | Conformance workflow runs the new contract tests against every implementation on the branch; green run required (T216). Risk R2 (stub endpoint override) is inherited; where spec 001's spike S8 recorded a refused override for a framework, that framework's tests stub at the agent-tool boundary as documented in its `CLAUDE.md` |

Development Workflow: no agent logic shared beyond the contract, fixtures, tool server, and tests (satisfied); `quickstart.md` is executable.

**Post-design re-check**: Pass. Watch items: per-kind dedupe touches the same worker file in all four implementations (sequenced in tasks), and the Claude Agent SDK `SessionStore` must not store secrets in transcripts.

## Project Structure

### Documentation (this feature)

```text
specs/002-multi-agent-safety/
├── spec.md
├── plan.md                  # This file
├── research.md              # Decisions D5a, D10, D11, the multi-agent design note; spikes S5, S6 (part)
├── data-model.md            # Migration 0003: reviews, findings, approval_requests; events dedupe key
├── quickstart.md            # Assumes spec 001 quickstart passes; covers additions only
├── reconciliation.md        # Created by Phase 0 (stub with headings)
├── contracts/
│   ├── http-api-additions.yaml      # /chat/stream, /admin/approvals; extends spec 001 http-api.yaml
│   └── work-queue-amendments.md     # per-kind dedupe key, params for chat/approval kinds; extends spec 001 work-queue.md
├── checklists/requirements.md
├── spikes/                  # S5-claude-sdk-session.md (and S6 notes), written by tasks
└── tasks.md
```

### Source Code (repository root)

Only files added or changed by this spec are listed; the full tree is in spec 001's plan.

```text
implementations/<name>/src/steward/      # (mastra: src/*.ts)
├── webhook.py|.ts          # routing extended: pr_review, approval_decision, chat
├── worker.py|.ts           # per-kind dedupe; handlers registered: pr_review, approval_decision, approval_sweep, chat; backoff/resume/limits
├── agents/review.py|.ts    # coordinator + 3 specialists (US4)
├── safety.py|.ts           # untrusted-data delimiting, scrubber, tool allowlist (US5)
├── approvals.py|.ts        # approval flow (US6)
├── chat.py|.ts             # /chat/stream and @steward handler (US7)
├── admin.py|.ts            # + GET /admin/approvals
└── session_store.py        # claude-agent-sdk only (US5)
shared/
├── db/migrations/0003_multi_agent.sql
└── conformance/
    ├── stubs/stub_bedrock.py            # extended with scenarios
    ├── src/conformance/scenarios/       # multi_agent.py, approval.py, chat.py
    └── tests/                           # test_us4_multiagent.py, test_us5_*.py, test_us6_approval.py, test_us7_*.py
```

**Structure Decision**: unchanged from spec 001: one directory per concern, each implementation self-contained, no shared agent library. This spec adds files inside existing components only; it creates no new component and no new OpenTofu root.

## Phasing (input to `/speckit-tasks`)

0. **Reconcile with the completed predecessor** (T200-T206): verify 001 checkpoints, diff as-built against the "Depends on" list, decide the `0003` shape, update this spec's artifacts, `/speckit-analyze`. Nothing later starts before this is done.
1. **Foundational delta** (T207-T214): migration `0003`, db tests and compose, conformance client for the additions, per-kind dedupe and webhook routing in each implementation, dedupe test.
2. **US4** multi-agent review (T080-T086).
3. **US5** reliability and safety (T087-T097; the `SessionStore` first because US6 needs it for the Claude Agent SDK).
4. **US6** approval (T098-T103).
5. **US7** chat and streaming (T104-T109).
6. **Polish** (T215-T222): `CLAUDE.md`, green CI, contract-tier checkpoint, live and deployed checkpoint (owner approval), independent clean-state quickstart, Bedrock log append, handoff check, `/speckit-analyze`.

## Risks

Risk IDs continue the original numbering; R1-R13 in spec 001's plan apply where relevant (R1 API churn, R2 stub endpoint override, R3 Claude SDK subprocess and local sessions, R9 SSE through CloudFront, R13 Bedrock gaps).

| ID | Risk | Mitigation |
|---|---|---|
| R1 | Framework delegation and approval APIs are churning (Mastra supervisor migration, Pydantic AI V2, LangChain middleware); docs go stale | Pin versions, verify against current docs, record churn as a report finding |
| R3 | Claude Agent SDK subagents multiply the subprocess memory footprint; sessions are local by default | Postgres `SessionStore` (T089, spike S5); sizing from spec 001 spike S10 re-checked with the review workload (T218) |
| R9 | SSE could be buffered by CloudFront plus ALB | T105 tests SSE through the edge; fallback in spec 001 R9 (direct ALB HTTPS with owner domain) |
| R13 | Bedrock gaps hit this spec: no structured outputs (B2) so specialist findings use tool-call output; count-tokens absent (B6); Claude SDK Bedrock hang report (B11) around subagents | Record per framework in spec 001 research §6 (T220); never route to the Anthropic API |
| R14 | Changing the dedupe key rewrites the `events` primary key in a live database that already holds 001 data | Migration `0003` is additive-then-swap in one transaction with a default kind for existing rows; verified in db tests and on the deployed schema (T208, T218) |
| R15 | Predecessor drift: 001 as built differs from the "Depends on" list (worker structure, enums, contract paths) | Phase 0 reconcile with `reconciliation.md`; this spec is updated to match, not 001, unless 001 has a blocking defect |
| R16 | Approval resume needs run state to outlive 24 hours (Claude SDK sessions, Mastra snapshots, LangGraph checkpoints) | Durable Postgres-backed state per framework; expiry tested through `approval_sweep`; `waiting_approval` runs excluded from `abandoned` sweeps |

## Complexity Tracking

No constitution violations to justify. The additions that might look like extra complexity, each required: the per-kind dedupe key (FR-010 with two work items per delivery), a Postgres `SessionStore` for one framework (FR-013 and approvals up to 24 hours; SDK default is local disk), and stub scenarios for scripted multi-agent behavior (conformance in CI without model spend, Principle IX).
