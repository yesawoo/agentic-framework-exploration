# Agentic Framework Exploration Constitution

## Core Principles

### I. Test Discipline (NON-NEGOTIABLE)

All test failures MUST be fixed, regardless of whether they are related to the current
change. A contributor MUST NOT hand back a PR with known-failing tests and MUST NOT
dismiss failures as "pre-existing" or "someone else's problem."

- Every CI pipeline MUST be green before merge.
- A failing test discovered during work on an unrelated feature MUST be fixed before
  or alongside that feature — not deferred.
- Test suites MUST be run before committing (`uv run pytest`, the TypeScript test
  runner, etc.).
- Linting and type checks (`uv run ruff check`, `tsc --noEmit`) MUST pass; pre-commit
  hooks, where configured, MUST NOT be bypassed.
- A reported test or validation result from one actor is a claim, not evidence.
  Before merge, it MUST be reproduced by an independent actor — CI, or a second
  session/person starting from a fresh clone or worktree of the branch — with
  no shared process state. The reproducing actor MUST NOT reuse the
  implementer's database, server, or shell (see Principle VIII).

**Rationale**: A single tolerated failure normalizes a culture of ignoring failures.
Selective test-fixing leads to CI rot and silent regressions. Self-reported
validation is only as trustworthy as the state it ran against; requiring an
independent reproduction closes the gap between "the implementer says it
passed" and "it actually works for anyone else."

### II. Scripted, Reproducible Deployment

Every deployable component MUST be deployable and tearable-down through documented
`just` targets (for example `just deploy <implementation>` and
`just destroy <implementation>`). Those targets are the only sanctioned way to change
deployed state, and they MUST behave identically whether run locally with sandbox
credentials or from CI.

- `main` MUST be the default/root branch; `master` MUST NOT be used.
- Deploy targets MUST NOT depend on undocumented local state (a shell with
  accumulated environment, a hand-edited file, a console click).
- Every deployable component MUST expose a health check that a deploy target verifies
  before reporting success.
- Every deployable component MUST be independently deployable and removable so that the
  four framework implementations can be compared side by side without coupling.
- Teardown MUST remove everything a deploy created; leftover billable resources are a
  defect.

**Rationale**: This repo compares four implementations of one agent; if any of them
deploys by a different or undocumented route, the deployment-effort comparison is
meaningless. Scripted targets keep the audit trail in version control. This is
deliberately lighter than glitch's "merge to main deploys to production" rule: the
project is a sandbox with owner-supplied credentials, not a production service. A
CI-triggered deploy MAY be added later without violating this principle.

### III. Repository Conventions

Each implementation directory and each shared component (infrastructure, reference tool
server, conformance/evaluation suite) MUST maintain its own `CLAUDE.md` documenting
architecture, commands, and constraints. Cross-component work MUST consult the relevant
`CLAUDE.md` before making changes.

- The repository root `CLAUDE.md` governs global policies that override component-level
  guidance when they conflict.
- Documentation MUST live under `docs/` — not at component or repo root (`README.md`,
  `CLAUDE.md`, and files under `specs/` excepted).
- Temp files MUST use `$TMPDIR`, never `/tmp` or `tmp/`.

**Rationale**: With four parallel implementations, undocumented per-implementation
conventions become invisible to anyone working across them, and the friction that a
convention hides is precisely what this repo exists to measure.

### IV. Infrastructure as Code

All infrastructure changes MUST be expressed in code (OpenTofu) and reviewed before
apply. Ad-hoc console/CLI changes to deployed infrastructure are prohibited.

- Infrastructure uses `tofu` (OpenTofu), not `terraform`.
- `tofu plan` output MUST be reviewed before `tofu apply`.
- Shared infrastructure and per-implementation infrastructure MUST be separate
  configurations/state so one implementation can be applied or destroyed without
  touching the others.
- A resource created outside OpenTofu and later needed MUST be imported or recreated
  under OpenTofu, not left as an unmanaged dependency.

**Rationale**: Untracked infrastructure changes are invisible, cannot be reviewed, and
cannot be reproduced. IaC is the audit trail for deployed state, and separate state per
implementation is what makes side-by-side deployment and clean teardown possible.

### V. Security by Default

Secrets MUST be stored and transmitted encrypted. Plaintext credential files MUST
NOT be committed or left on disk.

- Secrets stored in the repository MUST use SOPS + age encryption.
- SOPS-encrypted files MUST NOT be decrypted to a temp file then re-encrypted;
  edits MUST use SOPS's interactive edit.
