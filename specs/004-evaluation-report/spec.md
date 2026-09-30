# Feature Specification: Evaluation and Comparison Report

**Feature Branch**: `001-agent-framework-comparison` (shared working branch; this spec lives in `specs/004-evaluation-report/`)

**Created**: 2026-09-30 (split from the original Agent Framework Comparison spec of 2026-09-28)

**Status**: Draft

**Input**: Fourth of four sequential specs cut from the original "Agent Framework Comparison" feature. Original user description: "I want to build and deploy the same agent in several different frameworks to evaluate them. LangGraph, Claude Agent SDK, Mastra, and Pydantic AI. ... Deployment infrastructure goes into AWS using OpenTofu. Suggest other common things agents have to do so the spec fully demonstrates how these libraries work." This spec owns the last part of that: measuring the four implementations and writing the comparison report.

## Overview

Specs 001 to 003 build and deploy the four "PR steward" implementations (LangGraph, Claude Agent SDK, Mastra, Pydantic AI) with their core loop, multi-agent and safety behavior, and extended capabilities. This spec turns them into an *evaluation*: it adds per-run cost and quality measurement (User Story 8), a shared evaluation harness plus each framework's native evaluation tooling, and the comprehensive comparison report that assesses each framework's suitability as Taskrabbit's multi-agent library of choice (User Story 9). It also owns the final whole-environment verification and the closing teardown of the whole project.

This spec assumes the other three are complete. It does not add agent behavior. Where a predecessor left a story unbuilt or a framework capability unsupported, the report says so instead of hiding it (User Story 9, scenario 2).

