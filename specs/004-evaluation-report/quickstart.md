# Quickstart: Evaluation and Comparison Report

**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

This is an executable contract (Constitution VIII). It assumes the quickstarts of specs 001, 002, and 003 pass: the environment is deployed (`just up`), all four implementations are healthy, and the scenarios of the earlier specs you want evaluated have been run. It covers only what this spec adds. The `just` targets `eval`, `eval-all`, `report-check`, and `report-links` are created by tasks in `tasks.md`; until each exists, that step is not validated.

## A. Prerequisites and state check

Everything from spec 001 quickstart section 0 (credentials only via environment or profile). In addition the pinned judge model (Claude Opus 5.5 in `$BEDROCK_REGION`) must be enabled for the account.

```bash
just doctor                     # spec 001; must confirm the judge model is enabled
just status                     # tool server and all four implementations running
```

Expected: `doctor` exits 0; `status` lists five running components. The eval commands in section C need a deployed environment and spend on Bedrock; get owner approval before running them.

## B. Local contract check (no AWS, no model spend)

```bash
just up-local
just conformance-local          # includes shared/conformance/tests/test_us8_reports.py
just report-check               # validates any report JSON present against contracts/eval-report.schema.json
```

Expected: `test_us8_reports.py` passes for each implementation: report validates, delivery correctness present, per-run cost and duration retrievable via `/admin/runs`, limit-exceeded run records `limit_reason`. Record observed pass counts (Constitution VIII).

## C. Evaluate and compare (live tier)

```bash
just eval langgraph             # shared harness + the framework's native eval; writes shared/conformance/reports/langgraph/<ts>.json
just eval claude-agent-sdk
just eval mastra
just eval pydantic-ai
just eval-all                   # all deployed implementations (absent ones are reported, not skipped)
just report-check               # every report JSON validates; native_evals has all seven capabilities per framework
```

Expected: one schema-valid report per implementation in identical format, each recording the `git_sha` under test. Commit them with the SHA (T154).

Cost and duration of a single run (SC-009):

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" "$BASE_URL/<impl>/admin/runs/<run_id>"    # token read from Secrets Manager at run time, never written to a file
```

## D. Build and verify the report

```bash
just report-links               # every link in docs/report/ is a commit-pinned permalink whose path and line range resolve at that SHA
just report-check
```

Then follow the checks in `docs/report/verification.md` (T166): every framework/dimension cell filled (SC-010), seven evaluation capabilities for four frameworks (SC-021), Bedrock chapter covers all logged issues (SC-024), and a 10-claim spot check with at least 9 correct (SC-019).

## E. Final verification and teardown

Run by an actor other than the implementer, from a fresh clone or worktree (T416, T417):

1. Spec 001 quickstart sections 1-2 and the local checks of specs 002 and 003, recording commands and pass counts per implementation.
2. Spec 001 quickstart deployment sections and the live-scenario sections of specs 002 and 003, recording status codes and timings against SC-004, SC-022, SC-023.
3. Live agent engagement (T171) against the deployed environment.
4. Teardown:

```bash
just destroy-all                # also removes durable and edge layers, including the database (no final snapshot unless KEEP_FINAL_SNAPSHOT=1)
just verify-clean               # lists remaining tagged resources (project=agentic-framework-exploration); must be empty
```

Expected: `just verify-clean` exits 0 with no resources listed; a retained snapshot, if `KEEP_FINAL_SNAPSHOT=1` was used, is recorded as the declared exception (T418).

## Clean-state verification checklist (Constitution VIII)

Before reporting this spec complete, re-run from a fresh clone or worktree: section B in CI, and sections A, C, and E by an actor other than the implementer. Record the commands and observed output, including pass counts and status codes.
