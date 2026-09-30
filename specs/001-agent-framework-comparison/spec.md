# Feature Specification: Agent Framework Comparison

**Feature Branch**: `001-agent-framework-comparison`

**Created**: 2026-09-28

**Status**: Draft

**Input**: User description: "I want to build and deploy the same agent in several different frameworks to evaluate them. LangGraph, Claude Agent SDK, Mastra, and Pydantic AI. The agent should be hosted, listen for webhooks from GitHub, and when a PR is created, call an MCP server with a summary of what the PR is accomplishing to demonstrate how MCP evaluation works. It should also have a daily workflow that publishes a digest of all PRs created the previous day, and a multi-agent workflow that demonstrates how agents communicate. Deployment infrastructure goes into AWS using OpenTofu. Suggest other common things agents have to do so the spec fully demonstrates how these libraries work."

## Overview

The evaluator (the repo owner) wants to judge four agent frameworks by building the *same* agent four times against one shared behavioral contract, deploying each to the cloud, and comparing them side by side. The reference agent is a "PR steward" for a GitHub repository. It reacts to pull requests, publishes summaries to an external tool server, produces a daily digest, and coordinates several cooperating agents. The scenarios below deliberately cover the things production agents routinely need (tool use, scheduling, multi-agent handoff, durability, safety, approval gates, streaming, observability, evaluation) so that each framework is exercised on realistic ground rather than a toy demo.

Frameworks under evaluation: **LangGraph**, **Claude Agent SDK**, **Mastra**, **Pydantic AI**.

## Clarifications

### Session 2026-09-28

- Q: Should the four implementations be able to call each other across frameworks over an agent-to-agent protocol? → A: Yes, as one extra P3 scenario (User Story 14); the core multi-agent review (User Story 4) stays inside each framework. Model portability/fallback and deterministic record/replay testing are deferred.
- Q: Should long-context handling and long-term memory across runs be exercised? → A: Yes (User Story 15, P3).
- Q: Should the report assess the frameworks' own evaluation capabilities? → A: Yes (FR-049, FR-050, SC-021).
- Q: Should spinning the environment up and down be easy? → A: Yes (FR-051 to FR-056, SC-022, SC-023): one-command up, down, pause, resume, and status, with data preserved across teardown.
- Q: What is the final deliverable? → A: A comprehensive comparison report with links to source code, evaluating each framework's suitability as Taskrabbit's multi-agent library of choice (User Story 9, FR-029, FR-046 to FR-048).
- Q: Which additional agent capabilities should be exercised? → A: Codebase retrieval, the agent exposed as an MCP server, and dynamic tool loading with per-tool permissions are required (P3). Sandboxed code execution is included only where a framework supports it with trivial effort.
- Q: Which model provider do the four implementations use, and what if Bedrock cannot do something the Anthropic API can? → A: Amazon Bedrock, for every model call (agents, evaluation judge, helper models) in all four frameworks, because Taskrabbit runs on Bedrock and the evaluation must reflect the environment it would adopt. There is no fallback to the Anthropic API; a feature Bedrock lacks is recorded as "not supported on Bedrock" and not worked around. Every issue Bedrock causes (limits, workarounds, differences between frameworks) is logged during the work and highlighted in the final report (FR-057). If a framework cannot use Bedrock at all, the provider decision returns to the evaluator.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - PR opened produces a summary delivered to a tool server (Priority: P1)

When a pull request is opened in a watched repository, the agent receives the notification, reads the PR (title, description, changed files, diff), writes a concise summary of what the PR accomplishes, and delivers that summary to an external tool server using the standard tool-server protocol. This is the core loop the four implementations are compared on.

**Why this priority**: It is the minimum viable agent: inbound event, reasoning over external data, outbound tool call. Every other story builds on it, and it demonstrates how the tool-server protocol is consumed from each framework.

**Independent Test**: Open a PR in a test repository with one implementation running; verify the tool server records exactly one summary for that PR within the target time, and that the summary accurately describes the change.

**Acceptance Scenarios**:

1. **Given** a running implementation and a watched repository, **When** a PR is opened, **Then** the tool server receives one summary record containing the PR identifier, title, author, and a plain-language summary of the change's purpose.
2. **Given** a PR with a very large diff, **When** it is opened, **Then** the agent still produces a summary (degrading gracefully, e.g. by summarizing a subset and stating that it did) and does not fail.
3. **Given** a PR is edited or reopened after the initial summary, **When** the notification arrives, **Then** the agent does not create a duplicate record for the same PR state.
4. **Given** the tool server is unavailable, **When** a PR is opened, **Then** the failure is recorded and the delivery is retried until it succeeds or is clearly marked as failed.

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