Original IDs are kept for traceability: FR-, SC-, US, T (tasks), spikes (S#), and research decisions (D#) mean the same as in the original spec. New tasks use the reserved range T400-T499.

## Depends on / Inherited from predecessors

Assumed to exist and pass their own checkpoints. Each item is verified in Phase 0 (see Reconciliation).

**From spec 001-core-pr-steward**
- **Deployed shape and commands**: `just up`, `down`, `pause`, `resume`, `status`, `destroy-all`, `verify-clean`, `scenario`, and the `just eval <impl>` / `just eval-all` dispatcher entry points (001 T028) delegating to `shared/conformance/src/conformance/cli.py`. Infra roots `infra/{durable,edge,shared,tool-server,modules/implementation,implementations/*}`; the alarm set (5xx, failed runs, DLQ depth, missed digest) in the implementation module (001 T061); `destroy-all` that completes (ECR `force_delete`, artifacts bucket `force_destroy`, decision X03) and `verify-clean`.
- **Tables** (data-model of spec 001): `events`, `work_items`, `pr_summaries`, `digests`, `agent_runs` (with `input_tokens`, `output_tokens`, `cache_read_tokens`, `est_cost_usd`, `steps`, `model_calls`, `tool_calls`, `limit_reason`, `status`), `run_steps`, and the `toolserver` schema (`records`, `calls`). Migration 0001/0002 applied by the one-shot ECS migrate task.
- **HTTP contract**: `/admin/runs` and `/admin/runs/{run_id}` on every implementation (bearer admin token), returning the run fields above and steps.
- **Tool server**: four MCP tools, `GET /records`, per-call `toolserver.calls` rows with MCP client name/version (input to the MCP evaluation chapter).
- **Observability**: JSON logs, EMF metrics and names per spec 001 `contracts/observability.md` (`RunsSucceeded`, `RunsFailed`, `RunDurationMs`, `DigestPublished`, ...), landed by 001 T044-T047.
- **Harness core** (001 T025-T028): `client.py`, `fixtures.py`, `toolserver.py`, `report.py`, `conftest.py` (`--tier contract|live`, `--impl`), the initial fixture set (`basic-feature`, `large-diff`, `oversized-diff`, `risky-no-tests`, `prompt-injection`, `secret-in-diff`, `binary-only`, `bot-author`, `draft-pr`, `needs-context`) and `stub_bedrock.py` / `stub_github.py`, plus the compose stack.
- **Decisions**: Bedrock only with no Anthropic API fallback (D6); `us-east-1` for infra and `BEDROCK_REGION` (D6a); pinned global inference profiles from spike S12 (Sonnet 5.5 agents, Opus 5.5 judge, Haiku 4.5 helpers); migrate task shape; `destroy-all` leaves no snapshot unless `KEEP_FINAL_SNAPSHOT=1`; no shared agent logic across frameworks.
- **Bedrock issues log**: research §6 of spec 001 (table B1-B11 seeded, plus S12 findings).
- **CI**: per-component workflows and `conformance.yml` on the branch.

**From spec 002-multi-agent-safety**
- Multi-agent review (`pr_review` runs, coordinator plus three specialists) with delegation trace in `run_steps` (`delegation`, `delegation_result`), tables `reviews`, `findings`, `approval_requests` (migration 0003).
- Reliability and untrusted-input behavior, including `limit_exceeded` handling and the per-kind dedupe key, so an evaluation run over `pr_summary` and `pr_review` items is not dropped.
- Fixtures/expectations for injection and secret handling that the judge's `injection_safe` and `secret_leak` scores read (`prompt-injection`, `secret-in-diff`).
- Approval flow and chat/streaming scenarios (registered `just scenario` names) that the report describes.

**From spec 003-extended-capabilities**
- Retrieval (`retrieval` steps, `pr_summaries.sources`), so the `source_citation` score and the `needs-context` fixture work; long-context handling and memory (`memory_facts`, `/admin/memory`), the agent-as-MCP-server and A2A endpoints, dynamic tools and permissions (`tool_grants`), and the optional sandbox with each framework's recorded "supported" or "not natively supported" status (migration 0004).
- Their spike results (S1, S5, S7, S9, S13, and the sandbox spikes) under `specs/003-extended-capabilities/spikes/`, which the chapters cite.
- Additional fixtures and expectations they add to `shared/conformance/fixtures/`.

**Deployed state needed for live tasks**: `just up` brings up the tool server and all four implementations healthy, with `WATCHED_REPO`, `OWNER_LOGIN`, and credentials supplied through the environment (spec 001 quickstart section 0).

## Reconciliation

Before any work, verify the assumptions above against the as-built predecessors; the specs were written before code existed, so drift is expected.

Verify:
1. Each predecessor's checkpoint and Polish verification tasks are checked, and its as-built deviations are recorded.
2. Names and shapes: `agent_runs` and `run_steps` columns, `/admin/runs` fields, tool-server tool names, metric names, `just` target names, fixture ids and `expected.yaml` keys, stub scenario ids, and where each `cli.py` command lives.
3. Which stories were actually delivered per framework, and each framework's capability status (native, via integration, manual, not available; sandbox and A2A may be "not natively supported").
4. That the eval-report schema (`contracts/eval-report.schema.json` in this spec) and the report-validation code from 001 T025 agree.
5. That research §6 (spec 001) has been appended to by specs 001-003.

Mismatch handling: record each in `specs/004-evaluation-report/reconciliation.md` (headings: Verified, Deviations found, Spec/plan/tasks/contract changes made, Open questions), then update this spec, its plan, tasks, and contracts to match the as-built state. If a mismatch needs a change to a predecessor's code or contract, do not edit it silently; list it under Open questions for the owner. Phase 0 tasks in `tasks.md` carry this out; later phases do not start until Phase 0 is done.

## Out of scope here (owned by another spec)

- Webhook service, worker, run recording, tool server, deployment, up/down/pause/status, digest: spec 001-core-pr-steward.
- Multi-agent review, reliability and injection resistance, human approval, chat/streaming: spec 002-multi-agent-safety.
- Retrieval, agent-as-MCP-server, dynamic tools and permissions, long context and memory, sandbox, A2A: spec 003-extended-capabilities.
- Building any capability a framework lacks (FR-024, FR-037): recorded, not built.
- Deferred by the original spec: model portability/fallback and deterministic record/replay testing.
- Multi-tenant use, a UI beyond GitHub and tool-server inspection, other event sources, production HA.

## Clarifications

Carried over from the original session of 2026-09-28 (those that bear on this spec):

- Q: Should the report assess the frameworks' own evaluation capabilities? -> A: Yes (FR-049, FR-050, SC-021).
- Q: What is the final deliverable? -> A: A comprehensive comparison report with links to source code, evaluating each framework's suitability as Taskrabbit's multi-agent library of choice (User Story 9, FR-029, FR-046 to FR-048).
- Q: Which model provider, and what if Bedrock cannot do something? -> A: Amazon Bedrock for every model call, including the evaluation judge; no Anthropic API fallback; each Bedrock issue is logged during the work and highlighted in the report (FR-057). If a framework cannot use Bedrock at all, the provider decision returns to the evaluator.

## User Scenarios & Testing *(mandatory)*

### User Story 8 - Observability, cost tracking, and quality evaluation (Priority: P3)

For every run, the evaluator can see what happened (steps, tool calls, model calls, durations, errors), what it cost (tokens and estimated spend), and how good the output was. A fixed evaluation set of sample PRs with expected properties can be run against each implementation, producing comparable quality scores, including whether the summary was delivered correctly through the tool-server protocol.

**Why this priority**: This is what turns four working agents into an actual *evaluation*, and it is the meaning of "MCP evaluation" this spec assumes (see Assumptions). It is P3 because it needs the earlier stories to have something to measure.

**Independent Test**: Run the evaluation set against one implementation and obtain a report with per-sample quality results, latency, and cost; re-run and confirm results are comparable.

**Acceptance Scenarios**:

1. **Given** a completed run, **When** the evaluator opens its record, **Then** each model call and tool call is listed with timing and token usage.
2. **Given** the shared evaluation set, **When** it is run against each implementation, **Then** each produces a report in the same format so results can be compared directly.
3. **Given** a run that exceeds a configured spend or step limit, **When** the limit is hit, **Then** the run stops and records why. *(Behavior delivered by spec 001 under FR-016; this spec verifies it in the report tests.)*
4. **Given** errors in production runs, **When** they occur, **Then** an alert reaches the evaluator. *(Alarms delivered by spec 001 under FR-020; this spec confirms them in a deliberate-failure test, T152.)*

---

### User Story 9 - Comprehensive framework comparison report (Priority: P3)

After the implementations exist, the evaluator has a comprehensive written report that compares and contrasts the four frameworks and evaluates each one's suitability as Taskrabbit's multi-agent library of choice. It contains a side-by-side scorecard on shared dimensions (developer effort, how naturally each scenario was expressed, deployment complexity, runtime cost and latency, evaluation results, friction and gaps) plus narrative analysis of each framework's strengths, weaknesses, and fit against Taskrabbit's needs, including what evaluation capabilities each framework provides (see below), ending in a reasoned recommendation. Claims in the report link back to the source code, run records, and evaluation results that support them, so a reader can verify them.

**Why this priority**: It is the ultimate purpose of the exercise and the artifact a decision-maker will actually read, but it can only be completed once the implementations exist.

**Independent Test**: Read the report as someone deciding on a multi-agent library: verify every dimension has a value or reasoned note for all four frameworks, that the recommendation follows from the evidence, and that a sample of claims resolve to the code or results they cite.

**Acceptance Scenarios**:

1. **Given** all four implementations complete, **When** the report is read, **Then** no framework/dimension cell is empty.
2. **Given** a framework cannot support a scenario natively, **When** recorded, **Then** the report states what workaround was needed or that it was not achievable.
3. **Given** a claim about a framework's behavior or ergonomics, **When** the reader follows its link, **Then** it lands on the specific code, run record, or evaluation result that supports it.
4. **Given** the report's Taskrabbit suitability section, **When** read, **Then** each framework is assessed against the same stated criteria and the recommendation names which framework fits and under what conditions.
5. **Given** the report's evaluation-capabilities section, **When** read, **Then** it describes for each framework what it offers for evaluating agents (for example built-in scoring, datasets, experiment comparison, trace-based evaluation, and integration with external evaluation tools), what the evaluator actually used, and what had to be built by hand.
6. **Given** the code changes after the report is written, **When** links are followed, **Then** they still resolve to the code as evaluated (pinned to a fixed revision).
7. **Given** the report's Bedrock section, **When** read, **Then** it highlights every issue running these frameworks on Amazon Bedrock caused (capabilities lost or changed, workarounds, per-framework differences), each with its source and a marker for documented versus observed in this project.

---

### Edge Cases

- A predecessor story was not built for a framework, or was built for only some (US13 sandbox and US14 A2A are optional): the report section says so and the scorecard cell states "not built" or "not natively supported", never blank.
- The LLM judge is noisy or favors its own model family (risk R6): fixed rubric, a different and stronger judge model than the agents, and the limits stated in the report (FR-048).
- Bedrock throttling or quota limits differ across the four implementations when the evaluation runs against all four at once (retried per FR-012 in spec 001; recorded as a finding here if it affects results).
- A model or capability the agents or judge need is not enabled on Bedrock in the configured region: the eval run fails clearly at the start (`just doctor` from spec 001), not mid-run.
- Two implementations point at the same repository and tool server: records are attributed by implementation, so delivery correctness is scored per implementation.
- An implementation is not deployed when `just eval-all` runs: it is reported as absent, not silently skipped.
- Code changes between the evaluated revision and the report: links are permalinks pinned to the evaluated commit, and `just report-links` fails on any that do not resolve.
- A framework's cost figure is a client-side estimate (research §3 of spec 001): the report labels cost as estimated, not billed.

## Requirements *(mandatory)*

### Functional Requirements

Owned by this spec:

- **FR-019**: A shared evaluation set of sample PRs with expected properties MUST exist and MUST be runnable against every implementation, producing a report in an identical format that includes tool-server delivery correctness.
- **FR-029**: A comprehensive comparison report MUST be produced comparing and contrasting all four frameworks on developer effort, scenario fit, deployment complexity, cost, latency, evaluation results, and friction notes, with a side-by-side scorecard and narrative analysis per framework.
- **FR-046**: The report MUST evaluate each framework's suitability as Taskrabbit's multi-agent library of choice against one explicit, shared set of criteria stated in the report, and MUST end in a reasoned recommendation, including the conditions under which it would change.
- **FR-047**: Report claims MUST link to supporting source code, run records, or evaluation results, using links pinned to a fixed revision so they remain valid as the code evolves.
- **FR-048**: The report MUST distinguish measured results from the evaluator's judgment, and MUST state known limits of the evaluation (test repository scale, single model family, sample size).
- **FR-049**: The report MUST assess each framework's own evaluation capabilities, covering at least: defining test datasets, automated and model-graded scoring, evaluating tool-call and multi-agent behavior, evaluating from recorded traces, running and comparing experiments across versions, using evaluation in CI, and integrating with external evaluation platforms. Each capability MUST be marked native, via integration, manual, or not available, with a link to the code showing how it was used or to the evidence that it is not available.
- **FR-050**: The shared evaluation set and reports (FR-019) MUST run on every framework, and the report MUST separate what each framework's native evaluation tooling provided from what the shared harness supplied, so that the harness does not mask differences in native capability.
- **FR-057**: The report MUST include a prominent section highlighting every issue that using Amazon Bedrock caused (for example server-side tools, structured outputs, MCP connector, model access and inference-profile constraints, API-shape differences between frameworks, throttling), collected in a running log during the work, each entry citing its source or evidence and marked as documented or observed, so that Taskrabbit sees the cost of the Bedrock constraint per framework.

Extended here (base behavior owned by spec 001):

- **FR-018** (extended): spec 001 delivers the per-run record (steps, model calls, tool calls, timing, tokens, estimated cost, outcome) and its viewing endpoints. This spec adds best-effort OpenTelemetry export to an ADOT collector sidecar and confirms cost and duration of any single run can be looked up in under a minute (SC-009).
- **FR-020** (extended): spec 001 delivers alerts on errors and failed runs. This spec adds the collector sidecar and metric filters and proves the alarms fire in a deliberate-failure test (T152).

Inherited unchanged (owned by another spec; this spec depends on it): FR-016 (run limits; tested via T143), FR-021 (structured logs, no secrets), FR-022 (shared behavioral contract and conformance suite, whose all-four pass is SC-008 here), FR-023 and FR-024 (Bedrock only, recorded limitations), FR-025 to FR-028, FR-051 to FR-056 (used by T417 and T418).

FR-030 to FR-045 (extended capabilities) and FR-007, FR-008, FR-014, FR-015, FR-017 belong to specs 002 and 003; this spec only measures and reports them.

### Key Entities

- **Evaluation Sample / Evaluation Report**: A fixed PR fixture with expected properties, and the per-implementation scored results (a JSON file validated against `contracts/eval-report.schema.json`; not a database table).
- **Comparison Report**: The written comparison of the four frameworks, containing the scorecard, per-framework analysis, Taskrabbit suitability criteria and assessment, recommendation, and pinned links to evidence.
- **Framework Scorecard**: The comparison matrix of frameworks against dimensions, part of the report.
- **Suitability Criterion**: One stated dimension of Taskrabbit's needs, applied identically to every framework.

Used but owned elsewhere: Agent Run and Tool Server Record (spec 001), Review Finding and Consolidated Review (spec 002), Context Source, Memory Fact, Tool Grant, Sandbox Run (spec 003).

## Success Criteria *(mandatory)*

### Measurable Outcomes

Owned by this spec:

- **SC-008**: All four implementations pass the shared conformance suite, and the evaluation report format is identical across them.
- **SC-009**: The evaluator can look up the cost and duration of any single run in under 1 minute.
- **SC-010**: The finished report has every framework/dimension cell filled, applies the same suitability criteria to all four frameworks, and ends with a clear recommendation for Taskrabbit's multi-agent library.
- **SC-019**: In a spot check of 10 randomly chosen report claims, at least 9 link to the specific code, run record, or result that supports them, and 100% of links resolve.
- **SC-020**: A decision-maker who was not involved can read the report and state the recommendation and its main tradeoffs in under 30 minutes.
- **SC-021**: The report's evaluation-capabilities section covers all seven listed capabilities for all four frameworks, with no cell empty and each marked native, via integration, manual, or not available.
- **SC-024**: The report's Bedrock section covers all four frameworks, each issue has a cited source or evidence link and a documented-or-observed marker, and every issue logged during the work appears in it.

Measured here, owned by another spec (this spec produces the evidence; the owner spec defines the criterion): SC-001 (delivery within 2 minutes across the evaluation set), SC-006 (injection PRs in the set cause no out-of-policy action or leaked secret), SC-011 and SC-016 (source citation and oversized-diff coverage, via judge scores), SC-004, SC-022, SC-023 (deployment, resume, pause, cost, and teardown timings re-verified in T417 and T418).

## Assumptions

- **Frameworks**: "Pydantic API" in the original request means Pydantic AI. The four frameworks are LangGraph, Claude Agent SDK, Mastra, and Pydantic AI.
- **Model**: All implementations use the same Claude model family through Amazon Bedrock in the evaluator's AWS account. The judge is Claude Opus 5.5 (a different, stronger model than the Sonnet 5.5 agents), via its pinned global inference profile from spike S12 in spec 001. No Anthropic API key exists.
- **"MCP evaluation"**: Interpreted as evaluating how each framework discovers and calls tools on an MCP server, and how correctly and reliably it does so, rather than evaluating a third-party MCP product. The reference tool server's `toolserver.calls` data is the evidence.
- **Taskrabbit suitability criteria**: Taskrabbit's requirements are not yet written down. The report's criteria are proposed in research D17 and confirmed with the evaluator in T155. Likely candidates: language and stack fit, ability to run multiple cooperating agents reliably, security and guardrails, observability, evaluation tooling, operational and deployment burden, cost, maintenance and vendor risk, community maturity, and team learning curve.
- **Evaluation capabilities**: "Evaluation" in the report covers both how good each framework's agents are (measured with the shared set, User Story 8) and how well each framework helps a team evaluate agents in general. Third-party evaluation platforms are in scope only to the extent a framework integrates with them.
- **Audience**: The report's readers are Taskrabbit engineering decision-makers; it may reference Taskrabbit's needs but contains no confidential Taskrabbit data.
- **Credentials**: The evaluator supplies cloud credentials, a GitHub token, and Bedrock model access (including Opus 5.5 for the judge); the project never creates them.
- **Cost**: Live evaluation runs spend on Bedrock; each is a task marked as needing owner approval. The environment is torn down between sessions (spec 001 D18). Figures in the report are labeled estimated unless measured in T418.
- **Scale and limits**: One test repository, tens of fixtures, one model family, small samples; these limits are stated in the report (FR-048).
- **Conventions**: The project follows the constitution in `.specify/memory/constitution.md`, which wins over this spec.
