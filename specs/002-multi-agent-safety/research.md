# Research: Multi-Agent and Safe Interaction

**Date**: 2026-09-30 (facts verified 2026-09-28) | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Predecessor**: [../001-core-pr-steward/research.md](../001-core-pr-steward/research.md)

Only decisions and spikes owned by this spec are here, plus the rows of the framework capability matrix this spec exercises (copied so the spec reads alone). Decisions D1-D9, D12-D18 and spikes S1-S4, S7-S13 stay where the original put them (spec 001, 003, or 004). Framework facts come from research passes on 2026-09-28 against official docs, PyPI/npm, and GitHub. Page summaries were partly produced by a summarizer model, so exact signatures and class names MUST be re-checked against the linked pages when implementing. Anything not confirmed is marked **UNVERIFIED** and becomes a spike task rather than an assumption.

Legend: **N** = native, **I** = via integration/companion package, **M** = manual (we build it).

## 1. Framework capability matrix (rows this spec exercises)

Versions are those current on 2026-09-28; pin them in lockfiles (spec 001 owns the lockfiles).

| Capability (spec ref) | LangGraph (Python) | Claude Agent SDK (Python) | Mastra (TypeScript) | Pydantic AI (Python) |
|---|---|---|---|---|
| Packages | `langgraph` 1.2.12 (MIT), `langgraph-checkpoint-postgres` 3.1.2, `langchain` (`create_agent`) | `claude-agent-sdk` 0.2.161 (MIT); bundles a native Claude Code binary | `@mastra/core` 1.71.0 (Apache-2.0, `ee/` dirs proprietary), Node >= 22.13 | `pydantic-ai` 2.51.0 (V2 since 2026-06-23); companion `pydantic-ai-harness` 0.36.0 (0.x) |
| Multi-agent (FR-007) | **N**: subagents-as-tools, `Send` fan-out, subgraph streaming (`ns` path). `langgraph-supervisor` discouraged | **N**: `agents={...: AgentDefinition}`, parallel, `parent_tool_use_id`, `SubagentStart/Stop` hooks | **N**: supervisor `agents: {}` with `onDelegationStart/Complete`; sub-agent threads isolated | **N**: agent-as-tool + `usage=ctx.usage`; `pydantic-graph` parallel; Harness Subagents (**I**) |
| Durable execution / resume (FR-013) | **N**: Postgres checkpointer, resume by `thread_id` | **I/M**: `resume=session_id`; cross-host needs a `SessionStore` adapter (copy-in Postgres/S3 examples) | **N**: workflow `suspend()/resume()` snapshots in `@mastra/pg`; durable agents; multi-replica needs Redis | **I**: Temporal/DBOS/Prefect/Restate; Harness StepPersistence (0.x) |
| Human approval (FR-015) | **N**: `interrupt()` + `Command(resume)`; `HumanInTheLoopMiddleware` | **N**: `can_use_tool` callback; `PreToolUse` `defer` hook for out-of-process approval | **N**: `requireApproval`/`requireToolApproval`, needs persistent storage | **N**: `requires_approval` -> `DeferredToolRequests`, resume with `message_history` |
| Streaming (US7) | **N** streaming modes; SSE serving **M** | **N**: `include_partial_messages` (main agent only) | **N**: `agent.stream()`, `toAISdkStream()`; server SSE route format UNVERIFIED | **N**: `UIAdapter` SSE (AG-UI/Vercel AI) |
| Guardrails (FR-014) | **M** | **M** (hooks) | **N**: `PromptInjectionDetector`, `PIIDetector`, `SystemPromptScrubber`, `TokenCostControl` | **I**: Harness Guardrails + Prompt Injection Defender |
| Observability and limits (FR-016, FR-018) | `recursion_limit`, `ModelCallLimit/ToolCallLimit` middleware; OTel via `langsmith[otel]` (without LangSmith export UNVERIFIED) | **N**: `max_turns`, `max_budget_usd`, `total_cost_usd`; OTel from CLI subprocess (beta traces flag) | **N**: `@mastra/observability` tracing, token/cost auto | **N**: `UsageLimits` (request/tool-call/token/cost); Harness `SpendLimits` |
| Claude on Bedrock (FR-023; all **UNVERIFIED** until spike S12 of spec 001 is recorded) | `langchain-aws` `ChatBedrockConverse` (replaces `langchain-anthropic`) | Bedrock mode via `CLAUDE_CODE_USE_BEDROCK`; tool search and other first-party-only features may be unavailable | AI SDK Amazon Bedrock provider (replaces `anthropic/<model>` strings); caching via `providerOptions` | `pydantic-ai-slim[bedrock]`; `AnthropicCompaction` and provider-side code execution are Anthropic-API features, likely unavailable |