### User Story 8 - Observability, cost tracking, and quality evaluation (Priority: P3)

For every run, the evaluator can see what happened (steps, tool calls, model calls, durations, errors), what it cost (tokens and estimated spend), and how good the output was. A fixed evaluation set of sample PRs with expected properties can be run against each implementation, producing comparable quality scores, including whether the summary was delivered correctly through the tool-server protocol.

**Why this priority**: This is what turns four working agents into an actual *evaluation*, and it is the meaning of "MCP evaluation" this spec assumes (see Assumptions). It is P3 because it needs the earlier stories to have something to measure.

**Independent Test**: Run the evaluation set against one implementation and obtain a report with per-sample quality results, latency, and cost; re-run and confirm results are comparable.

**Acceptance Scenarios**:

1. **Given** a completed run, **When** the evaluator opens its record, **Then** each model call and tool call is listed with timing and token usage.
2. **Given** the shared evaluation set, **When** it is run against each implementation, **Then** each produces a report in the same format so results can be compared directly.
3. **Given** a run that exceeds a configured spend or step limit, **When** the limit is hit, **Then** the run stops and records why.
4. **Given** errors in production runs, **When** they occur, **Then** an alert reaches the evaluator.

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
3. **Given** a tool marked requires-approval, **When** it is called, **Then** it follows the approval flow of User Story 6.
4. **Given** a task that needs no extra tools, **When** it runs, **Then** no additional tools are loaded.

---

### User Story 13 - Sandboxed code execution (Priority: P3, optional)

Where a framework supports it with trivial effort, the agent can run the PR's test suite (or a provided script) in an isolated environment and include the result in its review. Frameworks that do not support this trivially are recorded as "not natively supported" in the scorecard rather than having it built for them.

**Why this priority**: Code execution is a common agent capability, but it carries safety risk and infrastructure cost, so it is limited to cheap cases.

**Independent Test**: For a supporting framework, open a PR with a failing test and confirm the review reports the failure from an isolated run that had no access to secrets.

**Acceptance Scenarios**:

1. **Given** a PR with a failing test and a supporting framework, **When** the review runs, **Then** the failure is reported with output from the isolated run.
2. **Given** PR code that attempts to read secrets or reach internal systems, **When** it runs in the sandbox, **Then** it cannot.
3. **Given** a run that exceeds the time or resource limit, **When** it is stopped, **Then** the review notes the run was cut off.
4. **Given** a framework without trivial support, **When** the report is produced, **Then** it states this rather than showing a workaround.

---

### User Story 14 - Cross-framework specialists over an agent-to-agent protocol (Priority: P3)

The multi-agent review can be run in a mixed mode in which the coordinator from one implementation delegates to specialists hosted by other implementations (built in different frameworks) through an open agent-to-agent protocol. The evaluator can see the same delegation trace as in User Story 4, now spanning framework boundaries.

**Why this priority**: It shows whether the frameworks interoperate, not just how each works alone. It is one optional scenario so the core loop stays independent of it.

**Independent Test**: Configure one implementation's coordinator to use a specialist hosted by a different implementation; open a PR and verify the consolidated review includes that specialist's finding and the trace names both frameworks.

**Acceptance Scenarios**:

1. **Given** a coordinator configured with a remote specialist from another framework, **When** a PR is reviewed, **Then** the consolidated review includes the remote specialist's finding attributed to it.
2. **Given** a remote specialist is unreachable or unauthorized, **When** the review runs, **Then** the coordinator delivers a labeled partial result as in User Story 4.
3. **Given** a completed mixed review, **When** the evaluator views the trace, **Then** each cross-framework delegation and response is visible with the framework of each agent.
4. **Given** every implementation, **When** it is asked to serve as a remote specialist, **Then** it advertises its capabilities and accepts authenticated delegations only from configured peers.

---

### User Story 15 - Long-context handling and memory across runs (Priority: P3)

The agent copes with material too large to fit in one pass (a huge diff, a long PR conversation, a long-running comment thread) by condensing or splitting it while preserving what matters. It also remembers durable facts across separate runs, such as repository conventions, a reviewer's stated preferences, and past decisions on similar PRs, and uses them in later summaries and reviews. The evaluator can inspect and correct what the agent has remembered.