- Runtime secrets (GitHub webhook secret, GitHub token, model API key) MUST live in an
  AWS-managed encrypted secret store provisioned by OpenTofu and MUST be injected at
  runtime, never baked into images, source, or logs.
- A secret that originates in OpenTofu state MUST be read live from Tofu output when
  another tool needs it, and MUST NOT be copied into a SOPS-encrypted file.
- Cloud credentials supplied by the owner MUST be used only through the environment or
  a credentials profile and MUST NOT be written into any file in the repository.
- Before referencing a secret, verify it exists; if a secrets file is empty or
  corrupted, restore from git — never recreate it manually.

**Rationale**: A single committed plaintext secret can compromise every system it
accesses, and this repo handles real cloud credentials and a public webhook endpoint.
A Tofu-originated credential copied elsewhere creates a second source of truth that
silently drifts on rotation.

### VI. Observability by Default

Any deployed service MUST emit structured logs, expose metrics, and have baseline
alerting configured before it is considered production-ready. Observability MUST land
with (or before) the feature that needs it, not be deferred to a later ticket.

- Logs MUST be structured (JSON or key=value fields), not free-form interpolated
  strings, and MUST include enough context (run id, delivery id, agent, tool) to trace
  a single operation without grepping application source.
- Logs MUST NOT contain secrets or full PII payloads (see Principle V); redaction is
  the responsibility of the emitting code, not the log pipeline.
- Logs MUST ship to a retained, searchable store on the deployment platform rather than
  being left only in container stdout.
- A service that exposes HTTP endpoints or background jobs MUST emit metrics (request
  rate/latency/errors, job success/failure/duration at minimum).
- Every metric-emitting service MUST have at least one alert covering its primary
  failure mode (error-rate spike, failed run, scheduled job not run).
- Each component's `CLAUDE.md` (Principle III) MUST document what it logs, what it
  emits, and where its alerts live.

**Rationale**: A service with no logs or metrics is undebuggable, and metrics with no
alerting are silently ignored. For this repo observability is also a comparison
dimension, so every implementation must produce comparable telemetry.

### VII. Prefer Maintained Client Libraries

When integrating with a third-party API, the project MUST default to the vendor's
official or a well-maintained community client library rather than hand-rolling an HTTP
client against the raw REST/GraphQL surface. A hand-rolled client is an explicit,
justified exception — not the default starting point.

- Hand-rolling a client MUST be justified by a specific, documented reason: the library
  does not support the required auth mode, is unmaintained/abandoned, or its dependency
  footprint is disproportionate to the handful of calls needed. "We didn't want a
  dependency" is not, by itself, a sufficient reason.
- The justification MUST be documented where a future maintainer will find it before
  touching the code — a comment on the client, `research.md`, or the component's
  `CLAUDE.md`.
- A hand-rolled client MUST construct request URLs explicitly rather than relying on
  base-URL + relative-path joining, and MUST have an integration test exercising the
  real (or recorded) request path, not just mocked unit tests.
- MCP servers and clients MUST use the official MCP SDK for the implementation
  language unless a framework under evaluation supplies its own MCP integration, in
  which case that integration is used and its behavior is recorded in the scorecard.

**Rationale**: Request construction, auth/token refresh, retry-with-backoff,
rate-limit handling, pagination, and error taxonomy are all things a maintained SDK has
usually already gotten right and a hand-rolled client will rediscover one incident at a
time. Requiring an explicit justification converts an invisible choice into one that
gets reviewed.

### VIII. Verification from a Clean State (NON-NEGOTIABLE)

A feature is not "done" until it has been verified from a state a fresh checkout would
produce. Verification performed against the implementer's long-running process state —
a warmed server, an already-populated datastore, a shell with accumulated environment —
proves nothing about the branch and MUST NOT be reported as a passing validation.

- Before reporting completion, the implementer MUST tear down and rebuild: stop any
  running process, reinstall dependencies from the lockfile (`uv sync --frozen`,
  `npm ci`), and bring any datastore or deployed environment up from scratch on the
  branch as checked out. Verification MUST then be performed against that rebuilt state
  with freshly started processes.
- A component exposing HTTP endpoints MUST have its clean-state run include a smoke
  check of its health endpoint plus at least one endpoint per user story, with observed
  status codes recorded.
- Pending schema or state migrations, where a datastore is used, are a completion
  blocker.
- Completion reports MUST state the commands run and their observed output. A claim of
  the form "validated end-to-end" without the reproducible command sequence is not a
  validation result and MUST be treated by reviewers as unverified.
- An agent or contributor MUST NOT report status ("running", "in progress",
  "validated", "deployed") that is not backed by an action already taken. Asserting
  progress in place of performing it is the same defect as reporting unreproduced test
  results.

