# Contract: Logs and metrics (Constitution VI)

Every implementation and the tool server emit the same structured logs and CloudWatch EMF metrics so alarms and the report compare like with like.

## Logs

JSON, one object per line, stdout to CloudWatch Logs. Required fields: `ts`, `level`, `implementation`, `msg`. Include when known: `run_id`, `delivery_id`, `work_item_id`, `agent`, `tool`, `outcome`, `duration_ms`. Secrets and full payloads are redacted by the emitting code.

## Metrics

Namespace `AgenticFrameworkExploration` (`METRICS_NAMESPACE`). EMF dimension sets: request metrics emit both `[Implementation]` and `[Implementation, Route]` so alarms can use the short set; run metrics and `DigestPublished` use `[Implementation]`; `ToolCalls` uses `[Implementation, Tool]`. The tool server's `Implementation` value is `toolserver`.

| Metric | Unit | Emitted by | Alarm |
|---|---|---|---|
| `HttpRequests` | Count | webhook and admin routes | no |
| `Http5xx` | Count | webhook and admin routes | yes: 5xx rate |
| `HttpLatencyMs` | Milliseconds | webhook and admin routes | no |
| `RunsSucceeded` | Count | worker | no |
| `RunsFailed` | Count | worker | yes: failed runs |
| `RunsLimitExceeded` | Count | worker | no |
| `RunDurationMs` | Milliseconds | worker | no |
| `DigestPublished` | Count | digest handler | yes: missing-data alarm (no digest published in the expected window) |
| `WorkItemsIgnored` | Count | worker | no |

The DLQ-depth alarm uses the SQS `ApproximateNumberOfMessagesVisible` metric. Tool-server metrics: `HttpRequests`, `Http5xx`, `HttpLatencyMs`, `ToolCalls` (dimension `Tool`), with a 5xx alarm.
