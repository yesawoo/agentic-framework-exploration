# Feature Specification: Core PR Steward (core loop and hosting)

**Feature Branch**: `001-agent-framework-comparison` (the branch name predates the split; this spec lives in `specs/001-core-pr-steward/`)

**Created**: 2026-09-28 (re-cut into four sequential specs 2026-09-30)

**Status**: Draft

**Input**: Re-cut of the original "Agent Framework Comparison" feature. Original request: "I want to build and deploy the same agent in several different frameworks to evaluate them. LangGraph, Claude Agent SDK, Mastra, and Pydantic AI. The agent should be hosted, listen for webhooks from GitHub, and when a PR is created, call an MCP server with a summary of what the PR is accomplishing to demonstrate how MCP evaluation works. It should also have a daily workflow that publishes a digest of all PRs created the previous day, and a multi-agent workflow that demonstrates how agents communicate. Deployment infrastructure goes into AWS using OpenTofu. Suggest other common things agents have to do so the spec fully demonstrates how these libraries work."

## Overview

The evaluator (the repo owner) wants to judge four agent frameworks by building the *same* agent four times against one shared behavioral contract, deploying each to the cloud, and comparing them side by side. The reference agent is a "PR steward" for a GitHub repository. Frameworks under evaluation: **LangGraph**, **Claude Agent SDK**, **Mastra**, **Pydantic AI**.

The original feature was too large to build in one pass and is now four specs built one after another. Original identifiers (FR-, SC-, US, T, D, S) are kept everywhere so every item traces to the original.

| Spec | Scope |
|---|---|
| **001 core-pr-steward (this spec)** | Core loop and hosting: PR summary delivered to the MCP tool server (US1), reproducible hosting with one-command up/down/pause/resume/status (US2), daily digest (US3) |
| 002 multi-agent-safety | Multi-agent review (US4), reliability and untrusted input (US5), human approval (US6), conversational trigger with streaming (US7) |
| 003 extended-capabilities | Repository retrieval (US10), agent as MCP server (US11), dynamic tools and permissions (US12), long-context and memory (US15), sandbox (US13), cross-framework A2A (US14) |
| 004 evaluation-report | Observability, cost and quality evaluation (US8), the comparison report (US9), final whole-environment verification |

This spec delivers the platform every later spec builds on: the shared behavioral contract, the four implementation skeletons with a working single-agent summary loop, the reference MCP tool server, the database core, the conformance harness core with stubs, the OpenTofu environment with its spin-up and spin-down commands, and the daily digest. At its end an evaluator can deploy any implementation, open a PR, see one summary on the tool server, see the daily digest, and tear the whole thing down to zero billable resources.

## Clarifications

### Session 2026-09-28

- Q: Should spinning the environment up and down be easy? → A: Yes (FR-051 to FR-056, SC-022, SC-023): one-command up, down, pause, resume, and status, with data preserved across teardown.
- Q: Which model provider do the four implementations use, and what if Bedrock cannot do something the Anthropic API can? → A: Amazon Bedrock, for every model call (agents, evaluation judge, helper models) in all four frameworks, because Taskrabbit runs on Bedrock and the evaluation must reflect the environment it would adopt. There is no fallback to the Anthropic API; a feature Bedrock lacks is recorded as "not supported on Bedrock" and not worked around. Every issue Bedrock causes (limits, workarounds, differences between frameworks) is logged during the work and highlighted in the final report (FR-057). If a framework cannot use Bedrock at all, the provider decision returns to the evaluator.

### Session 2026-09-30

- Q: How is the feature split? -> A: Four specs in sequence (001 core, 002 multi-agent and safety, 003 extended capabilities, 004 evaluation and report). Each later spec reconciles itself against the completed work of its predecessors before starting.
- Q: What does a redelivered webhook dedupe on in this spec? -> A: `delivery_id` alone, which is correct because `pr_summary` is the only work-item kind created from a webhook delivery here. Spec 002 introduces `pr_review` from the same delivery and defines a per-kind key (see Handoff to 002).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - PR opened produces a summary delivered to a tool server (Priority: P1)

