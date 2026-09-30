# Research: Evaluation and Comparison Report

**Date**: 2026-09-30 (decisions carried from 2026-09-28) | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

This spec owns the decisions D14 and D17 and the observability spikes below. Shared framework facts (capability matrix, versions verified 2026-09-28, D1-D13, D15, D16, D18, cost estimates in section 5) stay in `specs/001-core-pr-steward/research.md`; read them there instead of copying. Anything marked **UNVERIFIED** is a spike, not an assumption; re-check exact class names against current docs when implementing.

Legend for capability status: **N** native, **I** via integration/companion package, **M** manual (we build it), **NA** not available. These map to the report values `native`, `via_integration`, `manual`, `not_available`.

## 1. Facts this spec relies on (verified 2026-09-28; docs-based)

| Framework | Native eval and observability facts |
|---|---|
| LangGraph | `openevals` and `agentevals` (trajectory match, LLM-judge trajectory evaluators; MIT). Datasets and experiments are LangSmith features. OTel via `langsmith[otel]` (works without a LangSmith export is UNVERIFIED; cost tracking outside LangSmith UNVERIFIED). `recursion_limit`, `ModelCallLimit`/`ToolCallLimit` middleware |
| Claude Agent SDK | No native evals; Anthropic eval guidance only; open-source harnesses are external. OTel from the CLI subprocess (beta traces flag); `total_cost_usd`, `max_turns`, `max_budget_usd` (Claude docs say not to bill from `total_cost_usd`) |
| Mastra | Built-in scorers, custom scorers, `runEvals` in Vitest, datasets/experiments on pg storage. `@mastra/observability` tracing with token and cost auto-recording; exporters: storage, Langfuse, Arize; generic OTLP UNVERIFIED |
| Pydantic AI | `pydantic-evals` (Dataset, LLM judge, span-based evaluators); local, Logfire optional. OTel to any OTLP endpoint; `UsageLimits`; Harness `SpendLimits` (Harness is 0.x) |

Bedrock facts that affect evaluation (from spec 001 D6): no count-tokens on `bedrock-runtime`, so token usage comes from response usage fields; structured outputs unavailable, so scorers use tool-call or JSON-in-text output; Opus 5.5 is not open to all accounts; model access and quotas must be confirmed before the judge runs (S12). Haiku 4.5 has an end-of-life date no sooner than 2026-10-01; do not use it for the judge.

## 2. Decisions

### D14. Evaluation strategy (FR-019, FR-049, FR-050)
- **Decision**: Two layers. (1) **Shared harness** (`shared/conformance`, Python): fixtures (sample PRs with expected properties), contract tests, and an LLM-judge scorer (Opus) that emit the same JSON report for all four; runs against a deployed implementation. (2) **Native evals**, each in its framework's idiom: `pydantic-evals`, `openevals`/`agentevals`, Mastra scorers with `runEvals` in Vitest, and a manual eval for Claude Agent SDK. The report compares the two layers per framework.
- **Rationale**: FR-050 requires that the shared harness not mask native differences. The schema (`contracts/eval-report.schema.json`) keeps `fixtures`/`summary` (harness) apart from `native_evals`.
- **Judge scores**: `accuracy`, `coverage`, `source_citation`, `injection_safe`, `secret_leak`, graded against each fixture's `expected.yaml` with a fixed rubric. The judge is a different, stronger model than the agents (risk R6).
- **Alternatives**: a single shared harness only (rejected: masks native capability, FR-050); hosted platforms such as LangSmith, Langfuse, Logfire (rejected as required infrastructure: third-party accounts; recorded per framework as integrations, status `via_integration` where used).