**Rationale**: Reproducibility failures are invisible to the implementer, because the
implementer's own session reports everything passing. Fresh worktrees, CI runners, and
reviewers' machines all start from zero; validation that only ever runs against warmed
state tests the wrong thing.

### IX. CI Before Completion for New Components

A Spec Kit feature that creates a new implementation or shared component MUST land that
component's CI workflow (`.github/workflows/<component>-ci.yml`, running its tests and
linters on push and PR) in the same branch as its first implementation. That workflow
MUST have completed at least one green run on the feature branch before the feature is
reported complete or its PR is marked ready.

- A new component's CI workflow MUST exercise setup from scratch (dependency install and
  datastore creation on a clean runner), not merely run tests against pre-existing
  state.
- A feature MUST NOT be reported complete on the basis of locally-run tests alone when
  no CI run exists for the code under test.
- A test/lint-only workflow is an acceptable first step; absence of CI entirely is a
  blocking gap per Principle I, not a follow-up ticket.
- The shared conformance suite MUST run in CI against every implementation that exists
  on the branch.

**Rationale**: CI is the only actor that naturally runs from a clean state on every push,
which is what Principle VIII's verification requires and what an implementer's own
session cannot provide. Without a CI workflow, Principle I's "every CI pipeline MUST be
green" has nothing to bind to.

## Technology Standards

This section records the canonical technology choices for the repository. Deviations
require an explicit justification documented in the affected component's `CLAUDE.md`.

| Concern | Standard |
|---------|----------|
| Cloud | AWS |
| Infrastructure | OpenTofu (`tofu`) — NOT `terraform` |
| Python runtime | Python 3.13; packaging via `uv` + `pyproject.toml` (LangGraph, Claude Agent SDK, Pydantic AI implementations as applicable) |
| Python linting | `ruff` (select E, F, I minimum); `uv run ruff check` |
| TypeScript | Node.js LTS; `tsc` strict mode (Mastra implementation, and any TypeScript component) |
| Task runner | `just` |
| Secrets | SOPS + age in-repo; AWS-managed encrypted secret store at runtime |
| Tool protocol | MCP, via the official SDK for the implementation language |
| Model family | Claude, for all implementations, so framework differences are not model differences |
| CI | GitHub Actions |

## Development Workflow

### Branch Strategy

- The default/root branch MUST be named `main`, never `master`.
- Feature work MUST be done on a named branch (`###-short-description`).
- Force-push to `main` is prohibited.

### Pull Requests

- All PRs MUST have a passing CI run before merge.
- PRs MUST NOT be merged with known-failing tests (see Principle I).
- PR descriptions MUST explain *why*, not just *what*; commit messages follow the same
  rule.
- Spec Kit features (`/speckit-*`) MUST have a spec under `specs/` before implementation
  begins.

### Code Quality Gates

- `uv run pytest` and `uv run ruff check` (Python) MUST pass in CI.
- The TypeScript test runner and `tsc --noEmit` MUST pass in CI for TypeScript
  components.
- No comments describing *what* code does — only *why* when non-obvious.
- No abstractions added beyond what the current task requires (YAGNI). Implementations
  MUST NOT share agent logic across frameworks beyond the shared contract, fixtures, and
  tool server; sharing framework-specific code would defeat the comparison.
- A feature's `quickstart.md` is an executable contract, not prose. It MUST begin with
  the clean-state setup commands required to reach a working system from a fresh
  checkout (dependency install, datastore creation, deploy, health check) and MUST be
  runnable top-to-bottom by someone who has never run the project. "Validated
  quickstart" means those commands were executed in that order from a clean state — see
  Principle VIII.

## Governance

This constitution supersedes all other development guidelines. Where a component-level
`CLAUDE.md` conflicts with this document, this constitution governs.

**Amendment procedure**:
1. Open a PR that modifies this file.
2. Update `LAST_AMENDED_DATE` and increment `CONSTITUTION_VERSION` following
   semantic versioning (MAJOR: principle removal/redefinition; MINOR: new principle
   or section; PATCH: clarification/wording).
3. Update dependent templates under `.specify/templates/` if affected.
4. PR description MUST include a one-line rationale for each changed principle.

**Compliance**: All PR reviews MUST verify that changes comply with Principles I–IX.
Complexity violations MUST be documented in `plan.md`'s Complexity Tracking table
with a justification. Use `CLAUDE.md` (root and component-level) for runtime
development guidance.

**Version**: 1.0.0 | **Ratified**: 2026-09-28 | **Last Amended**: 2026-09-28
