# Implementation Plan: Evaluation and Comparison Report

**Branch**: `001-agent-framework-comparison` (shared working branch) | **Date**: 2026-09-30 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-evaluation-report/spec.md`. Shared context (constitution check details, risks R1-R13, cost note, project structure) lives in `specs/001-core-pr-steward/plan.md`; this plan states only the delta and restates what a reader needs to work from this spec alone.

## Summary

Measure the four implementations built by specs 001-003 and write the comparison report. Two layers of evaluation: a shared harness (fixtures, an LLM-judge scorer, identical JSON reports, tool-server delivery correctness) and each framework's native evaluation tooling, reported separately (FR-050). Add best-effort OpenTelemetry export and cost accounting per implementation. Write the report under `docs/report/` with per-framework chapters, a scorecard, a Bedrock issues chapter, an evaluation-capabilities chapter, and a Taskrabbit suitability assessment, with every claim linked to a commit-pinned permalink verified by `just report-links`. Finish with whole-environment verification and teardown.

## Technical Context

**Language/Version**: Python 3.13 (`uv`) for the shared harness (`shared/conformance`), the judge, `scripts/report_links.py`, and the LangGraph, Claude Agent SDK, and Pydantic AI native evals; TypeScript on Node 22 LTS, `tsc` strict (Mastra native evals under Vitest).

**Primary Dependencies (delta)**:
- Shared harness: `jsonschema` (report validation), `boto3` (judge calls through Bedrock), `httpx`, `pytest`, all already in `shared/conformance` (spec 001 T010).
- LangGraph evals: `openevals`, `agentevals` (already pinned by spec 001 T005).
- Pydantic AI evals: `pydantic-evals`, `logfire` for local span capture, no Logfire account (spec 001 T007).
- Mastra evals: `@mastra/evals`, `@mastra/pg` for datasets/experiments, `vitest` (spec 001 T008).
- Claude Agent SDK: no native eval package; manual harness using the SDK's `ResultMessage` cost/usage plus the shared judge.
- Observability: OpenTelemetry SDKs per framework path decided by spike T409; an ADOT collector sidecar in `infra/modules/implementation/`.

Exact versions are pinned by lockfiles; versions verified on 2026-09-28 are in `specs/001-core-pr-steward/research.md` section 1.

**Model provider**: Amazon Bedrock only (spec 001 D6, FR-023), region `us-east-1` for infrastructure and `BEDROCK_REGION` (D6a). Judge: Claude Opus 5.5 via `global.anthropic.claude-opus-5-5` (or the ID spike S12 recorded). Agents: Sonnet 5.5. No Anthropic API fallback. Bedrock reserves input plus `max_tokens` at request start and Opus output tokens burn quota at 10x, so judge calls set `max_tokens` tightly and the eval runner throttles concurrency (spec 001 T013 findings).

**Storage**: No new database tables. Eval reports are JSON files under `shared/conformance/reports/<impl>/`, copied to the artifacts bucket by `just down` (spec 001 D18). Reads `agent_runs`, `run_steps`, and `toolserver.*` from spec 001.

**Testing**: `pytest` and Vitest. Contract tier (CI, stub Bedrock and GitHub from spec 001) covers report schema validity, delivery correctness, cost/duration lookup, limit behavior, and `report_links.py`. Live tier (deployed, real Bedrock) produces the committed evidence and needs owner approval.

**Target Platform**: The AWS deployment from spec 001 (ECS Fargate, ALB, CloudFront, Aurora Serverless v2, SQS); local dev via docker compose.

**Project Type**: Delta on the multi-component repository: harness code, per-implementation `evals/`, one infra module change, and Markdown deliverables.

**Performance Goals**: Report lookups in under a minute (SC-009); a full `just eval-all` finishes in one working session within the spend the owner approves. Not optimized beyond that.

**Constraints**: Judge is a different, stronger model than the agents (risk R6); reports identical in format across implementations; native eval results kept separate from harness results; links pinned to a commit that exists; no credentials in any file (constitution V), including in `live-engagement.md`.

**Scale/Scope**: One test repository, the fixture set from specs 001-003 (tens of fixtures), four implementations, one model family.

## Constitution Check

*GATE: passes before Phase 0 of tasks. Re-check after the reconciliation.* Constitution v1.0.0 (Principles I-IX). Shared reasoning is in the spec 001 plan; the delta:

| Principle | Status | Delta in this spec |
|---|---|---|
| I. Test Discipline | Pass | Contract-tier tests for the report schema, judge scorer wiring, and link checker; live results committed as evidence; independent re-run in Polish |
| II. Scripted, Reproducible Deployment | Pass | No new deploy path; `just eval`/`eval-all`/`report-check`/`report-links` are scripted; T152 changes the implementation module and goes through `just plan`/`deploy` |
| III. Repository Conventions | Pass | Report under `docs/report/`; each new `evals/` dir documented in its component `CLAUDE.md`; temp files via `$TMPDIR` |
| IV. Infrastructure as Code | Pass | ADOT sidecar and metric filters only via OpenTofu in `infra/modules/implementation/`; plan reviewed first (owner approval) |
| V. Security by Default | Pass | Judge and evals use the task-role or owner-profile Bedrock chain; `live-engagement.md` redacts tokens; MCP config for T171 references the bearer only as `${ADMIN_TOKEN}` |
| VI. Observability by Default | Pass | Extends 001's logs and metrics with OTel export and confirms alarms by a deliberate-failure test |
| VII. Prefer Maintained Client Libraries | Pass | Native eval packages (`openevals`, `agentevals`, `pydantic-evals`, Mastra scorers), `jsonschema`, boto3; no hand-rolled Bedrock wrapper |
| VIII. Verification from a Clean State | Pass | Checkpoint tasks and an independent clean-state run record commands and output |
| IX. CI Before Completion | Pass | Report schema and link-checker tests run in `conformance.yml`; green run recorded (T415) |

No violations to justify.

## Project Structure

### Documentation (this spec)

```text
specs/004-evaluation-report/
├── spec.md
├── plan.md              # This file
├── research.md          # D14, D17, and this spec's spikes; measured cost section
├── data-model.md        # No new tables; eval artifacts and report entities
├── quickstart.md        # Assumes spec 001 quickstart passes; eval, report, final teardown
├── reconciliation.md    # Filled in Phase 0
├── tasks.md
├── contracts/
│   ├── eval-report.schema.json
│   └── http-api-additions.yaml   # No new paths; documents what is reused
├── checklists/requirements.md
└── spikes/              # S3 and observability parts of S4/S5/S6 (T409)
```

### Source code touched (repository root)

```text
shared/conformance/
├── src/conformance/{judge.py,evalrun.py,cli.py,report.py}   # judge and eval runner new; cli.py and report.py extended
├── tests/test_us8_reports.py
└── reports/<impl>/                                          # committed live results (with git SHA)
implementations/<name>/evals/                                # native eval suites (one per framework)
implementations/<name>/src/steward/observability.py         # (Mastra: src/observability.ts) OTel export and cost accounting
infra/modules/implementation/                                # ADOT collector sidecar, metric filters
docs/report/                                                 # index, scorecard, criteria, 4 chapters, mcp-evaluation, bedrock-issues,
                                                             # evaluation-capabilities, taskrabbit-suitability, verification, live-engagement