When a pull request is opened in a watched repository, the agent receives the notification, reads the PR (title, description, changed files, diff), writes a concise summary of what the PR accomplishes, and delivers that summary to an external tool server using the standard tool-server protocol. This is the core loop the four implementations are compared on.

**Why this priority**: It is the minimum viable agent: inbound event, reasoning over external data, outbound tool call. Every other story builds on it, and it demonstrates how the tool-server protocol is consumed from each framework.

**Independent Test**: Open a PR in a test repository with one implementation running; verify the tool server records exactly one summary for that PR within the target time, and that the summary accurately describes the change. Achievable with this spec alone.

**Acceptance Scenarios**:

1. **Given** a running implementation and a watched repository, **When** a PR is opened, **Then** the tool server receives one summary record containing the PR identifier, title, author, and a plain-language summary of the change's purpose.
2. **Given** a PR with a very large diff, **When** it is opened, **Then** the agent still produces a summary from a size-capped view of the diff and does not fail. Stating what was condensed, and handling input too large for one pass, is delivered by spec 003 (FR-041, US15).
3. **Given** a PR is edited or reopened after the initial summary, **When** the notification arrives, **Then** the agent does not create a duplicate record for the same PR state.
4. **Given** the tool server is unavailable, **When** a PR is opened, **Then** the failure is recorded and the delivery is retried until it succeeds or is clearly marked as failed. This spec provides the queue-level plumbing (redelivery, dead-letter queue, failed run record, alarm); the in-run backoff and the test that proves this scenario are delivered by spec 002 (FR-012, US5).

---

### User Story 2 - Each implementation is hosted and deployed reproducibly (Priority: P1)

The evaluator can provision the cloud environment and deploy any one of the four implementations from a clean checkout, using only version-controlled infrastructure definitions and the evaluator's supplied cloud credentials. Each implementation ends up publicly reachable to receive GitHub notifications, running side by side without interfering with the others.

**Why this priority**: "Hosted" is a stated requirement; an agent that only runs on a laptop cannot receive webhooks or run scheduled work, and deployment ergonomics are themselves an evaluation dimension.

**Independent Test**: From a fresh clone, run the documented provision-and-deploy sequence for one implementation and confirm it accepts a test webhook; then tear everything down and confirm no billable resources remain.

**Acceptance Scenarios**:

1. **Given** a fresh checkout and valid cloud credentials, **When** the evaluator follows the quickstart, **Then** the shared environment and one chosen implementation are deployed and pass a health check.
2. **Given** all four implementations deployed, **When** GitHub delivers an event to one implementation's address, **Then** only that implementation reacts.
3. **Given** a deployed environment, **When** the evaluator runs the teardown, **Then** all created resources are removed.
4. **Given** infrastructure changes, **When** the evaluator reviews the plan output before applying, **Then** the plan shows exactly what will change.
5. **Given** a running environment, **When** the evaluator pauses it, **Then** the implementations stop running and stop accruing compute charges while their data and configuration are preserved, and resuming brings them back healthy without redeploying.
6. **Given** a fully taken-down environment, **When** the evaluator brings it up again, **Then** it returns to a healthy state with one command, prior data is restored (unless a fresh start is chosen), and the GitHub notification address is re-registered automatically.
7. **Given** any state (up, paused, down), **When** the evaluator asks for status, **Then** they see what is running, how long it has been up, and an estimated daily cost.

---

### User Story 3 - Daily digest of yesterday's PRs (Priority: P2)

Every morning, each implementation runs a scheduled workflow that gathers all PRs created in the watched repository the previous day, groups and summarizes them, and publishes one digest. The scheduled run works without any inbound event, demonstrating each framework's story for scheduled and batch work.

**Why this priority**: It is the second explicitly requested behavior and exercises a different trigger type (time-based rather than event-based) plus aggregation over many items.

**Independent Test**: Seed the test repository with PRs dated the previous day, trigger the scheduled workflow manually, and verify the published digest lists every one of them and no others.

**Acceptance Scenarios**:

