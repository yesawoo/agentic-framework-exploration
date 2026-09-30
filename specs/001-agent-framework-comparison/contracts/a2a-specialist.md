# Contract: Cross-framework specialist over A2A

**Requirements**: FR-038, FR-039, FR-040 (User Story 14, P3) | Protocol: A2A (target v1.0 with v0.3 compatibility; Mastra supports both, see research S7).

Every implementation serves one A2A specialist, the **risk reviewer**, and can call another implementation's specialist from its coordinator when configured with `REMOTE_SPECIALISTS` (a list of `{name, url, token_secret}`).

## Agent card (served at `/.well-known/agent-card.json` under the implementation prefix)
```json
{
  "name": "pr-steward-risk-reviewer (<implementation>)",
  "description": "Reviews a pull request diff for security and correctness risk",
  "url": "https://<cloudfront>/<implementation>/a2a",
  "version": "1.0.0",
  "capabilities": {"streaming": false},
  "defaultInputModes": ["application/json"],
  "defaultOutputModes": ["application/json"],
  "skills": [{"id": "review_risk", "name": "Risk review", "description": "Security/correctness findings for a PR", "tags": ["review", "security"]}],
  "securitySchemes": {"bearer": {"type": "http", "scheme": "bearer"}}
}
```
Auth: bearer token per configured peer only (FR-039); unknown peers get 401.

## Task input (`review_risk`)
```json
{"repo": "owner/name", "pr_number": 12, "head_sha": "abc123", "diff_excerpt": "...", "correlation": {"run_id": "uuid", "parent_agent": "coordinator", "framework": "langgraph"}}
```
`diff_excerpt` is untrusted data; the specialist MUST apply the same injection defenses (FR-014).

## Task output (artifact)
```json
{"findings": [{"topic": "...", "severity": "info|low|medium|high", "evidence": "..."}], "confidence": "low|medium|high"}
```

## Coordinator behavior
- Each remote call is recorded as `delegation` and `delegation_result` steps with `framework` set to the remote's framework (FR-039).
- Timeout 30s (configurable). Unreachable, unauthorized, or protocol-mismatched remotes yield a labeled partial result (`missing_perspectives: ["risk"]`), never a failed review (FR-040).
- Loop guard: requests carry a hop count in `correlation`; a specialist refuses requests with hops >= 2 (spec edge case: mutual delegation loop).
- The core review (User Story 4) never depends on remotes; mixed mode is enabled only by configuration.