**Why this priority**: Context limits and memory are where frameworks differ most in built-in support, and both directly affect quality on real repositories. It builds on Stories 1, 7, and 10.

**Independent Test**: Run a PR with a diff larger than a single pass can hold and verify the summary covers its major parts. Then state a convention in one PR thread, open a later, unrelated PR that touches it, and verify the review applies the convention.

**Acceptance Scenarios**:

1. **Given** a PR whose diff exceeds what fits in one pass, **When** it is summarized, **Then** the summary covers every major changed area and states what was condensed.
2. **Given** a long-running comment thread, **When** the agent answers a follow-up, **Then** it uses the relevant earlier context even though the full thread is not held verbatim.
3. **Given** a convention stated in an earlier run, **When** a later run on a different PR touches it, **Then** the agent applies it and identifies where it learned it.
4. **Given** a remembered fact that is wrong or outdated, **When** the evaluator corrects or deletes it, **Then** later runs no longer use it.
5. **Given** remembered content from PRs, **When** stored, **Then** it contains no detected secrets and is treated as untrusted data when reused (FR-014).

---

### Edge Cases

- Two remembered facts contradict each other (newer vs. older, or one PR's convention vs. another's).
- The memory grows without bound over many runs.
- A condensed summary of the diff drops the one changed line that matters.
- Hostile PR content attempts to plant a false or malicious "convention" in memory.
- A PR is opened as a draft, converted to ready for review, or opened by a bot: does the agent summarize it? (Default: drafts and bot-authored PRs are summarized; bots are labeled as such.)
- A PR touches only binary or generated files, so no meaningful text diff exists.
- A PR is opened, then closed within seconds, before processing completes.
- The GitHub notification arrives while a previous run for the same PR is still in progress.
- The watched repository is private and the agent lacks access to some content.
- The daily workflow runs while the model provider is degraded.
- Two implementations accidentally point at the same repository and tool server (duplicate records must be distinguishable by implementation).
- The tool server changes its advertised capabilities between runs (e.g. a renamed tool).
- The evaluator's cloud credentials lack a permission needed during provisioning (failure must be clear, not partial and silent).
- Summary text contains content that should not be forwarded (secrets present in a diff).
- Retrieved repository content itself contains injected instructions (it is untrusted, like the PR).
- An external MCP client requests a PR from a repository outside the watched allowlist.
- A dynamically loaded tool is unavailable or its advertised schema differs from what was expected.
- Code run in the sandbox produces enormous output or never terminates.
- Two implementations are configured as each other's remote specialist, causing a delegation loop.
- A remote specialist speaks a different protocol version than the coordinator expects.
- A model or capability the agents need is not enabled or not available on Bedrock in the configured region (must fail clearly at provisioning or health check, not mid-run).
- Bedrock throttling or quota limits differ across the four implementations running at once (retried per FR-012; recorded as a finding if it affects results).

## Requirements *(mandatory)*

### Functional Requirements

**Core behavior**

- **FR-001**: Each of the four implementations MUST accept GitHub pull-request notifications over a publicly reachable address and act when a PR is opened.
- **FR-002**: On PR open, each implementation MUST read the PR's title, description, changed files, and diff, and produce a plain-language summary of what the PR accomplishes.
- **FR-003**: Each implementation MUST deliver that summary to the tool server by invoking one of the tool server's advertised tools via the standard tool-server protocol, discovering the tool rather than hard-coding its schema where the protocol allows.
- **FR-004**: The system MUST include a reference tool server that records received summaries and digests, exposes them for inspection, and identifies which implementation submitted each record.
- **FR-005**: Each implementation MUST run a scheduled workflow every morning that publishes one digest covering exactly the PRs created the previous calendar day, evaluated in a single documented timezone.
- **FR-006**: The digest MUST include for each PR: title, author, current status, link, and short summary, and MUST be published to the destination defined in the Assumptions section.
- **FR-007**: Each implementation MUST provide a multi-agent workflow with at least a coordinator and three specialist agents whose delegations, responses, and disagreements are visible in a trace.
- **FR-008**: The multi-agent workflow MUST tolerate the failure of any one specialist and deliver a partial, clearly labeled result.

**Reliability and safety**

