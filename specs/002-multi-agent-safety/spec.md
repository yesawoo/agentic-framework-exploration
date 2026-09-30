# Feature Specification: Multi-Agent and Safe Interaction

**Feature Branch**: `001-agent-framework-comparison` (the original single-feature branch; the work is now cut into four sequential specs, see below)

**Created**: 2026-09-30 (re-cut of the 2026-09-28 Agent Framework Comparison spec)

**Status**: Draft

**Input**: User description: "I want to build and deploy the same agent in several different frameworks to evaluate them. LangGraph, Claude Agent SDK, Mastra, and Pydantic AI. The agent should be hosted, listen for webhooks from GitHub, and when a PR is created, call an MCP server with a summary of what the PR is accomplishing to demonstrate how MCP evaluation works. It should also have a daily workflow that publishes a digest of all PRs created the previous day, and a multi-agent workflow that demonstrates how agents communicate. Deployment infrastructure goes into AWS using OpenTofu. Suggest other common things agents have to do so the spec fully demonstrates how these libraries work."

## Overview

The original Agent Framework Comparison feature was too large to plan and build in one piece. It is now four specs, built one after another. Each later spec reconciles itself against the completed work of its predecessors before starting.

| Spec | Name | Scope (original IDs kept) |
|---|---|---|
| 001-core-pr-steward | Core loop and hosting | US1 PR summary to the MCP tool server, US2 reproducible hosting and up/down/pause/resume/status, US3 daily digest; shared contract, stubs, DB core, tool server, conformance harness core |
| **002-multi-agent-safety (this spec)** | Multi-agent and safe interaction | US4 multi-agent review, US5 reliability and untrusted input, US6 human approval, US7 conversational trigger with streaming |
| 003-extended-capabilities | Extended agent capabilities | US10 retrieval, US11 agent as MCP server, US12 dynamic tools and permissions, US15 long context and memory, US13 sandbox (optional), US14 cross-framework A2A |
| 004-evaluation-report | Evaluation and comparison report | US8 observability, cost and quality evaluation, US9 the report, final whole-environment verification |

This spec (002) adds, on top of the working single-agent loop from 001, the behaviors that make the four implementations more than a summarizer: a coordinator with three specialists that delegate and merge findings with a visible trace (US4), hardening for redelivery, transient failure, restart and hostile content (US5), a human approval gate before a side-effecting comment (US6), and a conversational trigger with streamed progress (US7). The reference agent is still the "PR steward" for a GitHub repository, built four times (**LangGraph**, **Claude Agent SDK**, **Mastra**, **Pydantic AI**) against one shared behavioral contract, with all model calls on Amazon Bedrock and no shared agent logic across frameworks.

IDs (FR-, SC-, US, T, S, D) are the original IDs, not renumbered. New tasks in this spec use the reserved range T200-T299.

## Depends on / Inherited from predecessors

This spec assumes spec **001-core-pr-steward** is complete (its US1 and US2 checkpoints checked, US3 built) and provides all of the following. Phase 0 of this spec verifies each item against the as-built state (see Reconciliation).

**Contracts (spec 001 `contracts/`)**
- `http-api.yaml` core paths: `/health` (DB-free), `/ready`, `POST /webhooks/github` (signature check, 202 for handled events, no database access in the handler), `POST /internal/schedule` (kind `digest`; this spec adds `approval_sweep`, T223), `/admin/runs`, `/admin/runs/{run_id}`, and schemas `AgentRun` and `RunStep` (with the full `kind` and `outcome` enums, including `delegation`, `delegation_result`, `refused`, `timeout`, and the run status `waiting_approval` and `limit_exceeded`).
- `work-queue.md`: message envelope, `kind` list (`pr_summary`, `pr_review`, `digest`, `chat`, `approval_sweep`, `approval_decision`), `params` per kind, at-least-once semantics, visibility timeout and DLQ, limits, alerts.
- `mcp-tool-server.md`: the four tools including `record_review` (natural key `(implementation, repo, pr_number, head_sha)`), idempotent with `duplicate: true`.
- `environment.md`: all names, including `OWNER_LOGIN`, `MAX_STEPS`, `MAX_RUN_SECONDS`, `MAX_RUN_COST_USD`, `TOOLSERVER_URL`, `BEDROCK_*`.
- `observability.md`: log fields and metrics (`RunsSucceeded`, `RunsFailed`, `RunsLimitExceeded`, `RunDurationMs`, `WorkItemsIgnored`, and the rest).

