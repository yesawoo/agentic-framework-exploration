# Contract: Environment variables

One naming scheme for every implementation, the tool server, the migrate task, compose, and the OpenTofu modules. Local and CI runs use dummy values only; real secrets come from AWS Secrets Manager injected into the ECS task definition (Constitution V), never from a file in the repository.

| Name | Used by | Source (AWS) | Local / CI | Notes |
|---|---|---|---|---|
| `IMPLEMENTATION` | implementations, tool server client | task definition | compose | `langgraph`, `claude-agent-sdk`, `pydantic-ai`, `mastra`; labels every record |
| `BASE_PATH` | implementations, tool server | task definition (`/<impl>`, `/toolserver`) | empty | Services serve all routes under this prefix; the ALB forwards the full path unchanged |
| `AWS_REGION` | all | task definition (`us-east-1` default) | `us-east-1` | |
| `BEDROCK_REGION` | implementations, judge | task definition (defaults to `AWS_REGION`) | `us-east-1` | |
| `BEDROCK_MODEL_AGENT` | implementations | task definition | stub id | Global inference profile for Sonnet 5.5 (pinned by S12) |
| `BEDROCK_MODEL_JUDGE` | conformance judge | operator shell | stub id | Global inference profile for Opus 5.5 |
| `BEDROCK_MODEL_HELPER` | implementations | task definition | stub id | Helper model (Haiku 4.5 or its replacement per S12) |
| `BEDROCK_ENDPOINT_URL` | implementations | unset on AWS | stub URL | Local/CI only; overrides the Bedrock Runtime endpoint |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | implementations | task role (never set) | `test` / `test` | Dummy values for the stub only |
| `GITHUB_API_URL` | implementations, conformance | unset (`https://api.github.com`) | stub URL | Points PyGithub/Octokit at `stub_github` locally |
| `GITHUB_TOKEN` | implementations | Secrets Manager | dummy | |
| `GITHUB_WEBHOOK_SECRET` | implementations | Secrets Manager | dummy | HMAC key for `X-Hub-Signature-256` |
| `ADMIN_TOKEN` | implementations | Secrets Manager | dummy | Bearer for `/admin/*`, `/internal/*`, agent MCP |
| `TOOLSERVER_URL` | implementations | task definition: the CloudFront URL plus `/toolserver` | compose URL | On AWS, service-to-service calls go through CloudFront (which adds the origin secret header), so the ALB's default 403 stays in force |
| `TOOLSERVER_TOKEN` | implementations, tool server | Secrets Manager | dummy | Bearer for the tool server |
| `DB_HOST`, `DB_PORT`, `DB_NAME` | implementations, tool server, migrate | task definition | compose | |
| `DB_SCHEMA` | implementations, tool server, migrate | task definition | compose | Per-implementation schema, or `toolserver` |
| `DB_USER`, `DB_PASSWORD` | implementations, tool server | Secrets Manager `db-role/<schema>`, JSON keys `username` (the role name, equal to the schema name) and `password`, injected with ECS `valueFrom` `<arn>:username::` and `<arn>:password::` | dummy (`DB_USER` = the schema name) | Least-privilege role per schema; the role owns its schema |
| `MIGRATE_MODE` | migrate task only | task definition (`aws`) | `local` | `aws`: master credentials from `DB_MASTER_SECRET_ARN`, role password written to `DB_ROLE_SECRET_ARN`. `local`: no AWS calls; master credentials from `DB_MASTER_USER`/`DB_MASTER_PASSWORD`, role password from `DB_ROLE_PASSWORD`. On AWS one migrate task definition serves every schema: `DB_SCHEMA`, `DB_ROLE_SECRET_ARN`, and `--reset` are run-task overrides, and subnets and the security group come from `infra/durable` outputs |
| `DB_MASTER_SECRET_ARN` | migrate task only (`aws`) | Aurora-managed master secret | n/a | Used to create the schema, role, and `vector` extension; never given to an implementation |
| `DB_ROLE_SECRET_ARN` | migrate task only (`aws`) | `db-role/<schema>` secret created in `infra/durable` | n/a | JSON `{"username": "<schema>", "password": "..."}`. Migrate generates the password only when the secret has no value and never rotates an existing one (`--rotate` is explicit and must be followed by a service redeploy); the service reads it as `DB_USER`/`DB_PASSWORD` |
| `DB_MASTER_USER`, `DB_MASTER_PASSWORD`, `DB_ROLE_PASSWORD` | migrate task only (`local`) | n/a | dummy | Local and CI only |
| `QUEUE_URL` | implementations | task definition | ElasticMQ URL | Work queue; the DLQ is configured on the queue |
| `WATCHED_REPO` | implementations, conformance | task definition | compose | Allowlist of one repo |
| `OWNER_LOGIN` | implementations | task definition | compose | Only user allowed to command or approve |
| `DIGEST_TIMEZONE` | implementations | task definition | `America/Los_Angeles` | IANA name; one documented timezone (FR-005) |
| `MAX_STEPS`, `MAX_RUN_SECONDS`, `MAX_RUN_COST_USD` | implementations | task definition | compose | Per-run limits (FR-016) |
| `REMOTE_SPECIALISTS` | implementations | task definition | unset | JSON list of `{name, url, token_secret}` (US14); on AWS each `url` is the peer's CloudFront URL plus `/<impl>` |
| `METRICS_NAMESPACE` | implementations, tool server | task definition | `AgenticFrameworkExploration` | See observability.md |

## Framework-native variables and mapping

The names above are the contract. Frameworks and SDKs read their own names, which each implementation derives from the contract names at startup (tasks set both where a task definition can):

| Framework-native name | Set from | Used by |
|---|---|---|
| `AWS_REGION` | `BEDROCK_REGION` for the process that calls Bedrock (the two are equal by default) | boto3, `langchain-aws`, `@ai-sdk/amazon-bedrock`, Claude Agent SDK |
| `AWS_ENDPOINT_URL_BEDROCK_RUNTIME` | `BEDROCK_ENDPOINT_URL` (local and CI only) | boto3-based clients |
| `ANTHROPIC_BEDROCK_BASE_URL` | `BEDROCK_ENDPOINT_URL` (local and CI only) | Claude Agent SDK bundled binary |
| `CLAUDE_CODE_USE_BEDROCK` | fixed `1` | Claude Agent SDK |
| `ANTHROPIC_DEFAULT_SONNET_MODEL`, `ANTHROPIC_DEFAULT_OPUS_MODEL`, `ANTHROPIC_DEFAULT_HAIKU_MODEL` | `BEDROCK_MODEL_AGENT`, `BEDROCK_MODEL_JUDGE`, `BEDROCK_MODEL_HELPER` | Claude Agent SDK |
| `PORT` | `4111` for Mastra, `8000` for the Python services | container port and target group |

The conformance harness reads `TARGET_BASE_URL` (the implementation's base URL including `BASE_PATH`), `ADMIN_TOKEN`, `TOOLSERVER_TOKEN`, and `GITHUB_WEBHOOK_SECRET` (to sign test webhooks).