### D17. Report authoring (FR-029, FR-046..050)
- **Decision**: `docs/report/` (Constitution III). Markdown with per-framework chapters, one scorecard, a capability table like the spec 001 research capability matrix filled with tested results, Taskrabbit suitability criteria, and links pinned to a git tag/commit (`report-eval-1`) via permalink form `https://github.com/yesawoo/agentic-framework-exploration/blob/<sha>/<path>#L<n>`. A `just report-links` check resolves every link and verifies the SHA exists.
- **Suitability criteria (proposal, to confirm with owner in T155)**: stack fit; multi-agent coordination reliability; security/guardrails; observability; evaluation tooling; operational and deployment burden; cost; maintenance/vendor/license risk (Mastra `ee/`, LangGraph Agent Server license, Pydantic AI Harness 0.x, SDK ToS); community maturity/API stability; team learning curve.
- **Cross-cutting findings to confirm or refute** (carried from spec 001 research section 3): API churn (`langchain-mcp-adapters` archived 2026-09-17, Pydantic AI V2 renames, Mastra `network` to supervisor, `TemporalAgent` deprecated); licensing (Mastra `ee/` proprietary, LangGraph Agent Server Elastic-2.0 with license key, Claude Agent SDK under Anthropic Commercial Terms); 0.x dependency risk (Pydantic AI Harness, `fasta2a` changed owner); framework cost figures are client-side estimates; Claude Agent SDK one-subprocess-per-session hosting burden.
- **Rationale**: Constitution III places docs under `docs/`; pinned permalinks satisfy FR-047 and SC-019.
- **Alternatives**: links to `main` (rejected: they drift); a rendered site (rejected: out of scope, Markdown is enough for the audience).

## 3. Spikes owned here

Results go to `specs/004-evaluation-report/spikes/`. Task T409 runs them together.

| ID | Question | Blocks |
|---|---|---|
| S3 | Does LangGraph OTel work without any LangSmith export, and can token cost be read without LangSmith? | T148 |
| S4 (observability part) | Mastra: generic OTLP exporter name; token and cost recording in `@mastra/observability` | T151 |
| S5 (observability part) | Claude Agent SDK: does the CLI subprocess's OTel export (beta traces flag) reach a collector from a Fargate task, and how do `ResultMessage` cost and usage compare to `agent_runs` totals | T149 |
| S6 (observability part) | Pydantic AI: OTLP export of spans to the ADOT sidecar; delegate span nesting as seen in traces | T150 |

The other parts of S4, S5, S6 (scheduling, sandbox, A2A, SessionStore, `fasta2a`) are owned by specs 001-003. Spike S12 (Bedrock) and S8 are owned by spec 001; this spec reads their pinned model IDs and quota values.

## 4. Deferred by the original spec

Model portability/fallback and deterministic record/replay testing. The stub Bedrock used in CI covers plumbing, not agent quality.

## 5. Measured cost and timings (populated by T418)

Replaces the estimates in `specs/001-core-pr-steward/research.md` section 5 once measured. Leave unmeasured cells as "not measured" rather than guessed.

| Item | Estimate (spec 001 research section 5) | Measured (date, source) |
|---|---|---|
| `up` time from taken-down state | under 20 min target (SC-022) | |
| `pause` and `resume` time | under 5 min each (SC-022) | |
| Idle cost while paused as a share of running cost | under 25% (SC-023) | |
| Aurora active ACU-hours during a full evaluation | not estimated | |
| Bedrock spend for one `just eval-all` (agents plus judge) | not estimated | |
| Estimated daily cost reported by `just status` while all four run | per status command | |
| `destroy-all` and `verify-clean` result | no billable resources (SC-023) | |

## 6. Bedrock issues log

Owned by spec 001: `specs/001-core-pr-steward/research.md` section 6 is the single running log (entries B1-B11 seeded from documentation, with S12 and later findings appended by specs 001-003). This spec appends anything it observes during evaluation (judge throttling, Opus access, quota, per-framework differences) to that log, using the same columns:

| # | Issue | Frameworks affected | Basis (D documented / O observed) | Source | Impact / workaround (none if not worked around, FR-024) |
|---|---|---|---|---|---|

T162 turns the whole log into `docs/report/bedrock-issues.md` (FR-057, SC-024): every entry appears, each with a source or evidence link and its D/O marker.