scripts/report_links.py
```

**Structure Decision**: Reuse the layout defined in spec 001. New code is limited to the shared harness additions, per-implementation `evals/` and `observability` files, one module change, and documents. No shared agent logic is introduced across frameworks; the judge and harness are shared evaluation code, allowed by the constitution.

## Phasing (input to tasks)

Phase numbers restart per spec.

0. **Reconcile** with completed specs 001-003 (T400-T405). Blocks everything.
1. **Setup**: confirm skeleton directories and eval dependencies (T406-T407).
2. **Foundational**: wire report validation to the schema (T408); observability spike (T409).
3. **US8**: judge, report tests, four native eval suites, four observability implementations, ADOT sidecar and alarm test, eval CLI, full live evaluation, checkpoint.
4. **US9**: confirm criteria, skeleton, four chapters, cross-cutting chapters, link checker, pinning and spot check, checkpoint.
5. **Polish and whole-environment verification**: final documentation, CI green, independent clean-state runs, live agent engagement, `destroy-all` and `verify-clean`, `/speckit-analyze`.

## Risks (delta; see spec 001 plan for R1-R13)

| ID | Risk | Mitigation |
|---|---|---|
| R6 | LLM-judge scoring is noisy and biased toward its own model family | Opus judge vs Sonnet agents; fixed rubric from `expected.yaml`; sample size and limits stated in the report (FR-048) |
| R7 | Taskrabbit's criteria are not yet defined | Proposed in D17; T155 confirms with the owner before chapters are written |
| R14 | A predecessor spec drifted from what this spec assumes (field names, endpoint shapes, unbuilt stories) | Phase 0 reconciliation and `reconciliation.md`; the report states unbuilt scope instead of papering over it |
| R15 | Links rot or point at moved lines after later commits | Permalinks pinned to a tagged SHA (`report-eval-1`), `just report-links` checks path and line range at that SHA |
| R16 | Bedrock throttling or quota during the four-way live evaluation | Per-implementation sequencing option in `evalrun.py`, retries per FR-012, quota values recorded by S12, throttling logged to spec 001 research section 6 as a finding |
| R17 | Framework OTel export is uneven (LangGraph without LangSmith, Mastra generic OTLP are UNVERIFIED) | Spike T409 first; the `agent_runs` row remains the comparable source of truth and OTel stays best-effort (D13) |

## Complexity Tracking

No constitution violations. The only addition that might look heavy is the ADOT sidecar, required to show whether each framework exports traces usefully (FR-018 extended) while keeping comparable telemetry independent of it.