1. **Given** three PRs created yesterday and two created today, **When** the morning workflow runs, **Then** the digest lists exactly the three from yesterday, each with title, author, status, and a short summary.
2. **Given** no PRs were created yesterday, **When** the workflow runs, **Then** a digest is still published stating there was no activity (or the workflow deliberately skips publishing, per the chosen behavior in Assumptions), and it does not error.
3. **Given** the workflow fails partway, **When** it is re-run for the same day, **Then** the digest is published once, not twice.
4. **Given** PRs created around midnight, **When** the workflow runs, **Then** "yesterday" is evaluated consistently in a single documented timezone.

---

### Edge Cases

- A PR is opened as a draft, converted to ready for review, or opened by a bot: does the agent summarize it? (Default: drafts and bot-authored PRs are summarized; bots are labeled as such.)
- A PR touches only binary or generated files, so no meaningful text diff exists.
- A PR is opened, then closed within seconds, before processing completes.
- The GitHub notification arrives while a previous run for the same PR is still in progress.
- The watched repository is private and the agent lacks access to some content.
- The daily workflow runs while the model provider is degraded.
- Two implementations accidentally point at the same repository and tool server (duplicate records must be distinguishable by implementation).
- The tool server changes its advertised capabilities between runs (e.g. a renamed tool).
- The evaluator's cloud credentials lack a permission needed during provisioning (failure must be clear, not partial and silent).
- A very large diff arrives that would not fit the model's input (the agent works from a size-capped view; disclosing and condensing properly is spec 003, FR-041).
- A model or capability the agents need is not enabled or not available on Bedrock in the configured region (must fail clearly at provisioning or health check, not mid-run).
- Bedrock throttling or quota limits differ across the four implementations running at once (in-run retry is spec 002, FR-012; here the queue redelivers, and any effect on results is recorded as a finding in research section 6).
- A fresh `bootstrap` follows a `destroy-all` (no leftover secret names, no non-empty bucket or repository blocking the destroy).
- `up` is run twice in a row, or `down` is run with nothing deployed (both are safe no-ops).

## Requirements *(mandatory)*

### Functional Requirements

**Core behavior**

- **FR-001**: Each of the four implementations MUST accept GitHub pull-request notifications over a publicly reachable address and act when a PR is opened.
- **FR-002**: On PR open, each implementation MUST read the PR's title, description, changed files, and diff, and produce a plain-language summary of what the PR accomplishes.
- **FR-003**: Each implementation MUST deliver that summary to the tool server by invoking one of the tool server's advertised tools via the standard tool-server protocol, discovering the tool rather than hard-coding its schema where the protocol allows.
- **FR-004**: The system MUST include a reference tool server that records received summaries and digests, exposes them for inspection, and identifies which implementation submitted each record.
- **FR-005**: Each implementation MUST run a scheduled workflow every morning that publishes one digest covering exactly the PRs created the previous calendar day, evaluated in a single documented timezone.
- **FR-006**: The digest MUST include for each PR: title, author, current status, link, and short summary, and MUST be published to the destination defined in the Assumptions section.

**Reliability** (baseline only; the full reliability and safety story is spec 002)

- **FR-009**: The system MUST verify the authenticity of every incoming notification and reject unauthenticated ones without processing.
- **FR-010**: The system MUST process each distinct notification at most once, even when it is delivered multiple times, and MUST NOT create duplicate summaries or digests. *Delivered here*: worker-side dedupe on `delivery_id` (sufficient while `pr_summary` is the only kind created from a delivery), idempotent summary per `(repo, pr_number, head_sha)`, one digest per `(digest_date, repo)`. *Extended by spec 002*: a per-kind dedupe key once `pr_review` shares the delivery.
- **FR-011**: The system MUST respond to GitHub promptly and perform the actual agent work asynchronously, so slow model calls cannot cause delivery timeouts.
- **FR-012**: The system MUST retry transient failures (model provider, tool server, GitHub) with backoff, and MUST record terminal failures visibly. *Delivered here*: queue-level retry (SQS redelivery after the visibility timeout, dead-letter queue after 5 receives), failed runs recorded, and the alarms of FR-020. *Delivered by spec 002*: in-run exponential backoff for model, GitHub, and tool-server errors, and the tests for it.
- **FR-013**: In-flight runs MUST survive process restarts by resuming or safely retrying. *Delivered here*: a message is deleted only when its run reaches a terminal status, so a killed worker's message is redelivered, and handlers are idempotent on `(kind, subject_key)`. *Delivered by spec 002*: resume from framework-native state (checkpoints, workflow snapshots, sessions) and the restart test.
- **FR-016**: Each run MUST be subject to configurable step, time, and spend limits.