**Database (spec 001 migrations `0001`, `0002`)**
- Per-implementation tables `events`, `work_items`, `pr_summaries`, `digests`, `agent_runs`, `run_steps`, and the `toolserver` schema with `records` (kind `review` included) and `calls`.
- `0001` CHECK constraints admit every work-item kind, `agent_runs.kind`, `agent_runs.status` (`waiting_approval`, `limit_exceeded`, `abandoned`), and `run_steps.kind` (`delegation`, `delegation_result`) that this spec uses. If not, migration `0003` widens them (Reconciliation).
- The `shared/db` migrate runner and image, applied on AWS by the durable one-shot migrate task and locally by the compose `migrate` service; `0003` is the next migration number.

**Code and behavior in each of the four implementations**
- Service skeleton: `/health`, `/ready`, webhook handler routing pull_request to `pr_summary`, `POST /internal/schedule`, prefix-aware routes under `BASE_PATH`.
- Worker loop with one handler registry; unregistered kinds are acknowledged and recorded `ignored` (`WorkItemsIgnored`, no retry, no DLQ) until this spec registers `pr_review`, `chat`, `approval_decision`, and `approval_sweep`.
- Worker-side dedupe on `events.delivery_id` for `pr_summary` only (this spec replaces it with a per-kind key, see Reconciliation and FR-010 below).
- Run recording (`agent_runs`, `run_steps`), `GET /admin/runs[/{id}]`, structured logging and EMF metrics, per-run limits from configuration.
- PR summary agent, `github.py` (PyGithub or Octokit), `mcp_client.py` (tool discovery at run time), `model.py` (Bedrock client with the stub override), `agents/summary.py`, digest workflow.
- The framework-native Bedrock clients pinned by spike S12 (global inference profiles for Sonnet 5.5, Opus 5.5, Haiku 4.5) and the S8 findings on which frameworks accept the stub endpoint override.

**Shared components**
- `shared/conformance`: `stub_bedrock.py` (Converse and Invoke wire formats, `X-Stub-Scenario`, fault injection `fail_once`, `rate_limit`, `timeout`), `stub_github.py` (PR, comments create and update, webhook sender signing HMAC-SHA256), fixtures (`basic-feature`, `large-diff`, `oversized-diff`, `risky-no-tests`, `prompt-injection`, `secret-in-diff`, `binary-only`, `bot-author`, `draft-pr`, `needs-context`), the harness core (`client.py`, `fixtures.py`, `toolserver.py`, `report.py`, `conftest.py`), and the `just scenario` / `just eval` dispatcher.
- `compose.yaml` and `just up-local` / `just conformance-local`.
- `shared/tool-server` running with all four tools.

**Deployed state (used only by live checks)**
- Durable, edge, and shared layers plus the implementation module: SQS queue and DLQ per implementation, an EventBridge Scheduler rule for `digest` (this spec adds the `approval_sweep` rule, T223), alarms, `just deploy|destroy|smoke|up|down|pause|resume|status`, the migrate task that rebuilds when the `shared/db` source digest changes, CloudFront in front of the ALB.

**Decisions and spikes inherited (not reopened)**
- Bedrock only, no Anthropic API fallback, `us-east-1`; migrations run as a one-shot ECS migrate task; no shared agent logic across frameworks; research D1-D9, D13, D15 as in spec 001. Spike S12, S8, S10, S11 results.

## Reconciliation

Before any work in this spec starts (Phase 0 of tasks.md), verify the assumptions above against the as-built spec 001 output:

1. 001's checkpoint and verification tasks are checked and its as-built deviations are recorded.
2. Each item under "Depends on" exists and behaves as stated: contract paths and schemas, `RunStep`/`AgentRun` enums, `work-queue.md` kinds and params, `record_review` on the tool server, table shapes and CHECK constraints in `0001`, the worker handler registry and the `ignored` behavior, run recording, env names, stub scenarios and fault injection, fixtures, the `approval_sweep` schedule in the implementation module, and the `pr_summary`-only dedupe on `delivery_id`.
3. The specific known mismatch: 001 dedupes on `delivery_id` for `pr_summary` only. A single `pull_request` delivery now produces both `pr_summary` and `pr_review`, so this spec defines a distinct dedupe key per work-item kind (`delivery_id` plus `kind`) and changes the 001 worker accordingly (T203, T207, T210-T213).