- **FR-009**: The system MUST verify the authenticity of every incoming notification and reject unauthenticated ones without processing.
- **FR-010**: The system MUST process each distinct notification at most once, even when it is delivered multiple times, and MUST NOT create duplicate summaries or digests.
- **FR-011**: The system MUST respond to GitHub promptly and perform the actual agent work asynchronously, so slow model calls cannot cause delivery timeouts.
- **FR-012**: The system MUST retry transient failures (model provider, tool server, GitHub) with backoff, and MUST record terminal failures visibly.
- **FR-013**: In-flight runs MUST survive process restarts by resuming or safely retrying.
- **FR-014**: Content from PRs MUST be treated as untrusted data; the agents MUST NOT follow instructions embedded in it, and MUST NOT include detected secrets in any output.
- **FR-015**: Consequential side effects beyond recording summaries (posting a PR comment) MUST require explicit human approval and MUST default to not happening on rejection or timeout.
- **FR-016**: Each run MUST be subject to configurable step, time, and spend limits.

**Interaction**

- **FR-017**: A permitted user MUST be able to command the agent from a PR comment, receive incremental progress output, and ask follow-ups that use conversation context. Commands from non-permitted users MUST be ignored.

**Observability and evaluation**

- **FR-018**: Every run MUST produce a record of steps, model calls, tool calls, timing, token usage, estimated cost, and outcome, viewable by the evaluator.
- **FR-019**: A shared evaluation set of sample PRs with expected properties MUST exist and MUST be runnable against every implementation, producing a report in an identical format that includes tool-server delivery correctness.
- **FR-020**: Errors and failed runs MUST generate an alert to the evaluator.
- **FR-021**: The system MUST emit structured logs that never contain secrets.

**Shared contract and comparability**

- **FR-022**: All implementations MUST satisfy the same behavioral contract (inputs, outputs, tool-server records, digest format), verified by one shared conformance test suite that runs against each.
- **FR-023**: All implementations MUST use the same model family for reasoning where the framework allows, so that differences observed are attributable to the framework rather than the model. Every model call (agents, evaluation judge, helper models) MUST go through Amazon Bedrock, matching Taskrabbit's environment; the Anthropic API MUST NOT be used as a fallback. A capability unavailable on Bedrock MUST be recorded in the report as "not supported on Bedrock" (FR-024) rather than worked around.
- **FR-024**: Framework-specific limitations MUST be recorded rather than worked around silently; each workaround is noted in the report.

**Deployment**

- **FR-025**: All cloud infrastructure MUST be defined in version-controlled OpenTofu code targeting AWS, with a reviewable plan before apply, and MUST NOT be created via manual console changes.
- **FR-026**: The evaluator MUST be able to deploy and tear down each implementation independently, and the environment MUST support all four running at once.
- **FR-027**: Secrets (cloud credentials, GitHub webhook secret) MUST be stored encrypted and MUST NOT be committed in plaintext.
- **FR-028**: Every implementation MUST have a health check and a documented clean-state quickstart that runs top to bottom from a fresh checkout.

**Extended capabilities**

- **FR-030**: Each implementation MUST be able to search the watched repository's files and history during a run, use the results in its summary or review, and list the sources it consulted.
- **FR-031**: Retrieved repository content MUST be treated as untrusted data under FR-014, and retrieval MUST honor the run's step and spend limits (FR-016).
- **FR-032**: Each implementation MUST expose an MCP server interface advertising at least a "summarize PR" tool and a "get latest digest" tool.
- **FR-033**: The agent's MCP interface MUST require authentication, MUST restrict requests to the watched repository allowlist, and MUST return explicit errors rather than fabricated results.
- **FR-034**: Each implementation MUST start a run with a minimal tool set and load additional tools on demand, recording each load in the run record.
- **FR-035**: Each tool MUST carry a permission policy (allowed, requires approval, denied); denied calls MUST be refused and recorded, and requires-approval calls MUST follow FR-015.
- **FR-036**: Where a framework supports sandboxed code execution with trivial effort, the implementation SHOULD run the PR's tests in an isolated environment with no access to secrets or internal systems, bounded by time and resource limits, and include the results in the review.
- **FR-037**: Where a framework does not support sandboxed execution trivially, the report MUST record it as not natively supported; no custom sandbox is built for it.
- **FR-038**: Each implementation MUST be able to act as a remote specialist and as a coordinator's client over an open agent-to-agent protocol, so any implementation's coordinator can delegate to any other implementation's specialist.
- **FR-039**: Cross-framework delegation MUST require authentication between peers, MUST be limited to configured peers, and MUST appear in the delegation trace with the framework of each participant.
- **FR-040**: A failed or unreachable remote specialist MUST degrade to a labeled partial result per FR-008, and the core multi-agent workflow (FR-007) MUST NOT depend on cross-framework calls.
- **FR-041**: When input exceeds what one pass can hold, each implementation MUST condense or split it so every major changed area is covered, and MUST state in the output what was condensed or omitted.
- **FR-042**: Each implementation MUST retain conversation context across a long thread without holding it verbatim, so follow-ups can use relevant earlier content.
- **FR-043**: Each implementation MUST persist durable facts (repository conventions, stated preferences, prior decisions) across runs, apply them in later runs, and cite where each was learned.
- **FR-044**: The evaluator MUST be able to list, correct, and delete remembered facts, and deletions MUST take effect in the next run.
- **FR-045**: Remembered content MUST exclude detected secrets, MUST be treated as untrusted data when reused (FR-014), and MUST be bounded in size, with a stated rule for what is discarded.

