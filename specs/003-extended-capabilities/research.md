# Research: Extended Agent Capabilities

**Date**: 2026-09-30 (facts carried from the 2026-09-28 research passes of the original feature) | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

Framework facts below come from research passes on 2026-09-28 against official docs, PyPI/npm, and GitHub, as recorded in the original research. Page summaries were partly produced by a summarizer model, so exact signatures and class names MUST be re-checked against the linked pages when implementing. Anything not confirmed is marked **UNVERIFIED** and becomes a spike task (see "Spikes") rather than an assumption. Framework versions are those verified on 2026-09-28 and pinned in lockfiles by spec 001 (see spec 001 `research.md` §1); Phase 0 confirms the pins are unchanged.

This spec owns decisions D9 (agent-as-MCP-server and A2A), D12 (long context and memory), D16 (sandboxed execution) and the spikes listed in "Spikes". All other decisions (D1-D8, D10, D11, D13-D15, D17, D18, D6/D6a Bedrock and region) are owned by specs 001, 002, and 004 and are not reopened here. D6/D6a in brief, because they constrain everything below: Amazon Bedrock for every model call, no Anthropic API fallback, `us-east-1` for infra and `BEDROCK_REGION`, Claude Sonnet 5.5 for agents (`global.anthropic.claude-sonnet-5-5`), Opus 5.5 for the judge, Haiku 4.5 for helpers, exact IDs as pinned by spike S12 (spec 001).

Legend: **N** = native, **I** = via integration/companion package, **M** = manual (we build it).

## 1. Framework capability matrix (rows this spec exercises)