Mismatches are handled by updating this spec, its plan, tasks, and contracts to match what was built (not by changing 001 unless the mismatch is a defect in 001 that blocks this spec, in which case it is logged in `reconciliation.md` as an open question for the owner). Every finding is recorded in `specs/002-multi-agent-safety/reconciliation.md` under the headings Verified, Deviations found, Spec/plan/tasks/contract changes made, Open questions. Phase 1 and later phases do not start until Phase 0 is done, including `/speckit-analyze` on this spec.

## Out of scope here (owned by another spec)

- Webhook plumbing, tool server, DB core, hosting, up/down/pause/resume/status, daily digest, basic run record, logs and alerts: spec **001**.
- Repository retrieval (US10), agent as MCP server (US11), dynamic tools and per-tool permissions (US12), long-context condensation and long-term memory (US15, FR-041 to FR-045), sandbox (US13), cross-framework A2A specialists (US14): spec **003**. In particular, condensed-summary handling of oversized input (FR-041) is delivered and tested in 003, not here.
- Observability/cost/quality evaluation (US8), the shared evaluation set run and report (FR-019, FR-049, FR-050), the comparison report (US9), Bedrock issues chapter, final whole-environment verification: spec **004**.

## Clarifications

### Session 2026-09-28 (carried from the original spec, relevant part)

- Q: Which model provider do the four implementations use, and what if Bedrock cannot do something the Anthropic API can? → A: Amazon Bedrock for every model call in all four frameworks; no fallback to the Anthropic API; a feature Bedrock lacks is recorded as "not supported on Bedrock" and not worked around; every issue is logged (research §6 in spec 001) and highlighted in the final report (FR-057, spec 004). If a framework cannot use Bedrock at all, the provider decision returns to the evaluator.
- Q: Should the four implementations call each other across frameworks? → A: Only as the P3 scenario US14 (spec 003). The core multi-agent review (US4, this spec) stays inside each framework and MUST NOT depend on cross-framework calls (FR-040).

## User Scenarios & Testing *(mandatory)*

### User Story 4 - Multi-agent PR review with visible agent-to-agent communication (Priority: P2)

For a newly opened PR, several cooperating agents with distinct roles work together: a coordinator receives the PR and delegates to specialists (for example a change summarizer, a risk and security reviewer, and a test-coverage reviewer). Specialists work independently (concurrently where possible) and return structured findings; the coordinator combines them into one consolidated review that is delivered to the tool server. The evaluator can inspect a trace showing who delegated what to whom, what each agent returned, and how the final result was assembled.

**Why this priority**: Explicitly requested, and the area where the four frameworks differ most (graph edges, sub-agents, handoffs, agent-as-tool). It is placed at P2 because it depends on the single-agent loop in Story 1.

**Independent Test**: Open a PR that has an obvious risky change and a missing test; verify the consolidated review flags both, and that the trace shows the coordinator delegating to each specialist and receiving each response.

**Acceptance Scenarios**:

1. **Given** a PR with a risky change and no tests, **When** the multi-agent review runs, **Then** the consolidated review contains a finding attributed to each relevant specialist.
2. **Given** one specialist fails or times out, **When** the review runs, **Then** the coordinator still delivers a partial review that clearly says which perspective is missing.
3. **Given** a completed review, **When** the evaluator views its trace, **Then** every delegation and response between agents is visible in order, with each agent's identity.
4. **Given** two specialists disagree (e.g. one says low risk, one says high), **When** the coordinator combines them, **Then** the disagreement is surfaced rather than silently resolved.

---

### User Story 5 - Reliable and safe handling of untrusted input (Priority: P2)

The agent accepts only genuine GitHub notifications, processes each delivery at most once even if GitHub redelivers, survives transient failures without losing work, and resists hostile content inside PRs (for example a PR description that tells the agent to ignore its instructions or leak secrets).

**Why this priority**: Any hosted agent on a public address faces these problems immediately, and how each framework helps (or does not help) with them is a meaningful comparison point.

**Independent Test**: Send a forged notification, a duplicated notification, and a PR containing an injection attempt; verify rejection, single processing, and no policy violation respectively.

