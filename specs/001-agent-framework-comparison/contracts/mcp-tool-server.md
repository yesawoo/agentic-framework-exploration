# Contract: Reference MCP tool server

**Requirements**: FR-003, FR-004, FR-010 | Transport: MCP Streamable HTTP at `/mcp` | Auth: `Authorization: Bearer <token>` (static token from Secrets Manager; no interactive OAuth, because two of the four MCP clients do not run OAuth flows).

Implementation: Python, official `mcp` SDK (FastMCP). Every agent implementation MUST **discover** these tools via `tools/list` at run time (not hard-code schemas) and call them via `tools/call`. The server records each call in `toolserver.calls` (with MCP client name/version) for the MCP evaluation in the report.

All `record_*` tools are **idempotent**: repeating a call with the same natural key returns the existing record id with `duplicate: true` and does not create a second record.

## Tools

### `record_pr_summary`
Input:
```json
{
  "implementation": "langgraph | claude-agent-sdk | mastra | pydantic-ai",
  "repo": "owner/name",
  "pr_number": 12,
  "head_sha": "abc123",
  "title": "string",
  "author": "string",
  "summary": "plain-language description of what the PR accomplishes",
  "sources": [{"path": "src/a.py", "why": "defines the function being changed"}],
  "condensed": {"applied": false, "note": null}
}
```
Natural key: `(implementation, repo, pr_number, head_sha)`.
Output: `{"record_id": "uuid", "duplicate": false}`.
Errors (MCP `isError`): `invalid_argument` (missing/invalid fields), `unknown_implementation`.

### `record_review`
Input: same identity fields plus
```json
{
  "findings": [{"agent": "risk", "framework": "langgraph", "topic": "sql injection", "severity": "high", "evidence": "..."}],
  "missing_perspectives": ["tests"],
  "disagreements": [{"topic": "risk level", "positions": [{"agent": "risk", "view": "high"}, {"agent": "summarizer", "view": "low"}]}]
}
```
Natural key: `(implementation, repo, pr_number, head_sha)` for reviews. Output as above.

### `record_digest`
Input:
```json
{
  "implementation": "...", "repo": "owner/name", "digest_date": "2026-09-27",
  "issue_url": "https://github.com/owner/name/issues/40",
  "entries": [{"pr_number": 12, "title": "...", "author": "...", "status": "open|merged|closed", "url": "...", "summary": "..."}]
}
```
`entries` MAY be empty (digest is still published, per Assumption "Empty days"). Natural key: `(implementation, repo, digest_date)`.

### `list_records`
Input: `{"kind": "pr_summary|review|digest", "implementation": "optional", "repo": "optional", "since": "optional ISO datetime", "limit": 50}`
Output: `{"records": [ ... stored payloads with record_id, implementation, received_at ]}`. Read-only; used by the conformance suite and by agents that need previous records.

## Inspection view
`GET /records?kind=&implementation=&repo=` (bearer token) returns the same data as JSON for humans and the conformance harness. No UI beyond this in v1 (spec "Out of scope").

## Behavior the conformance suite checks
1. `tools/list` advertises exactly these four tools with JSON Schemas; a client that reads the schema builds valid calls.
2. Duplicate call -> `duplicate: true`, one stored row.
3. Missing/invalid bearer -> connection refused (401).
4. A tool that changes schema between runs (renamed field) is detected by the eval as a discovery failure, not silently mis-called (spec edge case: "tool server changes its advertised capabilities").
