# Implementation Plan: Extended Agent Capabilities

**Branch**: `001-agent-framework-comparison` (shared) | **Date**: 2026-09-30 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-extended-capabilities/spec.md`. Predecessor plans: spec 001 `plan.md` (shared technical context, structure, risks) and spec 002 `plan.md`. This plan states only the delta and restates what a reader needs to work from this spec alone.

## Summary

Add six extended capabilities to each of the four PR-steward implementations (LangGraph, Claude Agent SDK, Mastra, Pydantic AI), each in the framework's own idiom and each recorded as native, via integration, manual, not supported on Bedrock, or not natively supported: repository retrieval (US10), the agent as an MCP server (US11), dynamic tools with permissions (US12), long-context handling and durable memory (US15), optional sandboxed execution (US13), and cross-framework A2A specialists (US14). Everything runs on the environment, contract, and harness built by specs 001 and 002; this spec adds one migration, three tables, a small contract addition, fixtures, tests, and per-framework code. Details and alternatives: [research.md](research.md) (decisions D9, D12, D16; spikes S1, S5 sandbox part, S6 A2A part, S7, S9, S13).

Phase 0 reconciles this plan against the as-built predecessors before any new work starts (spec.md "Reconciliation", `reconciliation.md`).

## Technical Context (delta)

**Language/Version** (restated; unchanged from spec 001): Python 3.13 (LangGraph, Claude Agent SDK, Pydantic AI, conformance harness); TypeScript on Node 22 LTS, `tsc` strict (Mastra).

**Primary dependencies used here** (pinned by spec 001 lockfiles; verified 2026-09-28, re-checked in Phase 0):
- LangGraph: `langgraph` 1.2.x, `langgraph-checkpoint-postgres`, the LangGraph Postgres Store (S1), `langchain` middleware (`SummarizationMiddleware`, `ContextEditingMiddleware`, `LLMToolSelectorMiddleware`, `ProviderToolSearchMiddleware`), `langchain-aws`, FastMCP (`mcp`), `a2a-sdk`, PyGithub
- Claude Agent SDK: `claude-agent-sdk` 0.2.x (Bedrock mode, Invoke API only), built-in Read/Grep/Glob over a shallow checkout, tool search, `allowed_tools`/`disallowed_tools`, `PreCompact` hook, Bash sandbox (S5), FastMCP, `a2a-sdk`
- Mastra: `@mastra/core` 1.x, `@mastra/mcp` (`MCPServer`), `@mastra/memory` (Observational Memory, working memory, semantic recall), `@mastra/pg`, native A2A and `MastraClient`, `@ai-sdk/amazon-bedrock`, `@octokit/rest`
- Pydantic AI: `pydantic-ai` 2.x (`ProcessHistory`, toolset `.filtered()/.prepared()/.defer_loading()/.approval_required()`), `pydantic-ai-harness` 0.x (`Memory`, code-mode), `fasta2a`, `a2a-sdk`, FastMCP, PyGithub
- Shared: `mcp` (official Python SDK, also the generic MCP client in the harness), `a2a-sdk`, `psycopg` 3, `pytest`, `ruff`; Vitest for Mastra; Postgres with `pgvector`

**Model provider** (restated): Amazon Bedrock for every model call in all four frameworks; Claude Sonnet 5.5 for agents, Opus 5.5 for the judge, Haiku 4.5 for helpers; access through each ECS task role, no model API key, no Anthropic API fallback (spec FR-023; spec 001 research D6). **Region**: `us-east-1` for all infrastructure and for `BEDROCK_REGION` (spec 001 research D6a). Pinned inference-profile IDs come from spike S12 (spec 001).

**Storage** (delta): migration `0004_extended_tables.sql` adds `memory_facts`, `tool_grants`, `sandbox_runs` per implementation schema; the Aurora Serverless v2 cluster, the migrate task, and the `vector` extension are spec 001's. Framework memory stores (LangGraph Store, `@mastra/pg`, Harness `Memory`) live beside these tables in each schema.

**Testing**: as spec 001 (`pytest`, Vitest, contract tier in CI against the stub Bedrock and stub GitHub; live tier deployed). This spec adds one contract-tier test file per story and live scenarios `context-memory`, `mcp-server`, `tools`, `sandbox`, `a2a-mixed`.

**Target Platform**: unchanged (ECS Fargate, ALB, CloudFront, Aurora Serverless v2, SQS). Agent MCP and A2A endpoints are served under each implementation's path prefix through the existing CloudFront and ALB rules.

**Performance Goals**: `summarize_pr` over MCP returns within 2 minutes (SC-012); retrieval stays inside the run's step and cost limits (FR-031); per-remote A2A call timeout 30 s.

**Constraints** (delta): no shared agent logic across frameworks; sandbox gets no secrets and no internal network access; no custom sandbox or third-party sandbox vendor; A2A peers are configured and authenticated, never open; no Anthropic API fallback.

**Scale/Scope**: unchanged. Memory capped at 200 active facts per implementation.

## Constitution Check

*GATE: Must pass before Phase 0 tasks and re-check after Phase 1.* Constitution v1.0.0 (Principles I-IX), same evaluation as spec 001 plus these specifics.

| Principle | Status | How this spec satisfies it |
|---|---|---|
| I. Test Discipline | Pass | One contract-tier test file per story runs in CI for every implementation; per-task commands and output recorded; independent reproduction at T333 |
| II. Scripted, Reproducible Deployment | Pass | No new deploy path. New live scenarios run through `just scenario`; infra changes (T315, T316) go through the existing module and `just plan`/`deploy`; `down` still removes everything `deploy` created |
| III. Repository Conventions | Pass | Each touched component's `CLAUDE.md` gains a capability status table (T330); spikes under `specs/003-extended-capabilities/spikes/`; temp files via `$TMPDIR` |
| IV. Infrastructure as Code | Pass | Peer-token secrets and variables through OpenTofu only, plan reviewed first (T315, T316); default off or empty so core deployments are unchanged |
| V. Security by Default | Pass | Agent MCP and `/admin/memory` behind `ADMIN_TOKEN`; A2A bearer per configured peer, unknown peers 401; sandbox has no secrets; retrieved and remembered content treated as untrusted; memory writes scrubbed |
| VI. Observability by Default | Pass | Retrievals, tool loads, refusals, memory reads/writes, and delegations are `run_steps` rows; JSON logs carry `run_id`; component `CLAUDE.md` files document them |
| VII. Prefer Maintained Client Libraries | Pass | Official `mcp` SDK, `a2a-sdk`, `fasta2a`, PyGithub/Octokit, framework Bedrock clients; MCP/A2A wrappers are recorded as manual, not hand-rolled protocol clients. Documented exception (Claude Agent SDK retrieval via checkout) is spec 001's D7 |
| VIII. Verification from a Clean State | Pass | Quickstart begins by assuming spec 002's passes, then re-runs additions from a clean checkout (T333); checkpoints per story |
| IX. CI Before Completion | Pass with risk | Contract tier extended for each story; risk R2 from spec 001 (stub endpoint override) applies to any framework whose spike S8 needed the agent-tool-boundary fallback |

Development Workflow: no agent logic shared beyond contract, fixtures, and tool server. **Post-design re-check**: Pass; no violation added.

## Project Structure

### Documentation (this spec)

```text
specs/003-extended-capabilities/
├── spec.md
├── plan.md                        # This file
├── research.md                    # D9, D12, D16; spikes S1, S5 (sandbox), S6 (A2A), S7, S9, S13; Bedrock log pointer
├── data-model.md                  # memory_facts, tool_grants, sandbox_runs (migration 0004)
├── quickstart.md                  # additions only; assumes spec 002 quickstart passes
├── reconciliation.md              # Phase 0 output (stub until T301)
├── contracts/
│   ├── agent-mcp-server.md        # agent exposed as MCP server (FR-032, FR-033)
│   ├── a2a-specialist.md          # cross-framework specialist (FR-038..040)
│   ├── http-api-additions.yaml    # /admin/memory; extends spec 001 contracts/http-api.yaml
│   └── environment-additions.md   # extends spec 001 contracts/environment.md
├── checklists/requirements.md
├── spikes/                        # created by tasks: S1, S5, S7, S9, S13 findings
└── tasks.md
```

### Source Code (delta at repository root; the base layout is spec 001's plan)

```text
implementations/<impl>/            # each of langgraph, claude-agent-sdk, pydantic-ai (Python), mastra (TypeScript)
└── src/steward/                   # Mastra: src/
    ├── tools/retrieval.{py,ts}    # US10
    ├── tools/grants.{py,ts}       # US12
    ├── tools/sandbox.{py,ts}      # US13 (only where the spike shows trivial support)
    ├── mcp_server.{py,ts}         # US11
    ├── memory.{py,ts}             # US15 (also edits admin.{py,ts} for /admin/memory)
    └── a2a.{py,ts}                # US14 (also edits agents/review.{py,ts} to add remote specialists)