**Acceptance Scenarios**:

1. **Given** a notification without a valid signature, **When** it arrives, **Then** it is rejected and nothing is processed.
2. **Given** the same delivery is received twice, **When** both arrive, **Then** the work happens once.
3. **Given** a PR description containing instructions aimed at the agent, **When** the PR is summarized, **Then** the agent treats the text as data, the summary describes the PR (optionally noting the suspicious content), and no secret or out-of-scope action results.
4. **Given** the model provider returns a transient error or rate limit, **When** processing, **Then** the agent retries with backoff and eventually succeeds or reports a terminal failure.
5. **Given** the process is interrupted mid-run, **When** it restarts, **Then** in-flight work is resumed or safely retried rather than lost.
6. **Given** the tool server is unavailable (transient failure, moved here from the original US1 test), **When** a summary or review is delivered, **Then** the failure is recorded and the delivery is retried until it succeeds or is clearly marked as failed.
7. **Given** one `pull_request` delivery that produces both a `pr_summary` and a `pr_review` work item, **When** the worker processes them, **Then** both are processed, and a redelivery of that delivery processes each kind at most once (dedupe key is per kind).

---

### User Story 6 - Human approval before a consequential action (Priority: P3)

For actions with external side effects beyond recording a summary (for example posting a review comment on the PR), the agent pauses, asks a human for approval, and only proceeds once approved. Rejection or timeout means the action does not happen.

**Why this priority**: Human-in-the-loop is a core agent pattern with very different support across frameworks, but it is not required for the base loop.

**Independent Test**: Trigger a review that proposes a PR comment; verify nothing is posted until approval, and that rejection leaves the PR untouched.

**Acceptance Scenarios**:

1. **Given** the agent proposes a PR comment, **When** no decision has been made, **Then** nothing is posted and the run is visibly waiting.
2. **Given** a pending proposal, **When** the human approves, **Then** the comment is posted exactly once and the run completes.
3. **Given** a pending proposal, **When** the human rejects or the wait period expires, **Then** nothing is posted and the outcome is recorded.

---

### User Story 7 - Conversational trigger with streamed progress (Priority: P3)

A person can address the agent directly, for example by commenting a command on a PR (such as asking it to re-summarize or explain a file), and sees progress and partial output as it is produced rather than only a final answer. The agent keeps context across a follow-up question in the same conversation.

**Why this priority**: Covers streaming and conversational memory, which are common agent needs distinct from batch and webhook flows.

**Independent Test**: Comment a command on a PR, observe incremental output, then ask a follow-up that only makes sense given the first answer.

**Acceptance Scenarios**:

1. **Given** a comment addressed to the agent, **When** it is processed, **Then** the user sees incremental progress before the final answer.
2. **Given** an earlier exchange in the same thread, **When** the user asks a follow-up referring to it, **Then** the agent answers using that context.
3. **Given** a comment from a user not permitted to command the agent, **When** it arrives, **Then** it is ignored.

---

### Edge Cases

Those from the original list that this spec's stories exercise:

- A PR is opened, then closed within seconds, before processing completes.
- The GitHub notification arrives while a previous run for the same PR is still in progress.
- Summary text contains content that should not be forwarded (secrets present in a diff).
- Bedrock throttling or quota limits differ across the four implementations running at once (retried per FR-012; recorded as a finding if it affects results).
- A model or capability the agents need is not enabled or not available on Bedrock in the configured region (must fail clearly at provisioning or health check, not mid-run; the check itself is delivered by spec 001).
- Two implementations accidentally point at the same repository and tool server (duplicate records must be distinguishable by implementation); applies to review records as well as summaries.
- The tool server changes its advertised capabilities between runs (e.g. a renamed tool); applies to `record_review`.

Edge cases owned by other specs (retrieved content injection, memory poisoning, delegation loops across frameworks, sandbox, oversized diffs) are in specs 003 and 004.

## Requirements *(mandatory)*

### Functional Requirements

**Owned by this spec (main behavior delivered here)**