**Observability** (baseline only; evaluation, cost lookup, and tracing export are spec 004)

- **FR-018**: Every run MUST produce a record of steps, model calls, tool calls, timing, token usage, estimated cost, and outcome, viewable by the evaluator. *Delivered here*: the `agent_runs` and `run_steps` records for `model_call` and `tool_call` steps and `GET /admin/runs[/{id}]`. *Extended by spec 002* (delegation steps) and *spec 003* (tool-load, retrieval, and memory steps); *spec 004* adds OpenTelemetry export and the cost and duration lookup (SC-009).
- **FR-020**: Errors and failed runs MUST generate an alert to the evaluator.
- **FR-021**: The system MUST emit structured logs that never contain secrets.

**Shared contract and comparability**

- **FR-022**: All implementations MUST satisfy the same behavioral contract (inputs, outputs, tool-server records, digest format), verified by one shared conformance test suite that runs against each. *Delivered here*: the contract, the harness core, the stubs, and the contract-tier tests for US1 to US3. Specs 002 and 003 add the tests for their stories; spec 004 owns the identical evaluation report format (SC-008).
- **FR-023**: All implementations MUST use the same model family for reasoning where the framework allows, so that differences observed are attributable to the framework rather than the model. Every model call (agents, evaluation judge, helper models) MUST go through Amazon Bedrock, matching Taskrabbit's environment; the Anthropic API MUST NOT be used as a fallback. A capability unavailable on Bedrock MUST be recorded in the report as "not supported on Bedrock" (FR-024) rather than worked around.
- **FR-024**: Framework-specific limitations MUST be recorded rather than worked around silently; each workaround is noted in the report.

**Deployment**

- **FR-025**: All cloud infrastructure MUST be defined in version-controlled OpenTofu code targeting AWS, with a reviewable plan before apply, and MUST NOT be created via manual console changes.
- **FR-026**: The evaluator MUST be able to deploy and tear down each implementation independently, and the environment MUST support all four running at once.
- **FR-027**: Secrets (cloud credentials, GitHub webhook secret) MUST be stored encrypted and MUST NOT be committed in plaintext.
- **FR-028**: Every implementation MUST have a health check and a documented clean-state quickstart that runs top to bottom from a fresh checkout.

**Operations**

- **FR-051**: The evaluator MUST be able to bring up, and take down, the whole environment or any subset of implementations with one documented command each and no manual steps in between.
- **FR-052**: The system MUST support a pause state, distinct from full teardown, in which implementation compute stops and stops accruing charges while data, configuration, images, and secrets are preserved, and a resume that restores service without rebuilding or redeploying images. The data store SHOULD stop charging for compute while idle.
- **FR-053**: Bringing the environment up after a teardown MUST restore the previous data (memory facts, records, run history) by default, MUST offer an explicit fresh-start choice, and MUST automatically re-register the GitHub notification address, since it may change.
- **FR-054**: A status command MUST report, per component, whether it is running, paused, or absent, its uptime, and an estimated daily cost.
- **FR-055**: The system SHOULD guard against forgotten environments with a spend alarm and an optional maximum uptime after which implementations are paused automatically.
- **FR-056**: The persistent layer that survives teardown (state, images, secrets, report artifacts, the database, the public entry address) MUST be explicitly documented and separately destroyable, so that a full destroy leaves no billable resources.

### Key Entities