config/tool_grants.yaml            # per implementation, path in TOOL_GRANTS_FILE
shared/
├── db/migrations/0004_extended_tables.sql
└── conformance/
    ├── fixtures/                  # memory-convention-a/b, injected-convention, failing-test, retrieval-injection
    ├── src/conformance/{mcp_client.py,a2a_client.py,scenarios/{context_memory,mcp_server,tools,sandbox,a2a_mixed}.py}
    └── tests/test_us{10,11,12,13,14,15}_*.py
infra/
├── modules/implementation/        # A2A variables and peer secret injection; optional sandbox settings (default off)
└── durable/                       # peer-token secret entries (or the location recorded in reconciliation.md)
```

**Structure Decision**: Extend the existing per-implementation layout; no new top-level directory. New files are added beside spec 001 and 002 files, and the files that must be edited (`summary`, `review`, `admin`) are named in `tasks.md` so their sequencing is explicit.

## Phasing (input to tasks.md)

0. **Reconcile** with the completed predecessors (T300-T304); blocks everything.
1. **Foundational**: migration `0004`, fixtures, harness additions, compose variables.
2. **US10** retrieval; 3. **US11** agent as MCP server; 4. **US12** tools and permissions (needs spec 002 approval flow).
5. **US15** long context and memory (spikes S1, S9 first; builds on US10 and spec 002 thread context).
6. **US13** sandbox (optional; spike first); 7. **US14** A2A (spike S7 first; needs deployed implementations).
8. **Polish**: CLAUDE.md capability tables, Bedrock log, CI evidence, clean-state run, as-built deviations, `/speckit-analyze`.

## Risks (this spec's slice of the original register; IDs kept)

| ID | Risk | Mitigation |
|---|---|---|
| R1 | Framework APIs are churning (LangChain MCP archived, Pydantic AI V2 renames, Mastra MCP v1 to v2); docs and tutorials go stale | Pin versions; verify against current docs in Phase 0 (T303); record churn as a report finding |
| R2 | A framework will not accept an endpoint override, so the contract tier cannot drive it through the stub Bedrock server | Spec 001 spike S8 result per framework; where a fallback was chosen, this spec's contract tests use the same fallback (T301 checks) |
| R4 | Sandboxed execution of PR code is a security risk and often needs third-party vendors | US13 is optional and spike-only; no secrets or internal network in any sandbox; "not natively supported" is an acceptable result |
| R8 | 0.x dependencies (Pydantic AI Harness `Memory`, `fasta2a`) may change or lose maintenance | Pin versions; record as maintenance risk in the report |
| R13 | Bedrock cannot do something a framework needs here: no server-side tools (so no provider-side code execution), server-side tool search only via Invoke, possibly `AnthropicCompaction` and other Anthropic-only helpers | Record "not supported on Bedrock" in spec 001 research §6, never work around or use the Anthropic API (FR-023); load tools and compact history client-side where the framework allows |
| R14 (new, this spec) | A2A version skew (v0.3 vs v1.0) and unverified client/server support make some of the 12 ordered pairs fail for protocol reasons | Spike S7 first; a failing pair is a recorded result, degrading to a labeled partial review (FR-040) |
| R15 (new, this spec) | Memory poisoning through PR content, or unbounded memory growth | FR-045 scrubbing, untrusted-on-reuse, cap of 200 with LRU eviction, `injected-convention` fixture (SC-018) |

Risks R3, R5, R6, R7, R9-R12 belong to specs 001, 002, and 004.

## Complexity Tracking

No constitution violations to justify. Additions that might look like extra complexity, each required by a stated requirement: a fourth migration (`0004`, keeps each spec's tables with the spec that needs them), a generic MCP client and an A2A client in the conformance harness (FR-032, FR-038 must be tested from outside each framework), and per-peer secrets and variables in the implementation module (FR-039 requires authenticated configured peers).