- **FR-007**: Each implementation MUST provide a multi-agent workflow with at least a coordinator and three specialist agents whose delegations, responses, and disagreements are visible in a trace.
- **FR-008**: The multi-agent workflow MUST tolerate the failure of any one specialist and deliver a partial, clearly labeled result.
- **FR-014**: Content from PRs MUST be treated as untrusted data; the agents MUST NOT follow instructions embedded in it, and MUST NOT include detected secrets in any output. (Extended to retrieved repository content and remembered facts by spec 003, FR-031 and FR-045.)
- **FR-015**: Consequential side effects beyond recording summaries (posting a PR comment) MUST require explicit human approval and MUST default to not happening on rejection or timeout.
- **FR-017**: A permitted user MUST be able to command the agent from a PR comment, receive incremental progress output, and ask follow-ups that use conversation context. Commands from non-permitted users MUST be ignored. (Retaining context across a long thread without holding it verbatim is FR-042, spec 003.)

**Inherited from spec 001 and extended here (the requirement text lives in spec 001; this spec delivers the part stated)**

- **FR-010** (process each distinct notification at most once): 001 delivers webhook signature check, the `events` dedupe on `delivery_id` and idempotent summaries. This spec delivers the per-kind dedupe key (`delivery_id` plus `kind`) so a delivery that yields several work-item kinds is processed once per kind, and tests redelivery across all kinds and the reviews and approvals it adds.
- **FR-012** (retry transient failures with backoff, record terminal failures): 001 delivers SQS redelivery, the DLQ and the basic recorded failure. This spec delivers backoff for model, GitHub, and tool-server errors inside the agent handlers (including tool-server unavailability, moved from the original US1 test) and the tests.
- **FR-013** (in-flight runs survive restarts): 001 delivers SQS redelivery. This spec delivers resume-or-safe-retry per framework's native durability, including the Claude Agent SDK Postgres `SessionStore`.
- **FR-016** (step, time, spend limits): 001 delivers the limits configuration and enforcement for its run kinds. This spec delivers `limit_exceeded` handling in the reliability path and for multi-agent runs, and tests that such runs are not retried.
- **FR-018** (run record): 001 delivers the record for its run kinds. This spec adds the delegation trace (`delegation`, `delegation_result` steps), the `waiting_approval` status, and `chat` runs.
- **FR-021** (structured logs never contain secrets): 001 delivers log redaction in the emitting code. This spec adds the secret scrubber applied to every output, log line, and tool-server payload for content from PRs.
- **FR-022, FR-023, FR-024** (shared contract and conformance, Bedrock-only, record framework limitations): inherited unchanged; the new contract additions in this spec are covered by conformance tests here.
- **FR-040** (a failed or unreachable remote specialist degrades to a labeled partial result; the core workflow MUST NOT depend on cross-framework calls): the core-independence half is satisfied here (FR-007 works with in-framework specialists only); the remote-specialist half is delivered by spec 003.

**Not delivered here**: every other FR (spec 001, 003, or 004 owns it).

### Key Entities

- **Review Finding**: A specialist's structured observation (topic, severity, evidence, author agent) that the coordinator merges into a consolidated review.
- **Consolidated Review**: The coordinator's combined output: findings, surfaced disagreements, and a note of any missing perspectives.
- **Approval Request**: A pending proposed side effect with decision (approved, rejected, expired) and decider.
- **Pull Request Event** (extended): One delivery from GitHub; dedupe unit is now the pair (delivery identifier, work-item kind).
- **Agent Run** (extended): adds the delegation trace and the `waiting_approval` state; `chat` runs.
- **Tool Server Record** (extended use): reviews, labeled with the submitting implementation.

Entities owned by other specs: Watched Repository, PR Summary, Daily Digest (001); Context Source, Tool Grant, Sandbox Run, Memory Fact (003); Evaluation Sample/Report, Comparison Report, Framework Scorecard, Suitability Criterion (004).

## Success Criteria *(mandatory)*

### Measurable Outcomes

**Owned by this spec**

- **SC-005**: In the multi-agent scenario, the trace shows every delegation and response for 100% of runs, and a review completes with a labeled partial result in 100% of trials where one specialist is forced to fail.
- **SC-006**: Injection-attempt PRs in the evaluation set cause zero out-of-policy actions or leaked secrets across all implementations. (This spec measures it on the contract-tier and live fixtures `prompt-injection` and `secret-in-diff`; spec 004 re-measures on the full evaluation set.)
- **SC-007**: With approval required, zero side-effecting comments are posted without an approval in 100% of trials.

