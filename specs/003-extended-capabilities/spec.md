# Feature Specification: Extended Agent Capabilities

**Feature Branch**: `001-agent-framework-comparison` (shared branch for the four-spec split; this spec lives in `specs/003-extended-capabilities/`)

**Created**: 2026-09-30

**Status**: Draft

**Split from**: the original single feature "Agent Framework Comparison" (dated 2026-09-28). The original is cut into four specs built one after another: `001-core-pr-steward`, `002-multi-agent-safety`, `003-extended-capabilities` (this spec), `004-evaluation-report`. Original IDs (FR-, SC-, US, T, S#, D#) are kept so everything stays traceable to the original.

**Input**: "I want to build and deploy the same agent in several different frameworks to evaluate them. LangGraph, Claude Agent SDK, Mastra, and Pydantic AI. The agent should be hosted, listen for webhooks from GitHub, and when a PR is created, call an MCP server with a summary of what the PR is accomplishing to demonstrate how MCP evaluation works. It should also have a daily workflow that publishes a digest of all PRs created the previous day, and a multi-agent workflow that demonstrates how agents communicate. Deployment infrastructure goes into AWS using OpenTofu. Suggest other common things agents have to do so the spec fully demonstrates how these libraries work."

## Overview

The evaluator (the repo owner) is judging four agent frameworks (**LangGraph**, **Claude Agent SDK**, **Mastra**, **Pydantic AI**) by building the same "PR steward" agent four times against one shared behavioral contract. Spec 001 delivered the core loop (webhook, summary, tool server, hosting, digest). Spec 002 delivered multi-agent review, reliability and untrusted-input handling, human approval, and the conversational trigger.

This spec adds the **extended agent capabilities** that production agents routinely need beyond that base, each expressed in every framework's own idiom and recorded as native, via integration, manual, or not supported:

- repository retrieval beyond the diff, with cited sources (User Story 10);
- the agent exposed as an MCP server (User Story 11);
- dynamic tool loading and per-tool permission policies (User Story 12);
- long-context handling and durable memory across runs, with owner correction (User Story 15);
- sandboxed code execution, optional and only where trivial (User Story 13);
- cross-framework specialists over an agent-to-agent protocol (User Story 14).

All six are P3. None is required for the core loop or the multi-agent review, so the outcome "not natively supported" or "not supported on Bedrock" for a framework is a valid, recorded result and is never worked around silently (FR-024). Evidence and status per framework feed the comparison report built in spec 004.

## Depends on / Inherited from predecessors

This spec assumes specs 001 and 002 are complete and their quickstarts pass. It does not rebuild any of the following; Phase 0 of `tasks.md` verifies each against the as-built code.

**From spec 001 (core loop and hosting)**

| Area | What is assumed |
|---|---|
| Shared contract | `contracts/http-api.yaml` core paths (`/health`, `/ready`, `/webhooks/github`, `/internal/schedule`, `/admin/runs`, `/admin/runs/{run_id}`), `contracts/work-queue.md`, `contracts/mcp-tool-server.md`, `contracts/environment.md` (including `ADMIN_TOKEN`, `WATCHED_REPO`, `REMOTE_SPECIALISTS`, `MAX_STEPS`, `MAX_RUN_SECONDS`, `MAX_RUN_COST_USD`), `contracts/observability.md` |
| Database | migration `0001` tables `events`, `work_items`, `pr_summaries` (with `sources` JSON and `condensed`), `digests`, `agent_runs`, `run_steps`, and `0002` `toolserver`; the `shared/db` migrate runner and the one-shot ECS migrate task; the `vector` extension created by migrate as master. `agent_runs.kind` includes `mcp_summarize` (nullable `work_item_id` for that kind) and `run_steps.kind` includes `tool_load`, `retrieval`, `memory_read`, `memory_write`, `delegation`, `delegation_result`; `run_steps.outcome` includes `refused`, so this spec adds no ALTER to 001 tables |
| Implementations | The four deployable services with webhook receiver, SQS worker, per-run limits, `agent_runs`/`run_steps` recording, `/admin/runs`, GitHub fetch tools (PyGithub/Octokit), the summary path (`summary.py` / `summary.ts`), the tool-server MCP client, and `admin.py` / `admin.ts` |
| Tool server | `record_pr_summary`, `record_review`, `record_digest`, `list_records`; `digests` rows from the daily digest (US3) that `get_latest_digest` reads |
| Conformance harness | `shared/conformance` (`client.py`, `fixtures.py`, `toolserver.py`, `report.py`, `conftest.py` with `--tier` and `--impl`), `stub_bedrock.py` (Converse and Invoke, scripted scenarios, fault injection), `stub_github.py` (including code search, file contents, list PRs), `compose.yaml`, fixtures `needs-context`, `oversized-diff`, `large-diff`, `just scenario`, `just eval` entry points |
| Hosting | Deployed environment (ECS, ALB path prefixes, CloudFront stable URL that forwards MCP, A2A, admin and SSE traffic), `just up/down/pause/resume/status/deploy/smoke/plan`, `infra/modules/implementation` |
| Decisions | Bedrock only with no Anthropic API fallback; `us-east-1` for infra and `BEDROCK_REGION`; pinned inference profiles and per-framework Bedrock findings from spike S12; per-framework stub-endpoint results from spikes S8 (a framework whose stub override failed has a documented fallback that this spec's contract tests must follow); the Bedrock issues log structure (spec 001 `research.md` §6) |

**From spec 002 (multi-agent and safe interaction)**

| Area | What is assumed |
|---|---|
| Database | migration `0003` tables `reviews`, `findings`, `approval_requests` |
| Multi-agent review | Coordinator plus summarizer, risk, and test-coverage specialists (`agents/review.py` / `review.ts`), structured findings, `missing_perspectives`, `disagreements`, delegation trace in `run_steps`, per-specialist timeout; the risk reviewer is the specialist this spec serves over A2A |
| Safety | Untrusted-input handling (FR-014): the per-implementation wrapper that marks external text as data, and the per-implementation secret detector/scrubber that this spec reuses for retrieved content and memory writes; retry with backoff (FR-012); the Claude Agent SDK `SessionStore` adapter |
| Approval | The approval flow (`approval_requests`, `/approve <id>` and `/reject <id>` via `issue_comment`, expiry sweep, exactly-once post) that `requires_approval` tool grants reuse |
| Conversation | Thread context storage and `@steward` commands with `POST /chat/stream` (User Story 7) that long-context handling extends (FR-042) |
| Worker | A dedupe key per work-item kind (delivery id plus kind); this spec adds no new work-item kind, because `mcp_summarize` runs have no queue item |
| Handoff | Spec 002's "Handoff to 003" section and its `reconciliation.md`, which list as-built deviations |

**Environment and secrets inherited**: no new Bedrock models. New configuration names introduced here are in `contracts/environment-additions.md` and extend spec 001's `contracts/environment.md`.

## Reconciliation

Because this spec is built after 001 and 002 are finished, it MUST be reconciled against what was actually built before any new work starts. Phase 0 of `tasks.md` does this:

1. Confirm every checkpoint and verification task of specs 001 and 002 is checked, and read their recorded as-built deviations (their "Handoff" sections and `reconciliation.md` files).
2. Diff the as-built code, contracts, and schema against every row of the two tables above, and record the result in `specs/003-extended-capabilities/reconciliation.md` (Verified, Deviations found, Spec/plan/tasks/contract changes made, Open questions).
3. Handle each mismatch by updating this spec, its plan, `tasks.md`, `data-model.md`, and `contracts/` to match reality (not the other way round), adding new tasks from the reserved range T300-T399 where needed. A mismatch that cannot be absorbed here (for example a missing `run_steps.kind` value or a wrong `agent_runs.kind` constraint) is fixed by a task in this spec that adds a migration `0004` ALTER, and is recorded as a deviation.
4. Run `/speckit-analyze` on this spec's artifacts before Phase 1 begins.

Assumptions most likely to need adjustment: the exact file names in each implementation (`summary.py`, `review.py`, `admin.py` and Mastra equivalents), whether `agent_runs.kind` and `run_steps.kind` CHECK constraints already contain the values above, whether the migrate runner applies `0003`/`0004` per implementation schema in order, and whether the Claude Agent SDK and Mastra stub-endpoint fallbacks (spike S8) affect how contract-tier tests for US10-US15 can drive the model.

## Out of scope here (owned by another spec)

- Webhook, worker, PR summary, tool server, hosting, digest, up/down/pause/resume/status: spec 001.
- Multi-agent review, reliability and untrusted-input defenses, human approval, conversational trigger and streaming: spec 002. This spec only extends them.
- Observability/cost/quality evaluation (User Story 8), the shared evaluation harness runs and report format, native evaluation tooling, the comparison report and its Bedrock chapter, and whole-environment verification: spec 004. This spec supplies the behavior, contract tests, live scenarios, spike findings, and per-framework capability status that 004 measures and reports.
- Model portability/fallback and deterministic record/replay testing: deferred, not part of any of the four specs.

## Clarifications

### Session 2026-09-28 (carried from the original spec)

- Q: Should the four implementations be able to call each other across frameworks over an agent-to-agent protocol? → A: Yes, as one extra P3 scenario (User Story 14); the core multi-agent review (spec 002 User Story 4) stays inside each framework.
- Q: Should long-context handling and long-term memory across runs be exercised? → A: Yes (User Story 15, P3).
- Q: Which additional agent capabilities should be exercised? → A: Codebase retrieval, the agent exposed as an MCP server, and dynamic tool loading with per-tool permissions are required (P3). Sandboxed code execution is included only where a framework supports it with trivial effort.
- Q: Which model provider do the four implementations use, and what if Bedrock cannot do something the Anthropic API can? → A: Amazon Bedrock for every model call in all four frameworks; no fallback to the Anthropic API; a feature Bedrock lacks is recorded as "not supported on Bedrock" and not worked around; every Bedrock issue is logged and later highlighted in the report (FR-057, spec 004).

## User Scenarios & Testing *(mandatory)*

### User Story 10 - Repository context beyond the diff (Priority: P3)

When summarizing or reviewing a PR, the agent can look up relevant material in the repository (related files, existing conventions, prior PRs touching the same area) rather than relying only on the diff, and cites what it used.

**Why this priority**: Retrieval over a codebase is a core agent capability, and it improves summary quality in ways the evaluation set can measure.

**Independent Test**: Open a PR whose meaning is unclear from the diff alone (e.g. it changes a function whose purpose is documented elsewhere); verify the summary reflects the external context and names the sources.

**Acceptance Scenarios**:

1. **Given** a PR whose purpose depends on code outside the diff, **When** it is summarized, **Then** the summary reflects that context and lists the files or PRs consulted.
2. **Given** the needed context does not exist in the repository, **When** the agent searches, **Then** it says so rather than inventing context.
3. **Given** the repository is large, **When** the agent searches, **Then** it retrieves only relevant material and stays within the run's step and spend limits.

---

### User Story 11 - The agent is itself callable as an MCP server (Priority: P3)

In addition to calling the reference tool server, each implementation exposes its own capabilities (for example "summarize PR number N", "get latest digest") to outside MCP clients, so that any MCP-capable client can use the agent as a tool.

**Why this priority**: It shows the other half of MCP support, serving rather than consuming, and how each framework handles it.

**Independent Test**: Connect a generic MCP client to a deployed implementation, discover its tools, and invoke the summarize tool for an existing PR.

**Acceptance Scenarios**:

1. **Given** a deployed implementation, **When** an authorized MCP client connects, **Then** it can discover the agent's advertised tools.
2. **Given** a connected client, **When** it invokes the summarize tool with a valid PR number, **Then** it receives a summary of that PR.
3. **Given** a client without valid credentials, **When** it connects, **Then** it is refused.
4. **Given** an invalid PR number, **When** the tool is invoked, **Then** a clear error is returned rather than a fabricated summary.

---

### User Story 12 - Dynamic tool loading and per-tool permissions (Priority: P3)

The agent does not hold every tool at all times. It starts with a minimal set and loads additional tools (or tool groups) only when a task needs them, and each tool is governed by a permission policy: allowed, requires approval, or denied. Calls to a denied tool are refused and recorded.

**Why this priority**: Tool sprawl and least-privilege are practical concerns for real agents, and frameworks vary widely in how they express them.

**Independent Test**: Run a task that needs an extra tool group and confirm it is loaded on demand; then attempt a call to a denied tool and confirm refusal.

**Acceptance Scenarios**:

1. **Given** a task that needs a tool not in the initial set, **When** the agent runs, **Then** the tool is loaded on demand and the load is recorded in the run.
2. **Given** a tool marked denied, **When** the agent (or injected content) attempts to call it, **Then** the call is refused and the refusal is recorded.
3. **Given** a tool marked requires-approval, **When** it is called, **Then** it follows the approval flow of User Story 6 (spec 002).
4. **Given** a task that needs no extra tools, **When** it runs, **Then** no additional tools are loaded.

---

### User Story 15 - Long-context handling and memory across runs (Priority: P3)

The agent copes with material too large to fit in one pass (a huge diff, a long PR conversation, a long-running comment thread) by condensing or splitting it while preserving what matters. It also remembers durable facts across separate runs, such as repository conventions, a reviewer's stated preferences, and past decisions on similar PRs, and uses them in later summaries and reviews. The evaluator can inspect and correct what the agent has remembered.

**Why this priority**: Context limits and memory are where frameworks differ most in built-in support, and both directly affect quality on real repositories. It builds on User Story 7 (spec 002), User Story 1 (spec 001), and User Story 10.

**Independent Test**: Run a PR with a diff larger than a single pass can hold and verify the summary covers its major parts. Then state a convention in one PR thread, open a later, unrelated PR that touches it, and verify the review applies the convention.

**Acceptance Scenarios**:

1. **Given** a PR whose diff exceeds what fits in one pass, **When** it is summarized, **Then** the summary covers every major changed area and states what was condensed.
2. **Given** a long-running comment thread, **When** the agent answers a follow-up, **Then** it uses the relevant earlier context even though the full thread is not held verbatim.
3. **Given** a convention stated in an earlier run, **When** a later run on a different PR touches it, **Then** the agent applies it and identifies where it learned it.
4. **Given** a remembered fact that is wrong or outdated, **When** the evaluator corrects or deletes it, **Then** later runs no longer use it.
5. **Given** remembered content from PRs, **When** stored, **Then** it contains no detected secrets and is treated as untrusted data when reused (FR-014, spec 002).

---

### User Story 13 - Sandboxed code execution (Priority: P3, optional)

Where a framework supports it with trivial effort, the agent can run the PR's test suite (or a provided script) in an isolated environment and include the result in its review. Frameworks that do not support this trivially are recorded as "not natively supported" in the scorecard rather than having it built for them.

**Why this priority**: Code execution is a common agent capability, but it carries safety risk and infrastructure cost, so it is limited to cheap cases.

**Independent Test**: For a supporting framework, open a PR with a failing test and confirm the review reports the failure from an isolated run that had no access to secrets.

**Acceptance Scenarios**:

1. **Given** a PR with a failing test and a supporting framework, **When** the review runs, **Then** the failure is reported with output from the isolated run.
2. **Given** PR code that attempts to read secrets or reach internal systems, **When** it runs in the sandbox, **Then** it cannot.
3. **Given** a run that exceeds the time or resource limit, **When** it is stopped, **Then** the review notes the run was cut off.
4. **Given** a framework without trivial support, **When** the report is produced (spec 004), **Then** it states this rather than showing a workaround. Delivered here: the recorded status for that framework (spike file and the framework's `CLAUDE.md`).

---

### User Story 14 - Cross-framework specialists over an agent-to-agent protocol (Priority: P3)

The multi-agent review can be run in a mixed mode in which the coordinator from one implementation delegates to specialists hosted by other implementations (built in different frameworks) through an open agent-to-agent protocol. The evaluator can see the same delegation trace as in User Story 4 (spec 002), now spanning framework boundaries.

**Why this priority**: It shows whether the frameworks interoperate, not just how each works alone. It is one optional scenario so the core loop stays independent of it.

**Independent Test**: Configure one implementation's coordinator to use a specialist hosted by a different implementation; open a PR and verify the consolidated review includes that specialist's finding and the trace names both frameworks.

**Acceptance Scenarios**:

1. **Given** a coordinator configured with a remote specialist from another framework, **When** a PR is reviewed, **Then** the consolidated review includes the remote specialist's finding attributed to it.
2. **Given** a remote specialist is unreachable or unauthorized, **When** the review runs, **Then** the coordinator delivers a labeled partial result as in User Story 4 (spec 002).
3. **Given** a completed mixed review, **When** the evaluator views the trace, **Then** each cross-framework delegation and response is visible with the framework of each agent.
4. **Given** every implementation, **When** it is asked to serve as a remote specialist, **Then** it advertises its capabilities and accepts authenticated delegations only from configured peers.

---

### Edge Cases

Owned by this spec:

- Two remembered facts contradict each other (newer vs. older, or one PR's convention vs. another's).
- The memory grows without bound over many runs.
- A condensed summary of the diff drops the one changed line that matters.
- Hostile PR content attempts to plant a false or malicious "convention" in memory.
- The watched repository is private and the agent lacks access to some content it wants to retrieve.
- Retrieved repository content itself contains injected instructions (it is untrusted, like the PR).
- An external MCP client requests a PR from a repository outside the watched allowlist.
- A dynamically loaded tool is unavailable or its advertised schema differs from what was expected.
- Code run in the sandbox produces enormous output or never terminates.
- Two implementations are configured as each other's remote specialist, causing a delegation loop.
- A remote specialist speaks a different protocol version than the coordinator expects.

Inherited (owned by another spec, still exercised here):

- A capability the agents need is not available on Bedrock in the configured region (spec 001; here this shows up for server-side tool search on Converse paths and provider-side code execution, each recorded as "not supported on Bedrock").
- Bedrock throttling with four implementations at once (spec 001 FR-012 retry; recorded as a finding if it affects results here).

## Requirements *(mandatory)*

### Functional Requirements (owned by this spec)

**Extended capabilities**

- **FR-030**: Each implementation MUST be able to search the watched repository's files and history during a run, use the results in its summary or review, and list the sources it consulted.
- **FR-031**: Retrieved repository content MUST be treated as untrusted data under FR-014 (spec 002), and retrieval MUST honor the run's step and spend limits (FR-016, spec 001).
- **FR-032**: Each implementation MUST expose an MCP server interface advertising at least a "summarize PR" tool and a "get latest digest" tool.
- **FR-033**: The agent's MCP interface MUST require authentication, MUST restrict requests to the watched repository allowlist, and MUST return explicit errors rather than fabricated results.
- **FR-034**: Each implementation MUST start a run with a minimal tool set and load additional tools on demand, recording each load in the run record.
- **FR-035**: Each tool MUST carry a permission policy (allowed, requires approval, denied); denied calls MUST be refused and recorded, and requires-approval calls MUST follow FR-015 (spec 002).
- **FR-036**: Where a framework supports sandboxed code execution with trivial effort, the implementation SHOULD run the PR's tests in an isolated environment with no access to secrets or internal systems, bounded by time and resource limits, and include the results in the review.
- **FR-037**: Where a framework does not support sandboxed execution trivially, the report MUST record it as not natively supported; no custom sandbox is built for it. (This spec records the status per framework; spec 004 states it in the report.)
- **FR-038**: Each implementation MUST be able to act as a remote specialist and as a coordinator's client over an open agent-to-agent protocol, so any implementation's coordinator can delegate to any other implementation's specialist.
- **FR-039**: Cross-framework delegation MUST require authentication between peers, MUST be limited to configured peers, and MUST appear in the delegation trace with the framework of each participant.
- **FR-040**: A failed or unreachable remote specialist MUST degrade to a labeled partial result per FR-008 (spec 002), and the core multi-agent workflow (FR-007, spec 002) MUST NOT depend on cross-framework calls.
- **FR-041**: When input exceeds what one pass can hold, each implementation MUST condense or split it so every major changed area is covered, and MUST state in the output what was condensed or omitted. Split of the original: spec 001 delivers only graceful degradation on a large diff (US1 scenario 2: a summary that says it covered a subset); this spec delivers coverage of every major changed area and the condensed-summary test (moved here from spec 001 T034 (its original ID)).
- **FR-042**: Each implementation MUST retain conversation context across a long thread without holding it verbatim, so follow-ups can use relevant earlier content. (Extends the thread context and `@steward` conversation delivered by spec 002 User Story 7.)
- **FR-043**: Each implementation MUST persist durable facts (repository conventions, stated preferences, prior decisions) across runs, apply them in later runs, and cite where each was learned.
- **FR-044**: The evaluator MUST be able to list, correct, and delete remembered facts, and deletions MUST take effect in the next run.
- **FR-045**: Remembered content MUST exclude detected secrets, MUST be treated as untrusted data when reused (FR-014, spec 002), and MUST be bounded in size, with a stated rule for what is discarded.

### Requirements inherited from other specs (not delivered here)

| Requirement | Owner | How this spec relies on it |
|---|---|---|
| FR-003 (discover tools via the MCP client), FR-004 | spec 001 | Dynamic tool loading (US12) and `record: true` on `summarize_pr` use the existing client and tool server |
| FR-007, FR-008 | spec 002 | A2A specialist is the risk reviewer of the review workflow; remote failure follows FR-008 |
| FR-012 | spec 002 (retry) | Retrieval, MCP and A2A calls use the same backoff |
| FR-014 | spec 002 | Retrieved content, remembered content and remote specialist input are untrusted data |
| FR-015 | spec 002 | `requires_approval` tools use the approval flow |
| FR-016 | spec 001 | Retrieval, MCP-triggered summaries and sandbox runs are inside step, time and spend limits |
| FR-017 | spec 002 | Thread context (FR-042) builds on it |
| FR-018, FR-021 | spec 001 (basic) / spec 004 (full) | Steps written here (`retrieval`, `tool_load`, `memory_*`, refusals) go into the existing run record |
| FR-022, FR-023, FR-024 | spec 001 | New contract tests extend the same conformance suite; Bedrock only; limitations recorded, not worked around |
| FR-029, FR-049, FR-050, FR-057 | spec 004 | The report consumes this spec's evidence and Bedrock log entries |

### Key Entities

Introduced or extended here:

- **Context Source**: A repository file or prior PR consulted during a run, recorded with the run and cited in the output. Held inline as JSON on `pr_summaries.sources` and `run_steps.detail`, not a table.
- **Tool Grant**: A tool's permission policy (allowed, requires approval, denied) and whether it is loaded initially or on demand.
- **Sandbox Run**: An isolated execution of PR code, with its limits, output, and outcome.
- **Memory Fact**: A durable remembered statement (a convention, preference, or decision) with its source PR or thread, date, and status (active, corrected, deleted).

Used from predecessors: PR Summary, Agent Run (spec 001); Review Finding, Consolidated Review, Approval Request (spec 002); Tool Server Record (spec 001).

## Success Criteria *(mandatory)*

### Measurable Outcomes (owned by this spec)

- **SC-011**: On evaluation PRs whose purpose depends on code outside the diff, summaries cite the relevant source in at least 90% of cases and never cite a source that was not consulted.
- **SC-012**: A generic MCP client can connect to each implementation, discover its tools, and receive a correct summary for a valid PR within 2 minutes; unauthenticated connections are refused in 100% of trials.
- **SC-013**: In 100% of trials, calls to a denied tool are refused and recorded, and tools outside the task's needs are not loaded.
- **SC-014**: For every framework where sandboxed execution is supported, sandboxed code cannot reach secrets in 100% of trials; for every other framework, the report says not natively supported. Split: this spec delivers the sandbox behavior, its tests, and the recorded status per framework; spec 004 delivers the report statement.
- **SC-015**: For each of the 12 ordered pairs of frameworks (coordinator, remote specialist), a mixed review completes with the remote finding attributed and the trace showing both frameworks; an unreachable remote specialist yields a labeled partial result in 100% of trials.
- **SC-016**: For oversized evaluation PRs, summaries cover at least 90% of the major changed areas and always disclose what was condensed.
- **SC-017**: In a two-run memory test, the second run applies the convention learned in the first in at least 90% of trials and cites its source, and a deleted fact is never used again.
- **SC-018**: Injected false "conventions" planted through PR content are stored or applied in 0 trials.

Measurement note: this spec delivers the contract-tier tests and the live scenarios that produce these numbers. Spec 004 folds them into the shared evaluation set and the report, and does not redefine them.

## Assumptions

- **Frameworks**: "Pydantic API" in the request is taken to mean Pydantic AI. The four frameworks are LangGraph, Claude Agent SDK, Mastra, and Pydantic AI.
- **Model**: All implementations use the same Claude model family through Amazon Bedrock in the evaluator's AWS account, authenticated with the deployed workload's cloud identity. Model and region decisions are spec 001's and are not reopened.
- **Multi-agent design**: The A2A specialist is the "risk reviewer" from the coordinator-plus-three-specialists design (spec 002).
- **Repository scope**: Agents watch an evaluator-designated test repository (or short allowlist). MCP and retrieval requests outside the allowlist are refused.
- **Authorized users**: Only the repository owner may command the agent or correct memory in v1; the agent MCP interface, `/admin/memory` and A2A use bearer tokens (`ADMIN_TOKEN` for MCP and admin; per-peer tokens for A2A).
- **Sandbox scope**: US13 is spike-first and optional; "not natively supported" is an acceptable, recorded outcome, and no custom sandbox or third-party vendor is added.
- **Memory bounds**: Default cap 200 active facts with least-recently-used eviction (research D12), set by configuration.
- **Deferred capabilities**: Model portability/fallback and deterministic record/replay testing are not part of this round.
- **Out of scope**: Multi-tenant use, a user interface beyond GitHub and the tool-server inspection view, other event sources, and production-grade high availability.

## Handoff to 004

What this spec promises the evaluation and report spec:

- Contract-tier tests: `test_us10_retrieval.py`, `test_us11_agent_mcp.py`, `test_us12_tools.py`, `test_us15_context_memory.py`, `test_us13_sandbox.py`, `test_us14_a2a.py`, plus live scenarios `context-memory`, `mcp-server`, `tools`, `sandbox`, `a2a-mixed`, registered with `just scenario`.
- Fixtures with tags `needs-context`, `oversized`, `injection`, `memory-convention`, `injected-convention`, `failing-test` for the shared evaluation set.
- Per-framework capability status (native, via integration, manual, not supported on Bedrock, not natively supported) for each of FR-030..045, recorded in each implementation's `CLAUDE.md` and in the spike files under `specs/003-extended-capabilities/spikes/`, each with a code link.
- Bedrock issues appended to spec 001 `research.md` §6 with basis (documented or observed) and source.
- As-built deviations from this spec, recorded in this spec's `reconciliation.md` and in the section below before spec 004 starts.

### As-built deviations

None recorded yet. Filled in by the Polish phase (`tasks.md` T334).