- **Pull Request Event**: One delivery from GitHub, with a unique delivery identifier, PR identifier, action type, and timestamp; the unit of deduplication.
- **PR Summary**: The agent's plain-language account of a PR's purpose, tied to a PR state, producing implementation, and timestamp.
- **Review Finding**: A specialist's structured observation (topic, severity, evidence, author agent) that the coordinator merges into a consolidated review.
- **Daily Digest**: The summary of one calendar day's PRs; keyed by date and implementation so it publishes once.
- **Agent Run**: A single execution with steps, model calls, tool calls, cost, status, and (for multi-agent) the delegation trace.
- **Tool Server Record**: A stored summary, review, or digest, labeled with the submitting implementation.
- **Work Item**: One unit of queued work (`pr_summary`, `digest`; other kinds are defined by the queue contract and added by later specs) with an idempotency key, attempts, and status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For at least 95% of PRs among the fixtures this spec owns (`basic-feature`, `large-diff`, `binary-only`, `bot-author`, `draft-pr`), each implementation delivers a correct summary record to the tool server within 2 minutes of the PR being opened.
- **SC-002**: A forged notification is rejected in 100% of trials, and a redelivered notification produces zero duplicate records across 20 trials. Forged-signature rejection and redelivery dedupe are delivered and verified here; the injection and secret cases of the safety story are spec 002.
- **SC-003**: The morning digest for a seeded day lists 100% of that day's PRs and 0 PRs from other days, in all four implementations.
- **SC-004**: An evaluator with valid credentials can go from a fresh checkout to one working deployed implementation in under 30 minutes by following the quickstart, and can fully tear it down in under 10 minutes with no resources left behind.
- **SC-022**: From a taken-down state, one command returns the environment to healthy, with data restored and webhooks re-registered, in under 20 minutes; pause and resume each complete in under 5 minutes.
- **SC-023**: While paused, the status command's estimated cost is under 25% of the running cost, and a full destroy followed by the clean-check leaves zero billable resources.

Success criteria owned by other specs (for orientation): SC-005 to SC-007 spec 002; SC-011 to SC-018 spec 003; SC-008 to SC-010, SC-019 to SC-021, SC-024 spec 004.

## Assumptions

- **Frameworks**: "Pydantic API" in the request is taken to mean Pydantic AI. The four frameworks are LangGraph, Claude Agent SDK, Mastra, and Pydantic AI.
- **Model**: All implementations use the same Claude model family, since Claude Agent SDK is tied to it; this keeps the comparison fair. Models are accessed through Amazon Bedrock in the evaluator's AWS account, because Bedrock is what Taskrabbit uses, authenticated with the deployed workload's cloud identity rather than a model API key. The evaluator's account must have access to the chosen models in the chosen region. Each framework's Bedrock support is confirmed by a spike before implementation; the Bedrock decision is revisited if any framework lacks it.
- **"MCP evaluation"**: Interpreted as evaluating how each framework discovers and calls tools on an MCP server, and how correctly and reliably it does so, rather than evaluating a third-party MCP product.
- **MCP server**: There is no existing MCP server to target, so this project builds a small reference MCP server (record summaries, digests, and reviews; expose them for inspection), hosted alongside the agents.
- **Repository scope**: Agents watch an evaluator-designated test repository (or short allowlist), not every repository the evaluator owns. Use of production repositories is out of scope.
- **"Created the previous day"**: Uses the evaluator's local timezone, fixed in configuration; the morning schedule is approximately 08:00 in that timezone.
- **Empty days**: A digest stating "no PRs" is still published, so silence always means failure.
- **Credentials**: The evaluator supplies cloud credentials and a GitHub token, plus Bedrock model access enabled in the AWS account; the project never creates them. No Anthropic API key is needed.
- **Cost control**: Cost is managed by pausing or taking the environment down between sessions; leaving it running is the expensive case. Exact figures are estimates until measured.
- **Cost**: The exercise is small-scale; the environment is sized for low traffic, and the evaluator accepts modest ongoing cost while it is deployed.
- **Conventions**: The project follows the constitution in `.specify/memory/constitution.md`, adopted from the glitch repository as a starting point. Parts of it are specific to that repository and may need adapting.
- **No injection defense yet**: Until spec 002 lands, the agents run only against the owner's designated test repository and treat PR content with the base prompt only; FR-014 is not claimed by this spec.
- **Out of scope for the whole exercise**: Multi-tenant use, a user interface beyond GitHub and the tool-server inspection view, other event sources (Slack, email), and production-grade high availability.
- **Digest destination**: The daily digest is published as a GitHub issue in the watched repository, one per day per implementation (titled with the date and implementation name so reruns can find and reuse it). It is also recorded on the reference tool server.