**Split with spec 001**

- **SC-002**: A forged notification is rejected in 100% of trials, and a redelivered notification produces zero duplicate records across 20 trials. 001 delivers and measures it for the `pr_summary` path. This spec delivers the 20-trial redelivery measure across every work-item kind under the per-kind dedupe key (both `pr_summary` and `pr_review` from one delivery), plus the forged-signature check for the added event types (issue comments).

**Inherited (measured by another spec)**

- SC-001, SC-003, SC-004, SC-022, SC-023: spec 001. SC-008, SC-009, SC-010, SC-019, SC-020, SC-021, SC-024: spec 004. SC-011 to SC-018: spec 003. Every new test in this spec runs in the shared conformance suite and so contributes to SC-008.

## Assumptions

- **Frameworks and model**: as in spec 001: LangGraph, Claude Agent SDK, Mastra, Pydantic AI ("Pydantic API" in the request means Pydantic AI); one Claude model family, accessed only through Amazon Bedrock with the deployed workload's cloud identity; no Anthropic API key.
- **Multi-agent design**: The demonstration workflow is a coordinator plus three specialists (summarizer, risk/security reviewer, test-coverage reviewer). The exact roles may be adjusted at planning time without changing the scenarios. The specialists are the same three roles in every framework and use each framework's native delegation mechanism (subagents-as-tools, `AgentDefinition`, agent-as-tool, supervisor `agents`).
- **Approval channel**: The human-approval decision is made by replying `/approve <id>` or `/reject <id>` on the PR (research D10); requests expire after 24 hours through the scheduled `approval_sweep` work item.
- **Authorized users**: Only the repository owner (`OWNER_LOGIN`) may command the agent or decide approvals in v1.
- **Streaming shape**: GitHub has no streaming primitive, so progress is delivered by editing one PR comment at most every 2 seconds, and every implementation also exposes `POST /chat/stream` (SSE) for direct inspection (research D11).
- **Credentials and scope**: As in spec 001: the evaluator supplies cloud credentials, a GitHub token with issue and PR write access on the test repository only, and Bedrock model access. Live tasks that write to GitHub or spend on model calls need owner approval.
- **Out of scope**: as in spec 001 (multi-tenant use, UI beyond GitHub and the tool-server inspection view, other event sources, production-grade HA).

## Handoff to 003

What this spec promises downstream (003 verifies these in its Phase 0):

- Tables `reviews`, `findings`, `approval_requests` (migration `0003`), with `findings.framework` populated so cross-framework findings can be attributed; the per-kind dedupe key on `events`.
- The multi-agent review pipeline in every implementation (`agents/review.py`/`review.ts`) whose specialists can be swapped for remote ones, with delegation and delegation_result steps in `run_steps`, the `missing_perspectives` and `disagreements` fields, and labeled partial results on specialist failure.
- The approval flow (`approvals.py`/`approvals.ts`, `GET /admin/approvals`, `/approve` and `/reject` handling, `approval_sweep` expiry) reusable by US12 for `requires_approval` tools, and the `defer`/resume machinery, including the Claude Agent SDK Postgres `SessionStore`.
- `POST /chat/stream` (SSE events `progress`, `delta`, `tool`, `final`, `error`), the `chat` work-item handler, and `thread_id` context, on which US15 builds long-context handling.
- The secret scrubber and untrusted-data delimiting in `safety.py`/`safety.ts`, which US10 and US15 reuse for retrieved and remembered content.
- Reliability behavior: backoff, resume, per-kind dedupe, `limit_exceeded` not retried.
- Extended `stub_bedrock.py` scenarios (`risky-no-tests`, `specialist-timeout`, `specialists-disagree`, `rate_limit`, `fail_once`, `timeout`, slow response, `prompt-injection`, `secret-in-diff`, multi-turn chat) and contract-tier tests `test_us4_multiagent.py`, `test_us5_reliability.py`, `test_us5_safety.py`, `test_us5_dedupe_per_kind.py`, `test_us6_approval.py`, `test_us7_chat.py`, `test_us7_sse_through_edge.py`.
- Contract files in this spec: `http-api-additions.yaml` (extends spec 001 `contracts/http-api.yaml`) and `work-queue-amendments.md` (extends spec 001 `contracts/work-queue.md`).
