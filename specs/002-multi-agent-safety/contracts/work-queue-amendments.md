# Contract amendments: Work queue messages (spec 002)

**Extends**: `specs/001-core-pr-steward/contracts/work-queue.md` (envelope, retry, resume, limits, and alert semantics stay as there). **Requirements**: FR-010, FR-012, FR-013, FR-016 | Introduced by: research D5a.

This file states only what changes or is newly defined. Where the base contract and this file disagree, this file wins for the items below, and Phase 0 (T203, T205) reconciles it against what spec 001 built.

## 1. Dedupe key is per work-item kind (research D5a)

Base contract, semantics item 1: "the worker's first step is the `events` dedupe insert". Amended: the insert key is `(delivery_id, kind)`. One GitHub delivery may yield several work items (a `pull_request` delivery yields one `pr_summary` and one `pr_review`); each is processed at most once, and a redelivery of the delivery drops each message whose `(delivery_id, kind)` already exists. A message whose work item is already `done` is still deleted without effect. Schema change: [data-model.md](../data-model.md), migration `0003`.

## 2. `params` and `subject_key` by kind

| Kind | `params` | `subject_key` | Notes |
|---|---|---|---|
| `pr_summary` | `{"repo", "pr_number", "head_sha"}` | `pr:owner/repo#12@<head_sha>` | unchanged from 001 |
| `pr_review` | `{"repo", "pr_number", "head_sha"}` | `pr:owner/repo#12@<head_sha>` | same params and key form as `pr_summary`; distinct because uniqueness is on `(kind, subject_key)`. Resume rule (base semantics item 3) applies |
| `chat` | `{"repo", "pr_number", "comment_id", "thread_id", "command"}` | `chat:owner/repo#12/comment:<comment_id>` (proposed) | one work item per command comment |
| `approval_decision` | `{"approval_id", "decision": "approve\|reject", "decided_by"}` | `approval:<approval_id>:<decision>` (proposed) | applied only when `decided_by` equals `OWNER_LOGIN`; a second decision on a decided request is recorded and ignored |
| `approval_sweep` | `{}` | `approval_sweep:<scheduled_time>` (proposed) | expires `pending` requests whose `expires_at` has passed (24 hours after creation) |

The base contract defines `params` for all kinds but a `subject_key` form only for summaries and digests. The three "proposed" forms are the minimum needed for at-most-once processing of the new kinds; if spec 001 shipped different forms, the as-built forms win and this table is updated in Phase 0.

## 3. Handler registration

Base contract behavior (spec 001 T040-T043): a kind with no registered handler is acknowledged and recorded `ignored`. This spec registers handlers for `pr_review`, `chat`, `approval_decision`, and `approval_sweep` in each implementation's single handler registry (`worker.py` / `worker.ts`). After registration none of these kinds may be recorded `ignored` except a `chat` command from a non-owner or an `approval_decision` from a non-owner, which are recorded `ignored` on purpose (User Story 7 scenario 3, User Story 6).

## 4. Limits and waiting state

- A run that breaches `MAX_STEPS`, `MAX_RUN_SECONDS`, or `MAX_RUN_COST_USD` ends `limit_exceeded` and is not retried (base semantics item 4); this now includes multi-agent reviews, where the limits apply to the coordinator run as a whole, specialists included.
- A run awaiting an approval decision has status `waiting_approval`, is not counted as failed, is not redelivered as a fresh run, and is neither retried nor swept as `abandoned` before its `expires_at`. The decision arrives as a separate `approval_decision` work item that resumes the run (research D10); how the original `pr_review` message is acknowledged while the run waits is per framework mechanism (T100-T103) and must not lead to a fresh duplicate review.
