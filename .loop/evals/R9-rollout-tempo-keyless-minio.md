# Eval: R9 tempo keyless MinIO — first real Workload Identity consumer

eval: R9-rollout-tempo-keyless-minio

**Definition of Done:** The tempo job authenticates to MinIO by exchanging
its Nomad Workload Identity JWT, holding no static credential anywhere in
its jobspec or rendered secrets, scoped by a `tempo`-named policy to its own
bucket and denied every other, with tempo's static key left provisioned as
the rollback path and loki and registry untouched.

**Tooling constraint binding every row:** `grafana/tempo:2.10.8` is
distroless. `/tempo` is the only executable, with no `/bin/sh`, so
`nomad alloc exec` is unavailable. Rows read `nomad job inspect`,
`nomad alloc fs`, tempo's logs, or MinIO directly.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| Tempo runs with a rendered Workload Identity JWT | `nomad job status tempo`, then `nomad alloc fs <alloc> secrets/` | `Status = running` with one healthy allocation, and the secrets dir lists `nomad_minio.jwt` | deterministic check (`nomad alloc fs` lists the JWT) | 100% |
| No static MinIO credential is reachable by the task | `nomad job inspect tempo` and `nomad alloc fs <alloc> secrets/` | Neither contains `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY`, and no `minio.env` is rendered. `MINIO_ROOT_*` are included because minio-go's `EnvMinio` provider checks those names first, so omitting them would leave a live fallback unscored | deterministic check (grep over jobspec and rendered secrets) | 100% |
| MinIO accepts the exchanged credentials, observed at the earliest opportunity | tempo's logs for one `blocklist_poll` interval after the cutover | No `Access Denied` and no `AUTH: None`; the blocklist poll completes. A successful LIST is the first observable proof the STS credentials work, because tempo issues no PUT until it cuts a block | deterministic check (log scan over one poll interval) | 100% |
| Traces reach the bucket durably | `mc ls --recursive m1lab/tempo`, allowing up to `max_block_duration` (`tempo.hcl:105` = `30m`) | Object count under the `tempo` bucket rises after the cutover. Scored on a 30-minute horizon, not immediately after apply | deterministic check (object count rises) | 100% |
| The `tempo` policy grants its own bucket and nothing else | Exchange tempo's JWT directly (curl to MinIO STS per `docs/workload-identity.md`), then list the `tempo` bucket and another bucket with the returned credentials | Own bucket lists (exit 0); the other returns `AccessDenied`. Judged on this independent exchange and NOT on tempo's logs, because a missing policy and a real denial are indistinguishable from inside tempo (minio-go's chain swallows the provider error and falls back to anonymous) | deterministic check (allow own, deny other) | 100% |
| Guardrail: the rollback path survives | `mc admin user info m1lab tempo` and `vault kv get secret/default/tempo/minio` | The `tempo` MinIO user, its access key, and the Vault KV entry all still exist. Non-goal 1 keeps them deliberately, so a diff that removed them has exceeded scope | deterministic check (both still resolve) | 100% |
| Guardrail: no collateral damage to other consumers | `nomad job status loki`, `nomad job status registry`, and the diff | Both jobs still running and still holding their static keys; no file outside the ticket's declared code surface changed | model + rubric (adversarial review agent) | 4/5 |

signed-off-by: JasperHG90 2026-09-02
