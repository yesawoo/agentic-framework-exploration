# Quickstart: Core PR Steward (spec 001)

**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

This is an executable contract (Constitution: Development Workflow, Principle VIII). It MUST be runnable top to bottom from a fresh checkout. The `just` targets below are **planned**; they do not exist yet and are created by the tasks in `tasks.md`. Until each target exists, that step is not validated.

This quickstart covers spec 001 only (PR summary, hosting and spin-up/down, daily digest). Later specs write their own quickstart that starts with "assumes the 001 quickstart passes" and covers only their additions. Section numbers are the original ones; section 6 (evaluate and compare) belongs to spec 004.

Expected wall-clock targets: fresh checkout to one healthy deployed implementation in under 30 minutes; full teardown in under 10 minutes (SC-004).

## 0. Prerequisites (owner supplies)

Tools: `just`, `uv`, Node 22 LTS with `npm`, `tofu` (OpenTofu), `docker`, `sops` + `age`, `gh`, AWS CLI v2.

Credentials, provided **only through the environment or a profile**, never written to the repo:

```bash
export AWS_PROFILE=<sandbox-profile>          # or AWS_ACCESS_KEY_ID/SECRET/SESSION_TOKEN
export AWS_REGION=us-east-1                    # default; infra and Bedrock share one region (research D6a). Override both together to move
export GITHUB_TOKEN=<fine-grained PAT, contents:read, pull_requests:read+write, issues:write on the TEST repo only>
export BEDROCK_REGION=${AWS_REGION}          # default us-east-1; must be a region where the pinned Claude models are enabled for your account (no model API key is used)
export WATCHED_REPO=<owner>/<test-repo>       # allowlist of one repo
export OWNER_LOGIN=<your-github-login>        # only user allowed to command/approve
```

The webhook secret, admin token, and tool-server token are not exported by hand: `just secrets-load` generates any that are missing (random, 32 bytes) into Secrets Manager and never regenerates an existing value. `smoke`, `webhook-register`, and the conformance harness read them live from Secrets Manager into the process only, never into a file.

## 1. Clean-state setup

```bash
git clone https://github.com/yesawoo/agentic-framework-exploration.git && cd agentic-framework-exploration
git checkout 001-agent-framework-comparison
just setup            # uv sync --frozen (Python components), npm ci (Mastra), docker pull, tofu init
just doctor           # verifies tools, versions, and that AWS/GitHub credentials are valid and the pinned Bedrock models are enabled in $BEDROCK_REGION (read-only calls)
```

Expected: `just doctor` prints one line per check and exits 0.

## 2. Local contract check (no AWS, no model spend)

```bash
just up-local         # docker compose: Postgres, ElasticMQ, migrate one-shot, stub GitHub API, stub Bedrock Runtime endpoint, tool server, all 4 implementations
just conformance-local
```

Expected: contract-tier suite passes for each implementation: health 200, forged webhook 401, redelivered webhook processed once, PR summary recorded once on the tool server, digest published once, tool-server records well-formed, `/admin/runs` matches `contracts/`. Record the observed pass counts in the PR (Constitution VIII).

## 2b. The short version: spin up and down

Once section 1 is done, the whole environment is five commands. Sections 3 and 4 below are the same thing done one component at a time.

```bash
just bootstrap                 # once per AWS account: durable + edge layers (state bucket, ECR, secrets, VPC, Aurora database, budget alarm, CloudFront with a stable URL)
just secrets-load              # once, or after rotating keys (reads from env; nothing written to disk)
just up                        # everything; or: just up langgraph mastra
just status                    # running/paused/absent per component, uptime, estimated $/day
just pause                     # stop implementation compute (the database pauses itself when idle); `just resume` brings it back in minutes
just down                      # take everything runtime down; the database and its data stay (durable layer) and pause themselves; FRESH=1 just up starts with empty schemas
```

Optional guard against forgetting: `MAX_UPTIME_HOURS=8 just up` schedules an automatic pause. `just destroy-all` followed by `just verify-clean` removes even the durable and edge layers, including the database.

## 3. Deploy shared infrastructure and the tool server

```bash
just bootstrap        # one-time: durable and edge layers (own OpenTofu roots)
just plan shared      # REVIEW this output before applying (Constitution IV)
just deploy shared    # ECS cluster, ALB, security groups, log groups; then repoints the edge (CloudFront) origin at the new ALB (no image, no migrate)
just secrets-load     # writes GITHUB_TOKEN, webhook secret, ADMIN_TOKEN into Secrets Manager (from env; nothing written to disk)
just deploy tool-server   # runs the migrate task for the toolserver schema, then applies the service
just smoke tool-server
```

Expected: `just smoke tool-server` records `GET /health` -> 200, `tools/list` -> 4 tools, unauthenticated `/mcp` -> 401.

## 4. Deploy one implementation

```bash
just plan langgraph
just deploy langgraph      # builds image, pushes to ECR, runs the migrate task for its schema, applies its own state, waits for health check
just smoke langgraph
just webhook-register langgraph   # registers the GitHub webhook on $WATCHED_REPO pointing at the CloudFront URL
```

`just smoke <impl>` records status codes for: `/health` (200), forged webhook (401), valid `ping` (200), `POST /internal/schedule` digest for a seeded date (202), `/admin/runs` (200 with bearer, 401 without).

Repeat with `claude-agent-sdk`, `mastra`, `pydantic-ai` (each is independent).

## 5. User story validations (live tier)

Each scenario has a `just` target that drives it and asserts the outcome; the number in parentheses is the spec story. Live scenarios open real PRs on `$WATCHED_REPO` and spend Bedrock tokens (owner approval).

```bash
just scenario langgraph pr-summary      # (US1) opens a fixture PR on $WATCHED_REPO; asserts one tool-server record within 2 min
just scenario langgraph digest          # (US3) seeds PRs dated yesterday; triggers digest; asserts the GitHub issue + tool-server record; reruns and asserts no duplicate
just scenario langgraph deploy-smoke    # (US2) URL reachable, only the addressed implementation reacts, teardown of one leaves the others healthy
```

Scenarios for later stories (`multi-agent`, `safety`, `approval`, `chat`, `context-memory`, `mcp-server`, `tools`, `a2a-mixed`, `sandbox`) are added by specs 002 and 003.

## 6. Evaluate and compare

Not part of this spec: `just eval`, `just eval-all`, `just report-check`, and `just report-links` are delivered by spec 004.

## 7. Teardown

```bash
just destroy langgraph                  # removes that implementation only; others unaffected
just destroy tool-server
just destroy shared                     # runtime layer only; the database and CloudFront stay
# or all of the above in order: just down
just destroy-all                        # also removes the durable and edge layers, including the database (no final snapshot unless KEEP_FINAL_SNAPSHOT=1); succeeds even with images in ECR and objects in the artifacts bucket
just verify-clean                       # lists any remaining tagged resources (project=agentic-framework-exploration); must be empty
```

Expected: `just verify-clean` exits 0 with no resources listed (SC-004).

## Clean-state verification checklist (Constitution VIII)

Before reporting this spec complete, re-run from a fresh clone or worktree: sections 1 -> 2 in CI, and 3 -> 5 and 7 by an actor other than the implementer. Record the commands and the observed output, including status codes from each `just smoke`.