The spec 001 S12 and S8 records supersede the "UNVERIFIED" Bedrock row; Phase 0 (T202) copies the as-built facts here if they differ.

## 2. Decisions

### D5a. Dedupe key per work-item kind (amends D5 of spec 001)
- **Decision**: The worker's first step remains an insert into the `events` table with retry on connection while the database resumes, but the dedupe unit is `(delivery_id, kind)`, not `delivery_id` alone. `events` gains a `kind` column and its primary key becomes `(delivery_id, kind)` (migration `0003`). The webhook handler still never touches the database and still enqueues one work item per handled kind; the worker drops a message whose `(delivery_id, kind)` already exists. Work items keep the existing unique `(kind, subject_key)`. Kinds with no natural delivery (`digest`, `approval_sweep` from EventBridge) have no GitHub delivery id; the original data model does not say how the worker's `events` insert treats them (`work_items.event_delivery_id` is nullable, `events.delivery_id` is a primary key). Phase 0 (T203) records how 001 handled this; this spec follows the as-built behavior and only defines the key for the kinds it adds.
- **Rationale**: Spec 001 dedupes `pr_summary` on `delivery_id` alone. One `pull_request` delivery now yields both a `pr_summary` and a `pr_review`; with the old key the worker would drop the second as a duplicate. FR-010 requires at-most-once per distinct notification and work item, not one work item per delivery. Making `kind` part of the key keeps redelivery idempotent for each kind (User Story 5 scenarios 2 and 7).
- **Alternatives**: a separate dedupe table (rejected: adds a table for a one-column change and splits the "what happened to this delivery" record); keeping `delivery_id` as key and having the webhook enqueue a single work item that fans out to summary and review in the worker (rejected: hides the two work kinds from the queue, alarms and run records that already key on kind); suffixing `delivery_id` with the kind in the same column (rejected: breaks the "unique GitHub delivery id" audit meaning).
- **Reconcile**: the actual shape 001 shipped decides the exact migration; T203 records it, T207 writes the migration, T210-T213 change each worker, T214 tests it. Proposed `subject_key` forms for kinds the original left undefined (`chat`, `approval_decision`, `approval_sweep`) are in `contracts/work-queue-amendments.md`.

