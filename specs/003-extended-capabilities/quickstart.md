# Quickstart: Extended Agent Capabilities

**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

Assumes the spec 002 quickstart passes (which itself assumes spec 001's), so the environment, credentials, `just` targets, and secrets are already set up. This file covers only the additions. It MUST be runnable top to bottom from a fresh checkout on top of that state (Constitution: Development Workflow, Principle VIII). The scenario and check targets below are **planned**; they are created by tasks in `tasks.md`, and a step is not validated until its target exists.

## 0. Prerequisites

Everything in spec 001 quickstart section 0 (tools, `AWS_PROFILE`, `AWS_REGION`, `BEDROCK_REGION`, `GITHUB_TOKEN`, `WATCHED_REPO`, `OWNER_LOGIN`), plus:

- Phase 0 of `tasks.md` is done (`reconciliation.md` filled in).
- The migrate image contains `0004` (T306) and `just up` applies it to each implementation schema.
- For the A2A scenario: two or more implementations deployed, or all four for the full matrix; peer tokens exist (T315), read from Secrets Manager into the process only and never written to a file.

## 1. Clean-state setup

```bash
git checkout 001-agent-framework-comparison
just setup && just doctor          # spec 001 targets; doctor exits 0
```

## 2. Local contract check (no AWS, no model spend)

```bash
just up-local                      # includes the 0004 migration and inter-implementation networking for A2A tests
just conformance-local             # spec 001 and 002 tests first, then test_us10..us15
```

Expected: retrieval, agent-MCP, tools and permissions, context and memory, sandbox (skipped for frameworks marked not natively supported), and A2A contract tests pass for each implementation. Record the observed pass counts in the PR (Constitution VIII).

## 3. Deploy the additions

```bash
just plan langgraph                # review: A2A variables and peer secrets only (T315); sandbox settings only if T316 applied
just up                            # or: just up langgraph mastra ; migrate applies 0004 before each service starts
just status
just smoke langgraph               # spec 001/002 smoke unchanged; must still pass
```

`just smoke <impl>` additionally records: unauthenticated `/mcp` -> 401, `/admin/memory` with bearer -> 200 and without -> 401, and the agent card at `/.well-known/agent-card.json` -> 200.

## 4. Scenario validations (live tier)

The number in parentheses is the spec story. Each target drives the scenario and asserts the outcome; ⚠ live model spend and GitHub writes need owner approval.

```bash
just scenario langgraph context-memory     # (US10, US15) needs-context and oversized fixtures; convention learned in one PR applied in the next; delete the fact and re-check
just scenario langgraph mcp-server         # (US11) generic MCP client lists tools, summarizes a PR, is refused without credentials
just scenario langgraph tools              # (US12) on-demand load recorded; denied tool refused; requires-approval follows /approve
just scenario langgraph sandbox            # (US13) only where supported; otherwise prints "not natively supported" or "not supported on Bedrock" and exits 0
just scenario langgraph a2a-mixed pydantic-ai   # (US14) coordinator in langgraph uses the pydantic-ai risk specialist
```

Repeat with `claude-agent-sdk`, `mastra`, `pydantic-ai`. The full A2A matrix (12 ordered pairs plus the unreachable-remote case) is `just scenario all a2a-mixed` if T141 registers it that way; otherwise run each pair.

Expected: the memory scenario shows the second run citing its source and a deleted fact never reused (SC-017); `summarize_pr` over MCP returns a correct summary within 2 minutes and unauthenticated connections are refused (SC-012); denied tools are refused and recorded with `outcome='refused'` in `GET /<impl>/admin/runs/{id}` (SC-013); every A2A pair attributes the remote finding with both frameworks in the trace (SC-015).

## 5. Inspect

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" $URL/<impl>/admin/memory     # ADMIN_TOKEN read from Secrets Manager into the shell only
curl -H "Authorization: Bearer $ADMIN_TOKEN" $URL/<impl>/admin/runs/<run_id>   # retrieval, tool_load, memory_*, delegation steps
```

## 6. Teardown

Unchanged from spec 001 quickstart section 7 (`just down`; `just destroy-all` then `just verify-clean`). This spec adds no resource that `down` does not remove, apart from peer-token secrets in the durable layer, which `destroy-all` removes.

## Clean-state verification checklist (Constitution VIII)

Before reporting this spec complete, re-run sections 1-2 in CI and 3-5 from a fresh clone or worktree by an actor other than the implementer (T333). Record the commands and the observed output, including status codes from each `just smoke` and the result of each scenario.