## Out of scope here (owned by another spec)

- Multi-agent review, reviews and findings tables, `record_review` use by agents (FR-007, FR-008): spec 002 (US4). The tool server already offers `record_review`; nothing in this spec calls it.
- Injection and secret defenses (FR-014), in-run retry with backoff, framework-native resume, per-kind dedupe key, the Claude Agent SDK `SessionStore` (FR-010 extension, FR-012, FR-013 extension): spec 002 (US5).
- Human approval and the `/approve` `/reject` comment path (FR-015), conversational trigger and streaming (FR-017), `/chat/stream`, `approval_sweep`: spec 002 (US6, US7).
- Retrieval, the agent as MCP server, dynamic tools and permissions, sandbox, A2A, long-context and memory (FR-030 to FR-045, including the condensed-summary check moved out of the original T034): spec 003.
- Shared evaluation set and reports, native evaluation capabilities, OpenTelemetry export, cost and duration lookup, the comparison report, the Bedrock report chapter, `just eval`, and final whole-environment verification (FR-019, FR-029, FR-046 to FR-050, FR-057, SC-008 to SC-010, SC-019 to SC-021, SC-024): spec 004. This spec starts and maintains the Bedrock issues log (research section 6) that spec 004 turns into the chapter.

## Depends on / Inherited from predecessors

None: this is the first spec. It depends only on things outside the repository, supplied by the owner and never created by the project:

- An AWS account and credentials (profile or environment) with rights to create the resources in `infra/`, and Amazon Bedrock model access already enabled in `us-east-1` for Claude Sonnet 5.5, Opus 5.5, and Haiku 4.5 (quickstart section 0).
- A GitHub fine-grained token and a designated test repository (`WATCHED_REPO`), and the owner's login (`OWNER_LOGIN`).
- The constitution at `.specify/memory/constitution.md` (v1.0.0) and the Spec Kit templates.

## Reconciliation

Not applicable, first spec. The original decisions that later specs must not reopen are preserved here: Bedrock only with no Anthropic API fallback; `us-east-1` for infrastructure and `BEDROCK_REGION`; the S12 spike uses the owner's AWS profile; migrations run as a one-shot ECS migrate task (defined in `infra/durable`, image built and pushed by `bootstrap`); `destroy-all` leaves no snapshot unless `KEEP_FINAL_SNAPSHOT=1`; capability status "not available" is a valid recorded result (FR-049, SC-021, spec 004); no shared agent logic across frameworks.

## Handoff to 002

What this spec promises downstream. Spec 002's Phase 0 verifies each item against the as-built code and records the outcome in its `reconciliation.md`; this spec's `as-built.md` (task T176, finished by T178) records deviations.

