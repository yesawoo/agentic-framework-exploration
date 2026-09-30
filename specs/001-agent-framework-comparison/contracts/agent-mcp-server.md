# Contract: Agent exposed as an MCP server

**Requirements**: FR-032, FR-033 (User Story 11) | Transport: MCP Streamable HTTP at `/<implementation>/mcp` | Auth: bearer token (`ADMIN_TOKEN` secret).

Native in Mastra (`MCPServer`); wrapped with FastMCP (official `mcp` SDK) in the other three (see research D9). The contract is identical for all four.

## Tools

### `summarize_pr`
Input: `{"repo": "owner/name", "pr_number": 12}`
Behavior: `repo` MUST be in the watched allowlist, otherwise `isError` with code `repo_not_allowed`. Fetches the PR, runs the same summary path as User Story 1 (no tool-server write unless `record: true`), and returns
```json
{"repo": "...", "pr_number": 12, "head_sha": "...", "summary": "...", "sources": [ ... ], "run_id": "uuid"}
```
Errors: `pr_not_found` (explicit error; never a fabricated summary), `repo_not_allowed`, `run_limit_exceeded`.

### `get_latest_digest`
Input: `{"repo": "owner/name"}`
Output: the most recent row from `digests` for that repo plus its entries, or `isError` `no_digest_yet`.

## Conformance checks
1. Unauthenticated connection refused.
2. `tools/list` returns both tools with schemas.
3. `summarize_pr` on a fixture PR returns a summary and creates an `agent_runs` row with kind `mcp_summarize`.
4. Non-allowlisted repo and unknown PR return errors, not summaries.
