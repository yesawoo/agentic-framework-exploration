# Contract: Work queue messages

**Requirements**: FR-010 (baseline), FR-011, FR-012 (queue-level), FR-013 (baseline) | Owner: spec 001 | One SQS standard queue + DLQ per implementation (created by `infra/implementations/<name>`).

Producers: the webhook handler, EventBridge Scheduler (schedules), and, from spec 002, the approval decision path. Consumer: the worker loop inside each implementation.

Scope: all six kinds are defined here so the contract is stable, but spec 001 registers handlers only for `pr_summary` and `digest`. A message of any other kind is acknowledged and recorded as `ignored` (metric `WorkItemsIgnored`), never retried and never sent to the DLQ, until the spec that owns it registers a handler (`pr_review`, `chat`, `approval_decision`, `approval_sweep`: spec 002).

## Message body (JSON)
```json
{
  "schema": 1,
  "work_item_id": "uuid",
  "kind": "pr_summary | pr_review | digest | chat | approval_sweep | approval_decision",
  "subject_key": "pr:owner/repo#12@abc123",
  "delivery_id": "GitHub delivery id or null",
  "params": {}
}
```

`params` by kind:
- `pr_summary` / `pr_review`: `{"repo": "...", "pr_number": 12, "head_sha": "..."}`
- `digest`: `{"repo": "...", "scheduled_time": "<ISO-8601 UTC>", "date": "YYYY-MM-DD"}`. EventBridge Scheduler input templates can only pass the scheduled time (`<aws.scheduler.scheduled-time>`), not compute a date, so scheduled messages omit `date` and the worker derives the previous calendar day from `scheduled_time` in `DIGEST_TIMEZONE`; `date` is set by manual triggers and conformance scenarios (`POST /internal/schedule`)
- `chat`: `{"repo": "...", "pr_number": 12, "comment_id": 1, "thread_id": "...", "command": "..."}`
- `approval_decision`: `{"approval_id": "uuid", "decision": "approve|reject", "decided_by": "login"}`
- `approval_sweep`: `{}` (expires pending requests older than 24 h)

## Semantics
1. **At-least-once delivery**; consumers MUST be idempotent on `(kind, subject_key)`, and the worker's first step is the `events` dedupe insert, retrying the database connection while a paused database resumes. A message whose work item is already `done` is deleted without effect. In spec 001 the dedupe key is `delivery_id` alone, valid only because `pr_summary` is the only kind created from a delivery; spec 002 defines a distinct key per kind and changes the worker.
2. **Retries**: visibility timeout 6x the p95 run time; `maxReceiveCount` 5, then DLQ. Transient model/GitHub/tool-server errors are retried inside the run with backoff first (FR-012); SQS redelivery covers process death (FR-013).
3. **Resume**: in spec 001 a redelivered message restarts its run safely (idempotent tool calls, message deleted only at a terminal status). Spec 002 adds resume from framework state (checkpoint, workflow snapshot, session) for `pr_review` where the framework supports it.
4. **Limits**: each run enforces `MAX_STEPS`, `MAX_RUN_SECONDS`, `MAX_RUN_COST_USD` from configuration (FR-016); breaching ends the run with status `limit_exceeded` and is not retried.
5. **Alerts**: DLQ depth > 0 and `failed` runs raise CloudWatch alarms (FR-020); `limit_exceeded` is an expected, recorded outcome (metric `RunsLimitExceeded`, no alarm).