### D10. Approval mechanism (FR-015)
- **Decision**: The proposed PR comment is stored as an `ApprovalRequest`; the agent posts a "pending approval" comment; the owner approves or rejects by replying `/approve <id>` or `/reject <id>` on the PR (`issue_comment` webhook). Requests expire after 24 hours via a scheduled sweep (uniform EventBridge rule, `approval_sweep`, created by spec 001's implementation module). Each framework suspends its run with its native mechanism (LangGraph `interrupt`, Mastra `suspend`, Pydantic AI `DeferredToolRequests`, Claude SDK `defer` hook + resumed session).
- **Rationale**: Uses only GitHub and existing webhook plumbing; no extra UI.
- **Alternatives**: Slack buttons (rejected: extra account).
- **Notes carried into tasks**: `approved` triggers exactly one comment post, guarded by `posted_comment_id` set in the same transaction as the status change (data-model.md). The run is `waiting_approval` while pending and is not swept as `abandoned`. Only `OWNER_LOGIN` decisions count; other authors' `/approve` comments are ignored.

### D11. Streaming and conversation (US7)
- **Decision**: `@steward` comment commands are handled through the same queue; progress is streamed by editing one PR comment at most every 2 seconds, and every implementation also exposes `POST /chat/stream` (SSE) for direct inspection. Only the repository owner may command (FR-017).
- **Rationale**: GitHub has no streaming primitive; edit-in-place is the practical equivalent, and the SSE endpoint exposes each framework's native stream shape.
- **Notes carried into tasks**: SSE event names are `progress`, `delta`, `tool`, `final`, `error`, each with `run_id`; `thread_id` is at most 200 characters and keys the conversation context. Whether the SSE stream survives CloudFront and the ALB is verified by T105 (spec 001 risk R9).

## 3. Cross-cutting findings to carry into the report

Already-known differences this spec's work should confirm or refute (from the original list):
- **API churn**: Mastra `network` -> supervisor and MCP v1 -> v2; Pydantic AI V2 renamed history APIs; `TemporalAgent` deprecated. Tutorials older than mid-2026 are unreliable.
- **0.x dependency risk**: Pydantic AI Harness (guardrails, subagents, spend limits) is 0.x.
- **Hosting burden**: Claude Agent SDK's one-subprocess-per-session and disk transcripts change how the service is sized and scaled; subagents and deferred approvals make this visible (T089, T218).
- **Cost figures** from frameworks are client-side estimates.

## 4. Spikes owned by this spec

Spike outputs go to `specs/002-multi-agent-safety/spikes/`.

| ID | Question | Blocks |
|---|---|---|
| S5 | Claude Agent SDK: the `SessionStore` interface as of the pinned SDK version and a Postgres adapter; whether MCP `structuredContent` is passed through in tool results (affects `record_pr_summary`/`record_review` responses; if spec 001 already recorded a `structuredContent` finding, cite it and only confirm for `record_review`); Bash sandbox on Fargate is spec 003 | US5 (T089), US6 (T101) |
| S6 (part) | Pydantic AI: delegate span nesting for agent-as-tool trace capture, and `pydantic-graph` persistence, as they affect the delegation trace and resume. The `fasta2a` Storage/Broker/Worker effort and the A2A client parts of S6 are owned by spec 003 | US4 (T085), US5 (T092) |

Inherited and not repeated: S8 (stub endpoint override per framework), S10 (sizing), S11 (Aurora and up time), S12 (Bedrock gate) from spec 001. S3/S4 pieces used by this spec (Mastra SSE route format from S4, LangGraph OTel from S3) are recorded by whichever spec first needs them; if 001 or this spec's T106-T109 hit the Mastra SSE format question, the finding is written to `specs/002-multi-agent-safety/spikes/S4-mastra-sse.md`.

## 5. Cost note (informational)

Multi-agent reviews multiply model calls per PR (coordinator plus three specialists, concurrently), so a review costs several times a summary; chat sessions add per-turn cost. Per-run limits (`MAX_STEPS`, `MAX_RUN_SECONDS`, `MAX_RUN_COST_USD`) bound it. Live scenarios in this spec spend on Bedrock and need owner approval. Pricing and always-on estimates are in spec 001 research §5; spec 004 replaces estimates with measurements.

## 6. Bedrock issues log (owned by spec 001)

The running log, its table format, and the entries B1-B11 live in [spec 001 research §6](../001-core-pr-steward/research.md). This spec appends to it (T220) and does not keep a separate copy, so spec 004 can build the report chapter (`docs/report/bedrock-issues.md`, FR-057) from one table. Basis legend: D = documented (source cited), O = observed in this project (link to spike, run record or commit).

Entries from spec 001 that this spec is expected to confirm or refute, per framework:
- **B2** (no structured outputs): specialist findings are returned as structured tool-call output, not native structured-output modes; record the per-framework friction.
- **B6** (no count-tokens): token and cost recording for multi-agent runs comes from response usage fields; record any framework that cannot aggregate sub-agent usage into `agent_runs`.
- **B5** (server-side tool search only via InvokeModel): does not affect this spec's fixed specialist tool sets, but is noted where a framework tries to use it.
- **B11** (Claude Agent SDK Bedrock mode hang report): watch during subagent and deferred-session runs.

New issues found while working are appended as B12 onward with basis, source, and impact.