**Deliverables**

- **FR-029**: A comprehensive comparison report MUST be produced comparing and contrasting all four frameworks on developer effort, scenario fit, deployment complexity, cost, latency, evaluation results, and friction notes, with a side-by-side scorecard and narrative analysis per framework.
- **FR-046**: The report MUST evaluate each framework's suitability as Taskrabbit's multi-agent library of choice against one explicit, shared set of criteria stated in the report, and MUST end in a reasoned recommendation, including the conditions under which it would change.
- **FR-047**: Report claims MUST link to supporting source code, run records, or evaluation results, using links pinned to a fixed revision so they remain valid as the code evolves.
- **FR-048**: The report MUST distinguish measured results from the evaluator's judgment, and MUST state known limits of the evaluation (test repository scale, single model family, sample size).
- **FR-049**: The report MUST assess each framework's own evaluation capabilities, covering at least: defining test datasets, automated and model-graded scoring, evaluating tool-call and multi-agent behavior, evaluating from recorded traces, running and comparing experiments across versions, using evaluation in CI, and integrating with external evaluation platforms. Each capability MUST be marked native, via integration, manual, or not available, with a link to the code showing how it was used or to the evidence that it is not available.
- **FR-050**: The shared evaluation set and reports (FR-019) MUST run on every framework, and the report MUST separate what each framework's native evaluation tooling provided from what the shared harness supplied, so that the harness does not mask differences in native capability.
- **FR-057**: The report MUST include a prominent section highlighting every issue that using Amazon Bedrock caused (for example server-side tools, structured outputs, MCP connector, model access and inference-profile constraints, API-shape differences between frameworks, throttling), collected in a running log during the work, each entry citing its source or evidence and marked as documented or observed, so that Taskrabbit sees the cost of the Bedrock constraint per framework.

**Operations**

- **FR-051**: The evaluator MUST be able to bring up, and take down, the whole environment or any subset of implementations with one documented command each and no manual steps in between.
- **FR-052**: The system MUST support a pause state, distinct from full teardown, in which implementation compute stops and stops accruing charges while data, configuration, images, and secrets are preserved, and a resume that restores service without rebuilding or redeploying images. The data store SHOULD stop charging for compute while idle.
- **FR-053**: Bringing the environment up after a teardown MUST restore the previous data (memory facts, records, run history) by default, MUST offer an explicit fresh-start choice, and MUST automatically re-register the GitHub notification address, since it may change.
- **FR-054**: A status command MUST report, per component, whether it is running, paused, or absent, its uptime, and an estimated daily cost.
- **FR-055**: The system SHOULD guard against forgotten environments with a spend alarm and an optional maximum uptime after which implementations are paused automatically.
- **FR-056**: The persistent layer that survives teardown (state, images, secrets, report artifacts, the database, the public entry address) MUST be explicitly documented and separately destroyable, so that a full destroy leaves no billable resources.

### Key Entities

