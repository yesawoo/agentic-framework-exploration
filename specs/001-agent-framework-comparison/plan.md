# Implementation Plan: Agent Framework Comparison

**Branch**: `001-agent-framework-comparison` | **Date**: 2026-09-28 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-agent-framework-comparison/spec.md`

## Summary

Build the same "PR steward" agent four times (LangGraph, Claude Agent SDK, Mastra, Pydantic AI) against one shared behavioral contract, deploy each to AWS with OpenTofu, evaluate them with a shared harness plus each framework's native eval tooling, and publish a comprehensive comparison report (with pinned links to code and results) assessing suitability as Taskrabbit's multi-agent library.

Technical approach (details and alternatives in [research.md](research.md)):

- **Easy spin up/down**: `just up`, `down`, `pause`, `resume`, `status` wrap the per-component `deploy`/`destroy` targets; a small durable layers (state, images, secrets, the database, and the CloudFront distribution with its stable URL) survive teardown so data persists, images are not rebuilt, and the GitHub webhook stays valid; the database is Aurora Serverless v2 with scale-to-zero so an idle environment pays almost nothing for it (research D4, D18).
- **Uniform deployment shape**: every implementation is a container on ECS Fargate behind one ALB (path prefix) fronted by a long-lived CloudFront distribution for stable HTTPS; per-implementation OpenTofu state; one shared Aurora Serverless v2 Postgres with a schema per implementation.
- **Uniform plumbing, framework-specific agent logic**: webhook verification, SQS work queue, EventBridge-triggered digest and approval sweeps follow one contract ([contracts/](contracts/)); everything about how the agent reasons, delegates, remembers, and streams is written in each framework's own idiom and is *not* shared (Constitution: Development Workflow).
- **Reference MCP tool server** (Python, official MCP SDK) records summaries, reviews and digests, attributes them to the submitting implementation, and logs each MCP client's calls for the MCP evaluation.
- **Evaluation in two layers**: a shared harness (fixtures, contract tests, LLM-judge scorer, identical JSON reports) and native evals per framework, reported separately.
- **P3 breadth scenarios** (retrieval, agent-as-MCP-server, dynamic tools and permissions, sandbox, A2A, long-context and memory) are built where each framework allows, and recorded as native / integration / manual with evidence.

## Technical Context

**Language/Version**: Python 3.13 (LangGraph, Claude Agent SDK, Pydantic AI, tool server, conformance harness); TypeScript on Node 22 LTS, `tsc` strict (Mastra)

**Primary Dependencies**:
- LangGraph: `langgraph` 1.2.x, `langgraph-checkpoint-postgres`, `langchain`/`langchain-aws` (Bedrock), `langchain.mcp` (beta), FastAPI
- Claude Agent SDK: `claude-agent-sdk` 0.2.x (Bedrock mode), FastAPI
- Mastra: `@mastra/core` 1.x, AI SDK Amazon Bedrock provider, `@mastra/pg`, `@mastra/memory`, `@mastra/mcp`, `@mastra/observability`, `@octokit/rest`, `@octokit/webhooks`
- Pydantic AI: `pydantic-ai` 2.x (+`[bedrock]`), `pydantic-ai-harness` 0.x, `pydantic-evals`, `fasta2a`, FastAPI
- Shared: `mcp` (official Python SDK), `a2a-sdk`, `PyGithub`, `psycopg` 3, `boto3`, `pytest`, `ruff`; `docker compose`, ElasticMQ for local SQS
- Infra: OpenTofu (AWS provider), `just`, GitHub Actions

Exact versions are pinned by lockfiles; see research §1 for versions verified on 2026-09-28.

**Model provider**: Amazon Bedrock (because Taskrabbit uses it) for every model call (agents, judge, helpers) in all four frameworks; Claude Sonnet 5.5 for agents, Opus 5.5 for the judge, Haiku 4.5 for helpers; access through each ECS task role, no model API key, no Anthropic API fallback (spec FR-023; research D6). Conditional on spike S12, which runs first. **Region**: `us-east-1` for all infrastructure and for `BEDROCK_REGION` (one region, not split; the whole stack is region-parameterised so it can move; fallback `us-west-2`, or `us-east-2` for a separate quota bucket; research D6a).

**Storage**: Aurora Serverless v2 PostgreSQL with scale-to-zero (schema per implementation + `toolserver`); SQS (queue + DLQ per implementation); Secrets Manager; S3 for OpenTofu state and eval report artifacts

**Testing**: `pytest` (Python components, conformance harness), Vitest (Mastra, including `runEvals`), `pydantic-evals`, `openevals`/`agentevals`; two conformance tiers: contract tier (CI, stubbed model and GitHub) and live tier (deployed, real model)

**Target Platform**: AWS (ECS Fargate, ALB, CloudFront, Aurora Serverless v2, SQS, EventBridge Scheduler, CloudWatch/X-Ray, Secrets Manager); local dev via docker compose on macOS

**Project Type**: Multi-component repository: four service implementations, one shared tool server, one conformance/eval harness, OpenTofu infrastructure, and a written report

**Performance Goals**: Summary record delivered within 2 min of PR open (SC-001); webhook acknowledged within 2 s; single-run duration and cost recorded, not optimized

**Constraints**: One Claude model family for all implementations, served only through Bedrock; secrets never on disk in the repo; all infra via `tofu` with plan review; per-implementation deploy/destroy independence; no shared agent logic across frameworks; model spend bounded by per-run step/time/cost limits and a monthly budget alarm

**Scale/Scope**: One test repository, tens of PRs and fixtures, four implementations; low traffic; no multi-tenancy, no HA

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.* Constitution v1.0.0 (Principles I–IX).

| Principle | Status | How the plan satisfies it |
|---|---|---|
| I. Test Discipline | Pass | `pytest`/Vitest + `ruff`/`tsc --noEmit` in CI; independent reproduction by CI and a second session per quickstart |
| II. Scripted, Reproducible Deployment | Pass | `just deploy/destroy/plan/smoke <component>` are the only deploy path, with `up/down/pause/resume/status` as orchestration over them (same behavior local and CI); `down` removes everything `deploy` created and the durable and edge layers (created by `bootstrap`) are removed by `destroy-all`; health check verified by `deploy`; each implementation independently deployable/removable; `verify-clean` proves teardown. No CI-triggered deploy in v1 (allowed by the principle) |
| III. Repository Conventions | Pass | Each `implementations/*`, `shared/*`, `infra/*` root gets a `CLAUDE.md`; report and design docs under `docs/`; temp files via `$TMPDIR` |
| IV. Infrastructure as Code | Pass | OpenTofu only; shared root, tool-server root, and one root per implementation, each with separate state; plan reviewed before apply |
| V. Security by Default | Pass | Runtime secrets (GitHub token, webhook secret, admin/tool-server tokens) in Secrets Manager provisioned by OpenTofu and injected at runtime; model access via task-role IAM scoped to the pinned Bedrock models, so no model key exists (Principle V lists a "model API key"; nothing to store under Bedrock, no amendment needed); owner credentials via env/profile only; SOPS+age for any in-repo secret (none planned); webhook HMAC, bearer auth on MCP/admin/A2A, CloudFront-only ALB origin |
| VI. Observability by Default | Pass | JSON logs to CloudWatch with run/delivery/agent/tool ids; metrics via EMF; alarms for 5xx, failed runs, DLQ depth, missed digest; each component's `CLAUDE.md` documents them (D13) |
| VII. Prefer Maintained Client Libraries | Pass | PyGithub/Octokit, official `mcp` SDK, `a2a-sdk`, boto3; MCP integration used when the framework supplies one and behavior recorded; one documented idiomatic exception (Claude SDK retrieval via checkout) is a framework capability, not a hand-rolled client |
| VIII. Verification from a Clean State | Pass | Quickstart begins with clean-state setup; smoke checks record status codes; completion requires commands and output |
| IX. CI Before Completion | Pass with risk | Per-component workflows including conformance contract tier for every implementation on the branch; green run required before completion. Risk R2: framework endpoint override for the stub Bedrock server (spike S8) |

Development Workflow: no agent logic shared beyond contract, fixtures, and tool server (satisfied by structure below); `quickstart.md` is executable.

**Post-design re-check (after Phase 1)**: Pass. The design adds no principle violation. Items to keep an eye on during implementation are the CI stub model (R2) and secret handling in `just secrets-load` (must read from the environment and never write files).

## Project Structure

### Documentation (this feature)

```text
specs/001-agent-framework-comparison/
├── spec.md
├── plan.md              # This file
├── research.md          # Phase 0: capability matrix, decisions, spikes
├── data-model.md        # Phase 1: tables and artifacts
├── quickstart.md        # Phase 1: executable validation guide
├── contracts/           # Phase 1
│   ├── http-api.yaml            # every implementation's HTTP surface
│   ├── mcp-tool-server.md       # reference tool server (MCP)
│   ├── agent-mcp-server.md      # agent exposed as MCP server
│   ├── a2a-specialist.md        # cross-framework specialist
│   ├── work-queue.md            # SQS message contract
│   ├── environment.md           # one naming scheme for every environment variable
│   ├── observability.md         # log fields and CloudWatch EMF metrics/alarms
│   └── eval-report.schema.json  # identical eval report format
├── checklists/requirements.md

└── tasks.md             # Phase 2 (/speckit-tasks; not created here)
```

### Source Code (repository root)

```text
implementations/
├── langgraph/                # Python; FastAPI + LangGraph; CLAUDE.md, pyproject.toml, tests/
├── claude-agent-sdk/         # Python; FastAPI + claude-agent-sdk; CLAUDE.md, pyproject.toml, tests/
├── pydantic-ai/              # Python; FastAPI + pydantic-ai(+harness); CLAUDE.md, pyproject.toml, tests/
└── mastra/                   # TypeScript; Mastra server; CLAUDE.md, package.json, tsconfig.json, tests/
shared/
├── tool-server/              # Python; official mcp SDK; CLAUDE.md, pyproject.toml, tests/
├── db/                       # Python; migrate.py runner + SQL migrations per schema; CLAUDE.md, pyproject.toml, tests/ (own CI: db-ci.yml)
└── conformance/              # Python harness: contract tier, live tier, fixtures/, reports/, judge, stub-model + stub-github servers
infra/
├── durable/                  # survives `down`: S3 state bucket + lock, ECR repos, Secrets Manager, artifacts bucket, SNS + budget alarm, VPC/subnets, Aurora Serverless v2 cluster, the migrate task, app-to-db security group, and db-role secrets
├── edge/                     # survives `down`: CloudFront distribution (stable domain); origin repointed by `up`/`down`
├── shared/                   # runtime: ECS cluster, ALB, security groups, log groups
├── tool-server/              # ECS service for the tool server
├── modules/implementation/   # reusable OpenTofu module (ECS service, SQS+DLQ, schedules, alarms); CLAUDE.md
└── implementations/
    ├── langgraph/            # ECS service, target group/rule, SQS+DLQ, EventBridge schedules, alarms (DB role secret comes from durable; schema and role are created by the migrate task)
    ├── claude-agent-sdk/
    ├── mastra/
    └── pydantic-ai/
docs/
├── report/                   # the comparison report (index.md, per-framework chapters, scorecard, suitability)
└── design/                   # any long-form design notes (optional)
compose.yaml                  # local stack for the contract tier
justfile                      # all sanctioned deploy/test targets
scripts/                      # report_links.py and other helper scripts invoked by justfile targets
.github/workflows/            # <component>-ci.yml per component + conformance.yml, db-ci.yml, infra-ci.yml
CLAUDE.md                     # root policies
```

**Structure Decision**: One top-level directory per concern (implementations / shared / infra / docs). Each implementation is a self-contained deployable with its own `CLAUDE.md`, lockfile, container image, and OpenTofu root, so a framework can be built, deployed, and destroyed alone (Constitution II, III, IV). Shared code is limited to the tool server, the conformance harness, fixtures, and stubs, which the constitution allows; there is intentionally no shared "agent library".

## Phasing (input to `/speckit-tasks`)

Phases follow spec priorities. Each phase ends with something verifiable from a clean state.

1. **Foundations**: repo scaffolding, root `CLAUDE.md`, `justfile`, `infra/durable`, `infra/edge`, `infra/shared`, CI skeleton; local compose stack (Postgres, ElasticMQ, stubs); spikes S12 first (Bedrock works from every framework; it gates the provider decision), then S8, S10, S11 (Aurora scale-to-zero behavior, resume latency, idle keepalives). **Orchestration** (`up`/`down`/`pause`/`resume`/`status`, `db-reset`, webhook registration, uptime guard) lands here and is exercised by every later phase.
2. **Tool server and harness core**: `shared/tool-server`, conformance contract tier, fixtures (initial set), eval report schema validation.
3. **P1 slice, one framework first** (recommend Pydantic AI or LangGraph): webhook -> queue -> summary -> MCP record; deploy end-to-end; then replicate the same contract in the other three (spikes S2, S4, S5, S6 as they come due). Deployment (US2) is proven here.
4. **P2**: daily digest (US3), multi-agent review (US4), reliability and safety (US5) in all four.
5. **P3 breadth**: approval (US6), chat/streaming (US7), retrieval (US10), agent-as-MCP (US11), tools/permissions (US12), memory/long-context (US15), then optional sandbox (US13) and cross-framework A2A (US14).
6. **Evaluation**: live tier + native evals (US8), `just eval-all`, report JSON validation.
7. **Report** (US9): per-framework chapters, a prominent Bedrock issues chapter built from the log in research §6 (FR-057), capability table, Taskrabbit criteria (confirm with owner), recommendation, link pinning and `report-links`.
8. **Clean-state verification and teardown**: independent run of the quickstart, `verify-clean`.

## Risks

| ID | Risk | Mitigation |
|---|---|---|
| R1 | Framework APIs are churning (LangChain MCP archived, Pydantic AI V2, Mastra supervisor migration); docs and tutorials go stale | Pin versions; verify against current docs; record churn as a report finding |
| R13 | Bedrock cannot do something a framework needs. Docs-verified gaps: no server-side tools (code execution, web search), no structured outputs, no MCP connector, no count-tokens on `bedrock-runtime`; Sonnet 5.5 is global-inference-profile only; Opus 5.5 and Sonnet 5.5 need account model access; throttling with four implementations at once is unmeasured. The CI stub must speak both Converse and Invoke (binary event-stream) | Spike S12 before any model-dependent work; unsupported features are recorded as "not supported on Bedrock", never worked around or routed to the Anthropic API (FR-023); a framework with no Bedrock support returns the provider decision to the owner |
| R2 | A framework will not accept an endpoint override, so the CI stub Bedrock server cannot be used (Claude SDK bundled binary, Mastra AI SDK provider, SigV4 against a stub) | Spike S8 first; fallback is a contract tier that stubs at the agent-tool boundary for that framework, documented in `CLAUDE.md` |
| R3 | Claude Agent SDK subprocess model needs more memory/disk than expected; SDK session persistence is local by default | Spike S10, S5; size tasks accordingly; Postgres `SessionStore` adapter |
| R4 | Sandboxed execution of PR code is a security risk and often needs third-party vendors | US13 is optional and spike-only; no secrets or internal network access in any sandbox; "not natively supported" is an acceptable result |
| R5 | Live model and AWS spend grows while four implementations run | Per-run cost/step limits (FR-016), monthly budget alarm, scheduled `destroy` guidance, cost note in research §5 (estimates to verify) |
| R6 | LLM-judge scoring is noisy and biased toward its own model family | Different, stronger judge model; fixed rubric; sample size and limits stated in the report (FR-048) |
| R7 | Taskrabbit's criteria are not yet defined | Proposed criteria in research D17; confirm with owner before the report phase |
| R8 | 0.x dependencies (Pydantic AI Harness, `fasta2a`) may change or lose maintenance | Pin versions; record as maintenance risk in the report |
| R10 | Aurora resume from pause takes seconds, so first requests after idle can fail or time out; idle keepalives (ALB health check, framework pools) can prevent pausing and silently cost money | Handler never touches the DB before 202 (D4/D5); `/health` is DB-free, `/ready` checks deps; workers retry connections; spike S11 verifies each framework's pool behavior; `status` shows paused/active |
| R11 | The ALB DNS name changes on each `up`, so the long-lived CloudFront origin must be updated, and that deploy takes minutes; `up` may miss the 20 minute target | Measure in S11; fallback is a long-lived ALB (small idle cost) so the origin never changes |
| R12 | A long-lived database outlives code changes, so old data can meet new schemas | Migrations run as a one-shot migrate task (defined in `infra/durable`) before each deploy; `FRESH=1` / `just db-reset` drops implementation schemas; `destroy-all` removes the cluster |
| R9 | CloudFront + ALB + SSE buffering could break streaming | Validate SSE through CloudFront in the foundations phase; fall back to direct ALB HTTPS with owner domain |

## Complexity Tracking

No constitution violations to justify. Additions that might look like extra complexity, each required by a stated principle or requirement: a long-lived CloudFront layer (HTTPS and a stable webhook URL without a domain, FR-001, FR-053), a database that survives teardown (FR-053), a stub model/GitHub server (conformance in CI without model spend, Principle IX), separate OpenTofu roots per implementation (Principle IV), an `agent_runs`/`run_steps` record per implementation (FR-018 comparability).
