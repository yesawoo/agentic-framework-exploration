# Quickstart: Multi-Agent and Safe Interaction

**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Predecessor**: [../001-core-pr-steward/quickstart.md](../001-core-pr-steward/quickstart.md)

**Assumes the spec 001 quickstart passes.** That means: prerequisites and credentials (section 0 there), clean-state setup, the local contract check, and, for the live steps below, at least one implementation deployed and healthy via `just up` or `just deploy <impl>` with `just smoke <impl>` passing. This file covers only what this spec adds. It MUST be runnable top to bottom from a fresh checkout after 001's steps. The `just` targets and scenarios named here are planned and are created by the tasks in `tasks.md`; until a scenario exists that step is not validated.

Expected wall-clock: the additions add no new provisioning time. `just deploy <impl>` re-runs the migrate task, which now applies migration `0003`.

## 1. Reconciliation gate (Phase 0)

Before the first task of Phase 1, `specs/002-multi-agent-safety/reconciliation.md` exists with all four headings filled, every Deviation has a change made or an open question, and `/speckit-analyze` on this spec is clean or its findings are documented.

## 2. Local contract check (no AWS, no model spend)

```bash
just setup                # as in spec 001
just up-local             # compose: Postgres (migrate applies 0001, 0002, 0003), ElasticMQ, stubs, tool server, all 4 implementations
just conformance-local    # includes the tests added by this spec
```

Expected: the contract tier passes for each implementation, including:
- `test_us5_dedupe_per_kind.py`: one signed `pull_request.opened` delivery yields one `pr_summary` and one `pr_review` work item, both processed; a redelivery processes neither again.
- `test_us4_multiagent.py`: findings from each specialist, `missing_perspectives` when one specialist is forced to fail, a `disagreements` entry for conflicting specialists, ordered `delegation`/`delegation_result` steps in `GET /admin/runs/{id}`, `record_review` stored once.
- `test_us5_reliability.py`, `test_us5_safety.py`: forged signature 401, same delivery twice processed once, retry with backoff on `rate_limit`/`fail_once`, tool-server unavailable then recovered, worker killed mid-run resumes or safely retries, `limit_exceeded` not retried, injection and secret fixtures leak nothing.
- `test_us6_approval.py`: pending until `/approve <id>` from the owner, exactly one comment, rejection and expiry post nothing, non-owner ignored.
- `test_us7_chat.py`: `progress`/`delta`/`final` SSE events with `run_id`, follow-up uses thread context, non-owner ignored, streamed comment edited at most every 2 seconds.

Record the observed pass counts in the PR (Constitution VIII). Migration check: `just conformance-local` (or `shared/db` tests) shows `reviews`, `findings`, `approval_requests` in each implementation schema and `events` keyed on `(delivery_id, kind)`.

## 3. Deploy the additions (⚠ needs owner approval: AWS spend)

```bash
just plan langgraph      # review before applying (Constitution IV); expect no infrastructure change beyond the migrate image tag
just deploy langgraph    # rebuilds and pushes the migrate image (shared/db source changed), runs the migrate task (applies 0003), then applies the service and waits for health
just smoke langgraph     # same checks as spec 001
```

Repeat for `claude-agent-sdk`, `mastra`, `pydantic-ai`. Expected: the migrate task exits 0 and the deployed schema holds the new tables, with earlier data (if any) intact.

## 4. Scenario validations (live tier; ⚠ GitHub writes and Bedrock spend need owner approval)

The number in parentheses is the spec story.

```bash
just scenario langgraph multi-agent     # (US4) risky PR with no tests; asserts findings from each specialist and the delegation trace via /admin/runs/{id}; forced specialist failure yields a labeled partial review
just scenario langgraph safety          # (US5) forged webhook, duplicate delivery (per kind), injection PR, secret-in-diff PR, tool-server outage
just scenario langgraph approval        # (US6) proposed comment is pending until /approve; reject and expiry leave the PR untouched
just scenario langgraph chat            # (US7) @steward command streams progress; follow-up uses context; non-owner ignored
```

Repeat for the other three implementations. The `chat` scenario, together with `shared/conformance/tests/test_us7_sse_through_edge.py` (T105, run with `--tier live` against the CloudFront URL), also checks that SSE survives CloudFront and the ALB (spec 001 risk R9).

Expected: each scenario prints pass or a recorded failure; every run is readable at `GET <cloudfront>/<impl>/admin/runs/{id}` with steps, tokens, and cost.

## 5. Teardown

This spec adds no infrastructure. Return the environment to the state you found it in (`just pause` or `just down`; `just destroy-all` and `just verify-clean` are run by spec 004's final verification, not here).

## Clean-state verification checklist (Constitution VIII)

Before reporting this spec complete, re-run from a fresh clone or worktree: section 2 in CI, and sections 3-4 by an actor other than the implementer. Record the commands and the observed output, including status codes from each `just smoke` and the pass counts from `just conformance-local`.