- **Watched Repository**: The GitHub repository whose PRs the agent monitors; has a webhook secret and access token.
- **Pull Request Event**: One delivery from GitHub, with a unique delivery identifier, PR identifier, action type, and timestamp; the unit of deduplication.
- **PR Summary**: The agent's plain-language account of a PR's purpose, tied to a PR state, producing implementation, and timestamp.
- **Review Finding**: A specialist's structured observation (topic, severity, evidence, author agent) that the coordinator merges into a consolidated review.
- **Consolidated Review**: The coordinator's combined output: findings, surfaced disagreements, and a note of any missing perspectives.
- **Daily Digest**: The summary of one calendar day's PRs; keyed by date and implementation so it publishes once.
- **Agent Run**: A single execution with steps, model calls, tool calls, cost, status, and (for multi-agent) the delegation trace.
- **Approval Request**: A pending proposed side effect with decision (approved, rejected, expired) and decider.
- **Evaluation Sample / Evaluation Report**: A fixed PR fixture with expected properties, and the per-implementation scored results.
- **Comparison Report**: The written comparison of the four frameworks, containing the scorecard, per-framework analysis, Taskrabbit suitability criteria and assessment, recommendation, and pinned links to evidence.
- **Framework Scorecard**: The comparison matrix of frameworks against dimensions, part of the report.
- **Suitability Criterion**: One stated dimension of Taskrabbit's needs, applied identically to every framework.
- **Tool Server Record**: A stored summary, review, or digest, labeled with the submitting implementation.
- **Context Source**: A repository file or prior PR consulted during a run, recorded with the run and cited in the output.
- **Tool Grant**: A tool's permission policy (allowed, requires approval, denied) and whether it is loaded initially or on demand.
- **Sandbox Run**: An isolated execution of PR code, with its limits, output, and outcome.
- **Memory Fact**: A durable remembered statement (a convention, preference, or decision) with its source PR or thread, date, and status (active, corrected, deleted).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For at least 95% of PRs in the evaluation set, each implementation delivers a correct summary record to the tool server within 2 minutes of the PR being opened.
- **SC-002**: A forged notification is rejected in 100% of trials, and a redelivered notification produces zero duplicate records across 20 trials.
- **SC-003**: The morning digest for a seeded day lists 100% of that day's PRs and 0 PRs from other days, in all four implementations.
- **SC-004**: An evaluator with valid credentials can go from a fresh checkout to one working deployed implementation in under 30 minutes by following the quickstart, and can fully tear it down in under 10 minutes with no resources left behind.
- **SC-005**: In the multi-agent scenario, the trace shows every delegation and response for 100% of runs, and a review completes with a labeled partial result in 100% of trials where one specialist is forced to fail.
- **SC-006**: Injection-attempt PRs in the evaluation set cause zero out-of-policy actions or leaked secrets across all implementations.
- **SC-007**: With approval required, zero side-effecting comments are posted without an approval in 100% of trials.
- **SC-008**: All four implementations pass the shared conformance suite, and the evaluation report format is identical across them.
- **SC-009**: The evaluator can look up the cost and duration of any single run in under 1 minute.
- **SC-010**: The finished report has every framework/dimension cell filled, applies the same suitability criteria to all four frameworks, and ends with a clear recommendation for Taskrabbit's multi-agent library.
- **SC-011**: On evaluation PRs whose purpose depends on code outside the diff, summaries cite the relevant source in at least 90% of cases and never cite a source that was not consulted.
- **SC-012**: A generic MCP client can connect to each implementation, discover its tools, and receive a correct summary for a valid PR within 2 minutes; unauthenticated connections are refused in 100% of trials.
- **SC-013**: In 100% of trials, calls to a denied tool are refused and recorded, and tools outside the task's needs are not loaded.
- **SC-014**: For every framework where sandboxed execution is supported, sandboxed code cannot reach secrets in 100% of trials; for every other framework, the report says not natively supported.
- **SC-015**: For each of the 12 ordered pairs of frameworks (coordinator, remote specialist), a mixed review completes with the remote finding attributed and the trace showing both frameworks; an unreachable remote specialist yields a labeled partial result in 100% of trials.
- **SC-016**: For oversized evaluation PRs, summaries cover at least 90% of the major changed areas and always disclose what was condensed.
- **SC-017**: In a two-run memory test, the second run applies the convention learned in the first in at least 90% of trials and cites its source, and a deleted fact is never used again.
- **SC-018**: Injected false "conventions" planted through PR content are stored or applied in 0 trials.
- **SC-019**: In a spot check of 10 randomly chosen report claims, at least 9 link to the specific code, run record, or result that supports them, and 100% of links resolve.
- **SC-020**: A decision-maker who was not involved can read the report and state the recommendation and its main tradeoffs in under 30 minutes.
- **SC-021**: The report's evaluation-capabilities section covers all seven listed capabilities for all four frameworks, with no cell empty and each marked native, via integration, manual, or not available.
- **SC-022**: From a taken-down state, one command returns the environment to healthy, with data restored and webhooks re-registered, in under 20 minutes; pause and resume each complete in under 5 minutes.
- **SC-023**: While paused, the status command's estimated cost is under 25% of the running cost, and a full destroy followed by the clean-check leaves zero billable resources.
- **SC-024**: The report's Bedrock section covers all four frameworks, each issue has a cited source or evidence link and a documented-or-observed marker, and every issue logged during the work appears in it.

