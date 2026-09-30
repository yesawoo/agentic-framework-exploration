# Contract: Environment variable additions

**Spec**: 003-extended-capabilities | **Extends**: spec 001 `contracts/environment.md` (the base naming scheme; same columns and rules). Nothing here renames or overrides a base name. Names are added to spec 001's file only if Phase 0 shows that file is the single place every component reads from; otherwise this file stays the source for these names.

| Name | Read by | Source on AWS | Local default | Notes |
|---|---|---|---|---|
| `CONTEXT_TOKEN_THRESHOLD` | implementations | task definition | small value for the stub | Input size above which condensing or splitting starts (FR-041); model-window based on AWS, small locally so `oversized-diff` triggers it |
| `MEMORY_MAX_FACTS` | implementations | task definition | `200` | Cap on active facts; least-recently-used facts are evicted (FR-045, research D12) |
| `TOOL_GRANTS_FILE` | implementations | baked into the image, path in task definition | `config/tool_grants.yaml` | Tool grants (`tool_name`, `policy`, `load_mode`, `group`) loaded at startup (FR-034, FR-035) |
| `REMOTE_SPECIALISTS` | implementations | task definition | unset | Defined in spec 001 `contracts/environment.md`: JSON list of `{name, url, token_secret}`. `token_secret` is the name of a Secrets Manager entry holding the bearer this implementation presents to that peer |
| `A2A_INBOUND_PEERS` | implementations | task definition | unset | JSON list of `{name, token_secret}`: peers allowed to call this implementation's specialist (FR-039); tokens are read from Secrets Manager, never from files |
| `A2A_TIMEOUT_SECONDS` | implementations | task definition | `30` | Per remote call (contracts/a2a-specialist.md) |
| `A2A_MAX_HOPS` | implementations | task definition | `2` | Loop guard: a specialist refuses requests with hops >= this value |
| `SANDBOX_TIMEOUT_SECONDS`, `SANDBOX_MAX_OUTPUT_BYTES` | implementations that support US13 | task definition | compose | Limits for the isolated run; exceeding either records `outcome='cut_off'` |

Secrets: peer bearer tokens for A2A are Secrets Manager entries created by OpenTofu (per implementation root), injected at runtime, and never written to a file (Constitution V). The sandbox receives no secret variables.