1. **HTTP surface** (`contracts/http-api.yaml`, core paths): `/health` (liveness, no DB), `/ready`, `POST /webhooks/github` (HMAC verify, 202 for a handled event, 200 for `ping` and unhandled events, 401 for a bad signature, never touches the database), `POST /internal/schedule` (kind `digest` only), `GET /admin/runs`, `GET /admin/runs/{run_id}`. All under `BASE_PATH` (`/<impl>` on AWS, empty locally), admin routes behind the `ADMIN_TOKEN` bearer. Spec 002 extends the webhook routing and `/internal/schedule` via `http-api-additions.yaml`.
2. **Work queue** (`contracts/work-queue.md`): message schema and all six kind names are defined, but only `pr_summary` and `digest` have handlers. The worker keeps one handler registry (`worker.py` or `worker.ts`); an unregistered kind is acknowledged and recorded as `ignored` (metric `WorkItemsIgnored`, no retry, no DLQ). Spec 002 registers `pr_review`, `approval_decision`, `approval_sweep`, `chat`.
3. **Dedupe** (P3-02): `events.delivery_id` is the primary key and the worker drops a message whose `delivery_id` already exists. This is correct only while `pr_summary` is the sole kind created from a delivery. Spec 002 MUST define a distinct key per work-item kind (for example `delivery_id` plus `kind`), migrate `events` in migration 0003, and change the worker in all four implementations.
4. **Database**: one schema and login role per implementation plus `toolserver`; migration `0001_contract_tables.sql` creates `events`, `work_items`, `pr_summaries`, `digests`, `agent_runs`, `run_steps` (with the full contract enumerations for `work_items.kind`, `agent_runs.kind`, `run_steps.kind`, so later specs add tables, not enum changes); `0002_toolserver.sql` creates `records` and `calls`. The migrate runner is incremental (applies only pending numbered files per schema and records them), so spec 002 adds `0003`, spec 003 `0004`, and `db-reset` recreates everything.
5. **Tool server** (`contracts/mcp-tool-server.md`): four tools (`record_pr_summary`, `record_review`, `record_digest`, `list_records`), idempotent on natural keys, `implementation` label required, every call logged to `toolserver.calls`, bearer auth, `GET /records`.
6. **Stubs**: `stub_bedrock` speaks Converse and Invoke with binary event-stream, selects scenarios by header, marker, or fixture id, and has the fault knobs `fail_once`, `rate_limit`, `timeout`; only the scenarios spec 001 needs are scripted. `stub_github` serves get PR, list files and diff, list PRs, and create or update issue; spec 002 adds issue comments, and spec 003 code search and file contents. Per S8, a framework whose Bedrock endpoint override was refused is stubbed at the agent-tool boundary (recorded per framework in `spikes/S8-*.md` and `CLAUDE.md`).
7. **Conformance harness**: `client.py`, `fixtures.py`, `toolserver.py`, `conftest.py` (`--tier contract|live`, `--impl`), the `just scenario` dispatcher, initial fixtures `basic-feature`, `large-diff`, `binary-only`, `bot-author`, `draft-pr` (the loader and the `expected.yaml` and `tags` format are ready for later fixtures), and the CI workflows per component plus `conformance.yml`.
8. **Per-implementation code layout**: `model.py` (Bedrock wiring), `github.py`, `mcp_client.py`, `agents/summary.py`, `agents/digest.py`, `app.py`, `webhook.py`, `worker.py`, `runs.py`, `admin.py`, `logging_metrics.py`. Spec 002 adds `agents/review.py`, `safety.py`, and the approval and chat handlers.
9. **Infrastructure**: `infra/durable` (state bucket, ECR, secrets, artifacts bucket, VPC, Aurora Serverless v2 with scale-to-zero, migrate task, `app-to-db` security group, `db-role/*` secrets, SNS, budget), `infra/edge` (CloudFront), `infra/shared`, `infra/tool-server`, `infra/modules/implementation` (schedules: `digest` only), one root per implementation. Service-to-service calls go through the CloudFront URL. Spec 002 adds the `approval_sweep` schedule to the module.
10. **Orchestration**: `just bootstrap|secrets-load|plan|deploy|destroy|smoke|webhook-register|up|down|pause|resume|status|db-reset|destroy-all|verify-clean`. `destroy-all` works with images in ECR and objects in the artifacts bucket (T175).
11. **Observability**: the JSON log fields and CloudWatch EMF metrics in `contracts/observability.md`, and alarms for 5xx, failed runs, DLQ depth, and missed digest.
12. **Bedrock**: pinned global inference-profile IDs from S12, the environment names in `contracts/environment.md`, the research section 6 issues log seeded B1 to B11 and extended by S12. Later specs append.
13. **Deployed state at handoff**: after the last task of this spec the environment is destroyed (`destroy-all`, `verify-clean` empty). A later spec that needs a live environment runs `bootstrap` again; the durable database starts empty.
14. **Not delivered (spec 002 must add)**: injection and secret defenses, in-run retry with backoff, framework-native resume and the Claude Agent SDK `SessionStore`, multi-agent review, approval, chat and streaming, `pr_review` and `approval_sweep` routing, the per-kind dedupe key.
