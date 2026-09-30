---

description: "Task list for spec 004: Evaluation and Comparison Report"
---

# Tasks: Evaluation and Comparison Report

**Input**: Design documents from `/specs/004-evaluation-report/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md, `.specify/memory/constitution.md` (v1.0.0), and the completed specs 001-core-pr-steward, 002-multi-agent-safety, and 003-extended-capabilities.

**Tests**: Included. The constitution requires tests (Principle I) and a conformance suite that runs in CI (Principle IX); the spec makes the evaluation suite a deliverable (FR-019).

**Organization**: Phase 0 reconciles with the completed predecessors. Then tasks are grouped by user story (US8, US9), followed by Polish and whole-environment verification. Task IDs T142-T419 are the original IDs, kept for traceability (edited only where scope moved); T400-T499 are new IDs reserved for this spec. Phase numbers restart per spec.

## Format: `- [ ] T### [P?] [US#?] Description with file path`

- **[P]**: can run in parallel with the other [P] tasks in the same step (different files, no dependency on an incomplete task). Where a step lists four tasks (one per implementation), the four are [P] with each other; steps within a phase run in the order listed.
- **[US#]**: user story from spec.md. Phase 0, Setup, Foundational, and Polish tasks have no story label.
- **⚠ needs owner approval**: task creates or destroys AWS resources, writes to GitHub with the owner's token, or spends money on live model calls. Stop and get explicit approval (with `tofu plan` output shown for infrastructure) before doing it. Everything else is local and safe.
- References written "spec 001 T034" point at a task in a predecessor spec's `tasks.md`.

## Path Conventions

Per spec 001 plan.md and this spec's plan.md: `implementations/<name>/` (Python: `src/steward/`, TypeScript for Mastra: `src/`; native evals in `evals/`), `shared/conformance/`, `infra/modules/implementation/`, `docs/report/`, `scripts/`, `specs/004-evaluation-report/spikes/`.

## Constraints that apply to every task

- **No shared agent logic across frameworks** (constitution, Code Quality Gates): the judge and harness are shared evaluation code; each framework's native evals and observability are written in its own idiom.
- **Framework facts come from current docs**, not memory (research.md marks UNVERIFIED items as spikes). Record surprises in the component's `CLAUDE.md`.
- **Definition of done for any implementation task**: tests written and passing, `ruff check` (Python) or `tsc --noEmit` (TypeScript) clean, and the exact commands and output recorded. Reports of "validated" without commands are not accepted (Constitution VIII).
- **Model access uses each framework's maintained Bedrock client** and the judge uses boto3 through Bedrock, never a hand-rolled `invoke_model` wrapper for agents (Constitution VII). A capability Bedrock lacks is recorded as "not supported on Bedrock" (FR-023, FR-024) and appended to the Bedrock issues log (spec 001 research.md section 6), not worked around and not routed to the Anthropic API.
- **Secrets**: credentials come from the environment or an AWS profile only and are never written to any file in the repository (Constitution V), including report chapters and `live-engagement.md`.
- **Independent verification**: a second actor (CI or a fresh worktree/session) reproduces each finished component's tests (Constitution I).

---

## Phase 0: Reconcile with the completed predecessors

**Purpose**: Specs 001-003 were written before code existed. Confirm what was actually built and bring this spec in line before writing anything that depends on it. No later phase starts until every task here is done.

- [ ] T400 Confirm the predecessors are finished: each checkpoint and Polish verification task of specs 001, 002, and 003 (for example spec 001 T056 and T072 and the Polish tasks of each `tasks.md`) is checked, CI is green on the branch, and each predecessor's as-built deviations are recorded (its `reconciliation.md`, spec, plan, or `CLAUDE.md` notes). List anything unchecked or unrecorded in `specs/004-evaluation-report/reconciliation.md` under Open questions and stop for the owner if a predecessor checkpoint is not met
- [ ] T401 Inventory what was delivered per framework and per story (US1-US7, US10-US15) from the predecessors' checkpoints and `CLAUDE.md` files: which stories work, capability status (native, via integration, manual, not available, not built), sandbox and A2A results, and the final fixture set (ids, tags, `expected.yaml` keys) and registered `just scenario` names; write the inventory table into `reconciliation.md` (Verified) so the report chapters and scorecard can state unbuilt scope explicitly (spec User Story 9 scenario 2)
- [ ] T402 Diff the as-built code, contracts, and schema against this spec's "Depends on / Inherited from predecessors" list and record every finding in `reconciliation.md` (Verified, Deviations found): `agent_runs` and `run_steps` columns, `/admin/runs` response fields, `toolserver.records` and `toolserver.calls`, tool-server tool names, metric and alarm names, `just` target names including `eval`/`eval-all`, `cli.py` location and commands (spec 001 T028), `report.py` schema validation (spec 001 T025), stub scenario ids in `stub_bedrock.py`, the per-kind dedupe key from spec 002 that keeps `pr_summary` and `pr_review` work items distinct during an evaluation run, and where the migrate task, `destroy-all` (including ECR `force_delete` and artifacts bucket `force_destroy`) and `verify-clean` ended up
- [ ] T403 Update this spec's `spec.md`, `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `tasks.md`, and `contracts/` to match reality; list each change under "Spec/plan/tasks/contract changes made" in `reconciliation.md`; anything that requires a change to a predecessor's code or contract goes under Open questions for the owner and is not edited silently (no edits outside this spec dir)
- [ ] T404 Run `/speckit-analyze` on this spec dir (spec.md, plan.md, tasks.md) after T403, resolve or document every finding in `reconciliation.md`, and re-run until it reports no CRITICAL or HIGH findings
- [ ] T405 Gate: confirm the environment prerequisites for the live tasks are available to the owner (Bedrock access to Opus 5.5 for the judge and the quota values recorded by spec 001 T013, `WATCHED_REPO`, `OWNER_LOGIN`, credentials by environment or profile) and record the result in `reconciliation.md`; mark Phase 0 complete there

**Checkpoint**: `reconciliation.md` has all four headings filled, T404 is clean, and the owner has seen the Open questions.

## Phase 1: Setup

**Purpose**: Only what this spec needs beyond the skeleton spec 001 created.

- [ ] T406 [P] Confirm the directories this spec writes to exist (`docs/report/`, `scripts/`, `shared/conformance/reports/<impl>/` for the four implementations, `implementations/<name>/evals/`, `specs/004-evaluation-report/spikes/`), creating any missing one with a `.gitkeep`
- [ ] T407 [P] Confirm the evaluation dependencies are pinned in each component (`openevals` and `agentevals` for LangGraph, `pydantic-evals` and `logfire` for Pydantic AI, `@mastra/evals` for Mastra, `jsonschema` in `shared/conformance`), add any that are missing, refresh lockfiles (`uv lock`, `npm install --package-lock-only`), and make each component CI workflow run its `evals/` tests that need no live model (stub Bedrock) on a clean runner (Constitution IX)

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Things User Stories 8 and 9 both need. No story starts until this phase is complete.

- [ ] T408 Wire report validation: create `shared/conformance/src/conformance/report.py` (spec 001 T025 builds the rest of the harness core but leaves the report writer to this spec) so it writes and validates reports against `specs/004-evaluation-report/contracts/eval-report.schema.json` (load it from that path, or keep a copy under `shared/conformance/schemas/` with a test that fails when the two differ); add `just report-check` to `justfile` if spec 001 did not, validating every JSON under `shared/conformance/reports/`; test with one valid and one invalid sample report in `shared/conformance/tests/test_report_schema.py`
- [ ] T409 Spike S3 and the observability parts of S4, S5, S6 (LangGraph, Mastra, Claude Agent SDK, Pydantic AI): using the local stack, verify per framework whether OTel spans can be exported to an OTLP collector without any hosted vendor, how token and cost figures can be read, and how the framework's own usage figures compare with `agent_runs` totals (research section 3); write findings to `specs/004-evaluation-report/spikes/S3-otel.md` (with one section per framework), append any Bedrock-caused issue to spec 001 research.md section 6, and state per framework the OTel path T148-T151 will implement

## Phase 3: User Story 8 - Observability, cost tracking, and quality evaluation (Priority: P3)

**Purpose**: Goal: every run is inspectable (steps, tokens, cost, errors) and a shared evaluation set plus each framework's native evals yield comparable results. Independent test: run the evaluation set against one implementation and obtain a schema-valid report with per-fixture quality, latency, and cost; re-run and confirm comparability.

- [ ] T142 [US8] Implement the LLM-judge scorer in `shared/conformance/src/conformance/judge.py` (judge model Claude Opus 5.5 via its pinned Bedrock inference profile, fixed rubric from each fixture's `expected.yaml`, scores `accuracy`, `coverage`, `source_citation`, `injection_safe`, `secret_leak`) and the eval runner in `shared/conformance/src/conformance/evalrun.py` producing reports validated against `specs/004-evaluation-report/contracts/eval-report.schema.json` (`fixtures`, `summary`, `native_evals` kept separate per FR-050)
- [ ] T143 [P] [US8] Write `shared/conformance/tests/test_us8_reports.py` (contract tier; the judge runs against a `judge` scenario in `shared/conformance/stubs/stub_bedrock.py`, added if spec 001's stub lacks one): report validates against the schema, includes tool-server delivery correctness, per-run cost and duration are retrievable via `/admin/runs` in under 1 minute, a run exceeding its spend/step limit (spec 001 FR-016) stops and records `limit_reason`
- [ ] T144 [P] [US8] Implement the native evaluation suite for LangGraph in `implementations/langgraph/evals/` using `openevals` and `agentevals` (trajectory match and LLM-judge trajectory evaluators) run under `pytest`; note which parts need LangSmith (datasets/experiments) and mark capability status accordingly; write results to `shared/conformance/reports/langgraph/native-<timestamp>.json` and fill `native_evals.capabilities` for all seven FR-049 capabilities (datasets, automated and model-graded scoring, tool-call and multi-agent eval, trace-based eval, experiment comparison, CI usage, external platform integration) with status native|via_integration|manual|not_available and an evidence path
- [ ] T145 [P] [US8] Implement the native evaluation suite for Claude Agent SDK in `implementations/claude-agent-sdk/evals/` using a manual eval harness (no native evals exist; use the SDK's `ResultMessage` cost/usage and the shared judge), recording every FR-049 capability as manual or not_available with evidence; write results to `shared/conformance/reports/claude-agent-sdk/native-<timestamp>.json` and fill `native_evals.capabilities` for all seven FR-049 capabilities (datasets, automated and model-graded scoring, tool-call and multi-agent eval, trace-based eval, experiment comparison, CI usage, external platform integration) with status native|via_integration|manual|not_available and an evidence path
- [ ] T146 [P] [US8] Implement the native evaluation suite for Pydantic AI in `implementations/pydantic-ai/evals/` using `pydantic-evals` (Dataset, Case, LLM judge, span-based evaluators with local `logfire` capture, no Logfire account) run under `pytest`; write results to `shared/conformance/reports/pydantic-ai/native-<timestamp>.json` and fill `native_evals.capabilities` for all seven FR-049 capabilities (datasets, automated and model-graded scoring, tool-call and multi-agent eval, trace-based eval, experiment comparison, CI usage, external platform integration) with status native|via_integration|manual|not_available and an evidence path
- [ ] T147 [P] [US8] Implement the native evaluation suite for Mastra in `implementations/mastra/evals/` using Mastra built-in and custom scorers (tool-call-accuracy, completeness, custom scorers) via `runEvals` under Vitest, with datasets/experiments on `@mastra/pg`; write results to `shared/conformance/reports/mastra/native-<timestamp>.json` and fill `native_evals.capabilities` for all seven FR-049 capabilities (datasets, automated and model-graded scoring, tool-call and multi-agent eval, trace-based eval, experiment comparison, CI usage, external platform integration) with status native|via_integration|manual|not_available and an evidence path
- [ ] T148 [P] [US8] Implement observability for LangGraph in `implementations/langgraph/src/steward/observability.py`: best-effort OTel export (structured logs and EMF metrics already landed in spec 001 T044) to an ADOT collector sidecar, and token/cost accounting written to `agent_runs` (spike T409, covering S3, decides the OTel path); document the OTel path in `implementations/langgraph/CLAUDE.md` (Constitution VI)
- [ ] T149 [P] [US8] Implement observability for Claude Agent SDK in `implementations/claude-agent-sdk/src/steward/observability.py`: best-effort OTel export (structured logs and EMF metrics already landed in spec 001 T045) to an ADOT collector sidecar, and token/cost accounting written to `agent_runs` (spike T409, covering S5's observability part, decides the OTel path); document the OTel path in `implementations/claude-agent-sdk/CLAUDE.md` (Constitution VI)
- [ ] T150 [P] [US8] Implement observability for Pydantic AI in `implementations/pydantic-ai/src/steward/observability.py`: best-effort OTel export (structured logs and EMF metrics already landed in spec 001 T046) to an ADOT collector sidecar, and token/cost accounting written to `agent_runs` (spike T409, covering S6's observability part, decides the OTel path); document the OTel path in `implementations/pydantic-ai/CLAUDE.md` (Constitution VI)
- [ ] T151 [P] [US8] Implement observability for Mastra in `implementations/mastra/src/observability.ts`: best-effort OTel export (structured logs and EMF metrics already landed in spec 001 T047) to an ADOT collector sidecar, and token/cost accounting written to `agent_runs` (spike T409, covering S4's observability part, decides the OTel path); document the OTel path in `implementations/mastra/CLAUDE.md` (Constitution VI)
- [ ] T152 [US8] Add the ADOT collector sidecar and metric filters to `infra/modules/implementation/` and confirm the alarms (5xx, failed runs, DLQ depth, missed digest; alarm definitions from spec 001 T061) fire in a deliberate-failure test (⚠ needs owner approval: AWS)
- [ ] T153 [US8] Extend the eval CLI in `shared/conformance/src/conformance/cli.py` (created by spec 001 T028) so `just eval <impl>` runs the shared harness plus that implementation's native eval, writing `shared/conformance/reports/<impl>/<timestamp>.json`, and `just eval-all` covers every deployed implementation and reports absent ones, plus `just report-check` validating every report against `contracts/eval-report.schema.json`; live runs need owner approval for model spend (⚠)
- [ ] T154 [US8] Run the full live evaluation against each deployed implementation and commit the resulting report JSON under `shared/conformance/reports/` with the git SHA recorded (⚠ needs owner approval: AWS, GitHub writes, and model spend)
- [ ] T410 [US8] Checkpoint: from a clean state run `just up-local` then `just conformance-local` including `test_us8_reports.py`, then `just report-check` on the reports from T154, and re-run one implementation's `just eval` to confirm results are comparable to the first run (differences explained by judge variance are noted, not hidden); record commands and observed pass counts (Constitution VIII)

## Phase 4: User Story 9 - Comprehensive framework comparison report (Priority: P3)

**Purpose**: Goal: a written report comparing the four frameworks and assessing suitability as Taskrabbit's multi-agent library, with links pinned to a fixed revision. Independent test: read the report as a decision-maker; every framework/dimension cell is filled, the recommendation follows from the evidence, and a sample of claims resolves to the code or results they cite.

- [ ] T155 [US9] Confirm the Taskrabbit suitability criteria with the owner (proposal in this spec's research.md D17: stack fit; multi-agent coordination reliability; security/guardrails; observability; evaluation tooling; operational and deployment burden; cost; maintenance/vendor/license risk; community maturity and API stability; team learning curve) and write the agreed list to `docs/report/criteria.md`
- [ ] T156 [US9] Create the report skeleton `docs/report/index.md` (summary, method, limits per FR-048: test-repo scale, single model family, sample size, measured vs judgment) and `docs/report/scorecard.md` (matrix of frameworks x dimensions from spec FR-029 with a legend for native / via integration / manual, and the "not built" and "not natively supported" markers from the T401 inventory)
- [ ] T157 [P] [US9] Write the LangGraph chapter `docs/report/langgraph.md`: strengths, weaknesses, friction and workarounds per scenario (US1-US15), effort (code volume, time to first working version), deployment complexity, cost and latency from the eval reports, evaluation capabilities (FR-049), license/maintenance risk; every claim linked to a pinned permalink into `implementations/langgraph/`, `infra/`, or `shared/conformance/reports/langgraph/`
- [ ] T158 [P] [US9] Write the Claude Agent SDK chapter `docs/report/claude-agent-sdk.md`: strengths, weaknesses, friction and workarounds per scenario (US1-US15), effort (code volume, time to first working version), deployment complexity, cost and latency from the eval reports, evaluation capabilities (FR-049), license/maintenance risk; every claim linked to a pinned permalink into `implementations/claude-agent-sdk/`, `infra/`, or `shared/conformance/reports/claude-agent-sdk/`
- [ ] T159 [P] [US9] Write the Pydantic AI chapter `docs/report/pydantic-ai.md`: strengths, weaknesses, friction and workarounds per scenario (US1-US15), effort (code volume, time to first working version), deployment complexity, cost and latency from the eval reports, evaluation capabilities (FR-049), license/maintenance risk; every claim linked to a pinned permalink into `implementations/pydantic-ai/`, `infra/`, or `shared/conformance/reports/pydantic-ai/`
- [ ] T160 [P] [US9] Write the Mastra chapter `docs/report/mastra.md`: strengths, weaknesses, friction and workarounds per scenario (US1-US15), effort (code volume, time to first working version), deployment complexity, cost and latency from the eval reports, evaluation capabilities (FR-049), license/maintenance risk; every claim linked to a pinned permalink into `implementations/mastra/`, `infra/`, or `shared/conformance/reports/mastra/`
- [ ] T161 [US9] Write `docs/report/mcp-evaluation.md`: how each framework discovers and calls MCP tools (client), serves them (server), and A2A, using `toolserver.calls` data from the eval runs, with correctness and reliability findings and links
- [ ] T162 [US9] Write `docs/report/bedrock-issues.md` (FR-057, SC-024): a prominent chapter built from the Bedrock issues log in spec 001 research.md section 6 (with the entries appended by specs 001-003 and this spec), updated with every issue observed during the work (spike, scenario, eval), each entry with source or evidence link and a documented/observed marker, per-framework impact, and what Taskrabbit should expect on Bedrock; link it from `docs/report/index.md` and the suitability section
- [ ] T163 [US9] Write `docs/report/evaluation-capabilities.md`: the seven FR-049 capabilities per framework (native/integration/manual with evidence links) and a section separating what native tooling provided from what the shared harness supplied (FR-050)
- [ ] T164 [US9] Write `docs/report/taskrabbit-suitability.md`: apply the agreed criteria identically to all four frameworks, state the recommendation, the conditions under which it would change, and the main tradeoffs a reader can absorb in under 30 minutes (SC-020)
- [ ] T165 [US9] Implement `scripts/report_links.py` and `just report-links`: extract every link in `docs/report/`, require repo links to be permalinks pinned to a commit SHA that exists (`https://github.com/yesawoo/agentic-framework-exploration/blob/<sha>/<path>#L<n>`), and verify that each path and line range resolves at that SHA; exits non-zero on any failure; add a contract-tier test in `shared/conformance/tests/test_report_links.py` using a temporary git repository fixture
- [ ] T166 [US9] Tag the evaluated revision (`report-eval-1`), rewrite links in `docs/report/` to that SHA, run `just report-links` and `just report-check`, and spot-check 10 random claims per SC-019 recording the results in `docs/report/verification.md`
- [ ] T411 [US9] Checkpoint: as someone deciding on a multi-agent library, read `docs/report/` and record in `docs/report/verification.md` that every framework/dimension cell is filled (SC-010), the seven capabilities for four frameworks are covered (SC-021), every Bedrock log entry appears in `bedrock-issues.md` (SC-024), each unbuilt or unsupported scenario is stated (spec User Story 9 scenario 2), and the recommendation follows from the evidence; a reader who did not write the report states the recommendation and main tradeoffs within 30 minutes (SC-020, ⚠ needs the owner or another reader)

## Phase 5: Polish, Cross-Cutting Concerns, and Whole-Environment Verification

**Purpose**: Final verification of the whole project from a clean state, documentation, and teardown (Constitution VIII, IX). This phase covers all four specs' components, since this spec is the last.

- [ ] T413 [P] Finalize every component `CLAUDE.md` (implementations, `shared/tool-server`, `shared/conformance`, each `infra/*` root, and the new `evals/` directories) with architecture, commands, constraints, and what is logged/emitted/alerted (Constitution III, VI); update root `CLAUDE.md`
- [ ] T414 [P] Update `README.md` at the repo root (written by spec 001 T168) (purpose, quickstart pointer, cost warning, teardown reminder) and a `docs/design/overview.md` that links to the four specs, their plans, and the report
- [ ] T415 Confirm every component workflow (`.github/workflows/*-ci.yml`, `conformance.yml`, `db-ci.yml`, `infra-ci.yml`) has at least one green run on the feature branch, including the conformance contract tier against every implementation on the branch (SC-008), and record the run URLs in the PR description
- [ ] T416 Independent clean-state verification (an actor other than the implementer, from a fresh clone/worktree): run spec 001 quickstart sections 1-2 and the local checks in the quickstarts of specs 002 and 003 and this spec's section B, and record commands and observed output, including pass counts per implementation
- [ ] T171 Live agent engagement (⚠ needs owner approval: deployed environment, GitHub writes, Bedrock spend): after `just up`, an interactive Claude Code session (not the scripted harness) drives each deployed implementation as a real user would and records what it observed in `docs/report/live-engagement.md`. For each of the four: (1) connect a generic MCP client (start the Claude Code session with `--mcp-config` pointing at a file under `$TMPDIR` that references the bearer only as `${ADMIN_TOKEN}`, exported in that shell from a value read from Secrets Manager at run time; verify env expansion works in that file; do not use `claude mcp add`, which persists the header in plaintext config; delete the file and unset the variable afterwards, Constitution V) to `/<impl>/mcp`, list tools, call `summarize_pr` on a real PR in `$WATCHED_REPO`, call `get_latest_digest`, and confirm an unauthenticated connection is refused (SC-012); (2) open a real PR and confirm the summary lands on the tool server (`GET /toolserver/records`); (3) comment `@steward` and `/approve <id>` as the owner and watch the streamed reply (`POST /<impl>/chat/stream` with `curl -N`); (4) read the run just produced from `/<impl>/admin/runs/{id}` (steps, tokens, cost) and CloudWatch logs; (5) try one injection PR and one forged webhook. Record commands, status codes, and any divergence from what the scripted scenarios reported; a disagreement is a bug in the harness or the agent and is fixed or logged Supports SC-001, SC-002, SC-006, SC-007, SC-012. `live-engagement.md` must redact all tokens. Append every Bedrock problem observed to the Bedrock issues log (spec 001 research.md section 6) and update `docs/report/bedrock-issues.md`, pin the links in `live-engagement.md`, and rerun `just report-links` and `just report-check` afterwards (this task runs after link pinning). The Claude Code session driving this is evaluator tooling, not an implementation model call under FR-023.
- [ ] T417 Independent clean-state verification of deployment (⚠ needs owner approval): spec 001 quickstart deployment sections, the live-scenario sections of specs 002 and 003, and this spec's sections C and D by a second session, recording every command, status code, and timing against SC-004, SC-022, SC-023
- [ ] T418 Run `just destroy-all` then `just verify-clean` and record the empty result (⚠ needs owner approval); measure and record actual cost and `up`/`pause`/`resume` times, and fill this spec's research.md section 5 with measured figures replacing the estimates in spec 001 research.md section 5; if `KEEP_FINAL_SNAPSHOT=1` was used, record the retained snapshot as the declared exception
- [ ] T412 Clean-state run of this spec's quickstart: an actor other than the implementer follows `quickstart.md` sections A-E from a fresh clone (sections that need approval only with the owner's go-ahead) and records commands and observed output; fix or log every divergence between the document and reality in `reconciliation.md`
- [ ] T419 Run `/speckit-analyze` on the finished artifacts of this spec and resolve or document every finding; update spec.md, plan.md, and the checklist to reflect what was actually built

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 0 (Reconcile)** depends on specs 001-003 being complete and blocks everything. T400 first; T401 and T402 next (independent of each other); T403 after both; T404 after T403; T405 any time after T400.
- **Phase 1 (Setup)** depends on Phase 0. T406 and T407 are [P].
- **Phase 2 (Foundational)** depends on Phase 1 and blocks the user stories. T408 and T409 are independent.
- **Phase 3 (US8)** depends on Phase 2. T142 (judge and runner) first. T143 depends on T142 and T408. T144-T147 (native evals) and T148-T151 (observability) are parallel across the four implementations; T148-T151 need T409. T152 depends on T148-T151 having a sidecar target and needs a deployed environment. T153 depends on T142 and T144-T147. T154 depends on T148-T153 and on a deployed environment (`just up`). T410 after T154.
- **Phase 4 (US9)** depends on US8 results for the data-bearing chapters. T155 (criteria with the owner) and T156 (skeleton) can start once Phase 0 is done and can run in parallel with Phase 3. T157-T160 (chapters) need T154 and are [P] with each other. T161-T163 need T154 and the T401 inventory. T164 needs T155, T157-T163. T165 can be written any time after Phase 0. T166 needs T157-T164 and T165. T411 after T166. Sections describing an unbuilt story must say so.
- **Phase 5 (Polish)** last. T171 runs after link pinning (T166) as its text says. T418 (`destroy-all`) is the last environment action; T412 and T419 follow it (T412's live sections use the environment before T418 runs, or a fresh `just up` afterwards with owner approval).

### Parallel lanes

- **Shared lane**: T408, T142, T143, T153, T165.
- **One lane per implementation** (LangGraph, Claude Agent SDK, Pydantic AI, Mastra), each: native evals (T144-T147) then observability (T148-T151). Tasks that edit the same file within one implementation are sequential (`observability.py`/`observability.ts` only here).
- **Infra lane**: T152 (one module, all implementations at once).
- **Report lane**: T155, T156 early; chapters T157-T160 in parallel after T154; cross-cutting chapters T161-T164 after them.

### Example: parallel work within User Story 8

```text
Shared lane:      T142 judge/runner -> T143 tests -> T153 eval CLI
LangGraph lane:   T144 native evals + T148 observability
Claude SDK lane:  T145 native evals + T149 observability
Pydantic AI lane: T146 native evals + T150 observability
Mastra lane:      T147 native evals + T151 observability
Infra lane:       T152 ADOT sidecar + alarm test (needs approval)
then:             T154 live evaluation -> T410 checkpoint
```

## Implementation Strategy

### Reconcile first

1. Phase 0 in full. A short, honest `reconciliation.md` prevents an evaluation of something that was not built.

### MVP

1. Phase 1-2, then T142/T143/T408 and one implementation's native evals and observability.
2. Run `just eval` for that one implementation (live, with approval) and confirm a schema-valid report and a per-run cost lookup in under a minute (SC-009).
3. Stop and validate: contract tier green in CI, one report committed.

### Incremental delivery

Replicate the eval suite and observability across the other three frameworks, then `just eval-all`. Write the criteria and skeleton while evaluation runs, then the chapters from the committed reports, then the cross-cutting chapters, then link pinning and the spot check. Finish with Polish, the independent verification, and the teardown.

### Scope notes

- The report must state unbuilt or unsupported scenarios (US13 sandbox and US14 A2A are optional in spec 003); "not natively supported" is a valid recorded result.
- Deferred by the original spec: model portability/fallback and deterministic record/replay testing.
- Model access is Amazon Bedrock only (spec 001 research D6, FR-023): no Anthropic API key or fallback exists. During any task, append Bedrock problems to the issues log (spec 001 research.md section 6); T162 turns that log into the report chapter (FR-057).
- Task ID map from the original list: T142-T166 and T171 keep their IDs here; original T167-T170 and T172-T174 (also used by spec 001 for its own polish) are renumbered T413-T419 here to avoid a clash; T175-T199 belong to spec 001, T200-T299 to spec 002, T300-T399 to spec 003. New here: T400-T412 and T413-T419.