## Assumptions

- **Frameworks**: "Pydantic API" in the request is taken to mean Pydantic AI. The four frameworks are LangGraph, Claude Agent SDK, Mastra, and Pydantic AI.
- **Model**: All implementations use the same Claude model family, since Claude Agent SDK is tied to it; this keeps the comparison fair. Models are accessed through Amazon Bedrock in the evaluator's AWS account, because Bedrock is what Taskrabbit uses, authenticated with the deployed workload's cloud identity rather than a model API key. The evaluator's account must have access to the chosen models in the chosen region. Each framework's Bedrock support is confirmed by a spike before implementation; the Bedrock decision is revisited if any framework lacks it.
- **"MCP evaluation"**: Interpreted as evaluating how each framework discovers and calls tools on an MCP server, and how correctly and reliably it does so, rather than evaluating a third-party MCP product.
- **MCP server**: There is no existing MCP server to target, so this project builds a small reference MCP server (record summaries, digests, and reviews; expose them for inspection), hosted alongside the agents.
- **Repository scope**: Agents watch an evaluator-designated test repository (or short allowlist), not every repository the evaluator owns. Use of production repositories is out of scope.
- **Multi-agent design**: The demonstration workflow is a coordinator plus three specialists (summarizer, risk/security reviewer, test-coverage reviewer). The exact roles may be adjusted at planning time without changing the scenarios.
- **"Created the previous day"**: Uses the evaluator's local timezone, fixed in configuration; the morning schedule is approximately 08:00 in that timezone.
- **Empty days**: A digest stating "no PRs" is still published, so silence always means failure.
- **Approval channel**: The human-approval decision can be made through any simple mechanism the evaluator can use (e.g., a reaction or reply on the PR); the exact mechanism is a planning decision.
- **Authorized users**: Only the repository owner may command the agent in v1.
- **Credentials**: The evaluator supplies cloud credentials and a GitHub token, plus Bedrock model access enabled in the AWS account; the project never creates them. No Anthropic API key is needed.
- **Cost control**: Cost is managed by pausing or taking the environment down between sessions; leaving it running is the expensive case. Exact figures are estimates until measured.
- **Cost**: The exercise is small-scale; the environment is sized for low traffic, and the evaluator accepts modest ongoing cost while it is deployed.
- **Conventions**: The project follows the constitution in `.specify/memory/constitution.md`, adopted from the glitch repository as a starting point. Parts of it are specific to that repository and will need adapting.
- **Deferred capabilities**: Model portability/fallback and deterministic record/replay testing are candidates for a later round, not this one.
- **Taskrabbit suitability criteria**: Taskrabbit's requirements are not yet written down. The report's criteria will be proposed at planning time and confirmed with the evaluator. Likely candidates: language and stack fit, ability to run multiple cooperating agents reliably, security and guardrails, observability, operational and deployment burden, cost, maintenance and vendor risk, community maturity, and team learning curve.
- **Evaluation capabilities**: "Evaluation" in the report covers both how good each framework's agents are (measured with the shared set, User Story 8) and how well each framework helps a team evaluate agents in general. Third-party evaluation platforms are in scope only to the extent a framework integrates with them.
- **Audience**: The report's readers are Taskrabbit engineering decision-makers; it may reference Taskrabbit's needs but contains no confidential Taskrabbit data.
- **Out of scope**: Multi-tenant use, a user interface beyond GitHub and the tool-server inspection view, other event sources (Slack, email), and production-grade high availability.
- **Digest destination**: The daily digest is published as a GitHub issue in the watched repository, one per day per implementation (titled with the date and implementation name so reruns can find and reuse it). It is also recorded on the reference tool server.