| Capability (spec ref) | LangGraph (Python) | Claude Agent SDK (Python) | Mastra (TypeScript) | Pydantic AI (Python) |
|---|---|---|---|---|
| Long context (FR-041) | **N**: `SummarizationMiddleware`, `ContextEditingMiddleware`, trimming | **N**: auto-compaction, `PreCompact` hook, 1M context on Sonnet 5 / Opus 5.x | **N**: Observational Memory (Observer/Reflector, 5-40x compression, default observer model is Gemini -> configure Claude Haiku 4.5) | **N**: `ProcessHistory`, `AnthropicCompaction` |
| Long-term memory (FR-043) | **N**: Store with semantic search (Postgres store class name UNVERIFIED) | **M**: CLAUDE.md/auto-memory are file-based; no hosted store. Managed Agents memory stores are a different product | **N**: working memory, semantic recall, observational memory on `@mastra/pg` | **I**: Harness `Memory` (Postgres store) 0.x |
| Agent as MCP server (FR-032) | **I**: Agent Server `/mcp` only; own FastAPI **M/UNVERIFIED** | **M**: wrap `query()` in FastMCP (`claude mcp serve` exposes Claude Code's own tools, not your agent) | **N**: `MCPServer` at `/api/mcp/:serverId/mcp` | **M**: wrap in FastMCP |
| A2A (FR-038) | **I**: Agent Server only (`/a2a/{assistant_id}`); OSS client/server UNVERIFIED | **M** (no support found) | **N**: server + `MastraClient.getA2A()/getA2AV1()` | **I**: `fasta2a[pydantic-ai]` (repo moved to datalayer; supply Storage/Broker/Worker); `Agent.to_a2a()` removed in V2; client UNVERIFIED |
| Dynamic tools / permissions (FR-034/035) | **N**: `LLMToolSelectorMiddleware`, `ProviderToolSearchMiddleware`, HITL `interrupt_on`+`when` | **N**: tool search on by default, `allowed_tools`/`disallowed_tools`, permission modes | **N**: `toolsets`, `activeTools`, `requireToolApproval` fn; per-request tools via `requestContext` UNVERIFIED | **N**: `.filtered() .prepared() .approval_required() .defer_loading()` |
| Sandbox (FR-036) | **I**: Deep Agents backends (E2B, Daytona, Modal, Runloop, ...) = third-party account | **N/UNVERIFIED**: Bash sandbox (bubblewrap) needs `enableWeakerNestedSandbox` in unprivileged containers; Fargate unverified | **N** `Workspace` API but isolation needs remote sandbox (E2B/Daytona) or Docker daemon | **I/N**: provider-side Anthropic code execution (**N**); Harness code-mode (Monty, stdlib only) |
| GitHub retrieval (FR-030) | **M**: community GitHub toolkit being sunset -> own tools or GitHub MCP | **N**: Read/Glob/Grep over a checkout; **I**: GitHub MCP | **M**: Octokit or GitHub MCP; RAG is native | **I**: Harness `[github]` wraps official GitHub MCP; else **M** |
| Claude on Bedrock (FR-023; all **UNVERIFIED**, spike S12) | `langchain-aws` `ChatBedrockConverse` (replaces `langchain-anthropic`) | Bedrock mode via `CLAUDE_CODE_USE_BEDROCK`; tool search and other first-party-only features may be unavailable | AI SDK Amazon Bedrock provider (replaces `anthropic/<model>` strings); caching via `providerOptions` | `pydantic-ai-slim[bedrock]`; `AnthropicCompaction` and provider-side code execution are Anthropic-API features, likely unavailable |

Rows for hosting, multi-agent, durable execution, approval, streaming, scheduling, MCP client, guardrails, native evals, and observability are in spec 001 `research.md` §1 (unchanged) and are exercised by specs 001, 002, and 004.

## 2. Decisions owned by this spec

### D9. Agent-as-MCP-server and A2A
- **Decision**: Mastra uses `MCPServer` and native A2A. LangGraph, Claude Agent SDK and Pydantic AI wrap their agent in FastMCP (official SDK) and, for A2A, use the official `a2a-sdk` (Python) or `fasta2a` where it is the framework's own answer (Pydantic AI). Contracts in [contracts/agent-mcp-server.md](contracts/agent-mcp-server.md) and [contracts/a2a-specialist.md](contracts/a2a-specialist.md). The A2A specialist exposed is the same "risk reviewer" everywhere.
- **Rationale**: Wrapping cost is exactly what the report should record as **M**. Scoped to P3 per the clarification.
- **Alternatives**: skip A2A for frameworks without native support (rejected: FR-038 requires all four).

### D12. Long context and memory (US15)
- **Decision**: Diffs over a configured token threshold are handled per framework with its idiomatic mechanism (LangGraph summarization/context editing, Claude SDK auto-compaction, Mastra Observational Memory, Pydantic AI `ProcessHistory`, and `AnthropicCompaction` only if S12 shows it works on Bedrock), with a shared fixture set of oversized PRs. Durable facts use each framework's native memory (LangGraph Store, Mastra memory, Pydantic AI Harness `Memory`) and a Postgres-backed in-process MCP tool for Claude Agent SDK. Every implementation exposes `/admin/memory` list/correct/delete ([contracts/http-api-additions.yaml](contracts/http-api-additions.yaml) (extends spec 001 `contracts/http-api.yaml`)). Facts are secret-scrubbed on write, stored with source, and capped (default 200 facts, oldest-least-used evicted).
- **Rationale**: FR-041..045; "native where it exists, manual where it doesn't" is what the report needs to record.

### D16. Sandboxed execution (US13, optional)
- **Decision**: Spike only. Attempt where no new infrastructure is needed: Pydantic AI via provider-side code execution (likely "not supported on Bedrock"; S12 confirms), Claude Agent SDK via its Bash sandbox if it works on Fargate. LangGraph (E2B/Daytona/Modal) and Mastra (remote sandbox or Docker daemon) are recorded "not natively supported without a third-party sandbox" unless a spike proves otherwise.
- **Rationale**: FR-036/037 explicitly allow "not natively supported". Running untrusted PR code adds security risk; the owner should not pay for extra vendors.

Note on D12 and spec 002: thread context for `@steward` conversations (User Story 7) is delivered by spec 002; this spec adds the condensing of long threads (FR-042) on top of it, using the mechanisms named in D12.

## 3. Cross-cutting findings to confirm or refute in this spec

Subset of spec 001 `research.md` §3 that these scenarios exercise:
- **API churn**: `langchain-mcp-adapters` archived 2026-09-17; Pydantic AI V2 renamed MCP/history/A2A APIs (`Agent.to_a2a()` removed in V2); Mastra MCP v1 to v2 and `network` to supervisor. Tutorials older than mid-2026 are unreliable.
- **0.x dependency risk**: Pydantic AI Harness (`Memory`, Guardrails, code-mode) is 0.x; `fasta2a` changed owner.
- **Licensing**: Mastra `ee/` features proprietary; LangGraph Agent Server (which also hosts `/mcp` and `/a2a`) is Elastic-2.0 with a license key and is not used, so LangGraph MCP-server and A2A support is recorded as manual.

## 4. Spikes owned by this spec (resolve UNVERIFIED items before dependent tasks)

Outputs go to `specs/003-extended-capabilities/spikes/`. Spike IDs are the originals; where an original spike spans specs, the split is stated.

| ID | Question | Blocks | Task |
|---|---|---|---|
| S1 | Does the LangGraph Postgres Store exist under the current package name, and which class do we use? | US15 (LangGraph) | T314 |
| S5 (sandbox part) | Claude Agent SDK: Bash sandbox on Fargate (`enableWeakerNestedSandbox`); can it run a PR's tests with no secrets and no internal network access? (The `SessionStore` Postgres adapter and `structuredContent` parts of S5 are owned by specs 002 and 001.) | US13 | T131 |
| S6 (A2A part) | Pydantic AI: `fasta2a` persistent Storage/Broker/Worker effort; A2A client; LangGraph A2A outside the Agent Server. (Delegate span nesting and graph persistence are owned by spec 002.) | US14 | T135 |
| S7 | Does each framework's A2A client interoperate with each other's server (A2A v0.3 vs v1.0)? | US14 | T135 |
| S9 | Which Postgres extensions/settings (pgvector) are needed for semantic recall in Mastra/LangGraph on Aurora? | US15 | T130 |
| S13 | Pydantic AI sandbox options on Bedrock: provider-side code execution (expected unavailable, B1) and Harness code-mode | US13 | T132 |

Spikes S2, S3, S4, S8, S10, S11, S12 are owned by specs 001, 002, and 004. From S4, the per-request tools via `requestContext` UNVERIFIED item is consumed by US12 (Mastra): T124 reads spec 002's or 001's S4 finding and does not repeat the spike; if S4 left it open, T124 records the outcome in its own notes.

## 5. Cost note

Spec 001 `research.md` §5 stands. This spec's live scenarios add Bedrock spend (retrieval calls, long-context condensing, memory runs, twelve A2A pairs) and possibly a sandbox on Fargate; all are marked "needs owner approval" in `tasks.md` and run only against a deployed environment the owner has approved.

## 6. Bedrock issues log (owned by spec 001, appended here)

The running log is spec 001 `research.md` §6 (table columns: `#`, Issue, Frameworks affected, Basis D/O, Source, Impact/workaround). This spec appends entries there, continuing the `B<n>` sequence, and never keeps a separate copy. Spec 004 turns the full log into the report chapter (FR-057).

Seeded entries this spec is expected to confirm (D to O) or extend:

| Seed | Relevance here | What to observe |
|---|---|---|
| B1 | US13: Pydantic AI provider-side code execution not available on Bedrock | S13 confirms; record "not supported on Bedrock" |
| B3 | US11: MCP connector and Agent Skills unavailable; agents use client-side MCP (already the plan) | Any MCP-server or MCP-client friction observed under Bedrock |
| B5 | US12: server-side tool search only via InvokeModel, not Converse | Whether each framework's on-demand loading works client-side (T121-T123) |
| B9 | US15: `AnthropicCompaction`, `langchain-anthropic`, Anthropic-only helpers may not work | Whether Pydantic AI compaction works on Bedrock (T128); Mastra observer model (Haiku 4.5, end-of-life date, spec 001 S12) |
| B4, B10, B11 | Wire-format split, throttling, framework maturity | Live scenarios with four implementations calling at once (A2A pairs, memory runs) |

New entries likely: sandbox on Fargate (S5), LangGraph Store or Mastra Observational Memory on Bedrock, A2A/MCP-server behavior of each framework under Bedrock, throttling during `a2a-mixed`.
