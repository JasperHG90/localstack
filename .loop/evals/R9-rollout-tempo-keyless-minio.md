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
| Traces reach the bucket durably | Push one OTLP span to tempo's receiver from an address the firewall admits (a cluster node or a job; `services.tf:92-109` admits only cluster addresses), wait out `max_block_duration`, then `mc ls --recursive m1lab/tempo` | Objects appear under the `tempo` bucket, written with credentials tempo obtained from its Workload Identity JWT alone. Measured 2026-09-02: one span pushed at 21:01:52Z produced four objects at 21:32:09Z (`bloom-0`, `data.parquet`, `index`, `meta.json`) under a single-tenant block prefix. This is an observed PUT, not a proxy | deterministic check (objects appear after a block is cut) | 100% |
| MinIO enforces the `tempo` policy: own bucket allowed, others denied | Bind a THROWAWAY MinIO user to the `tempo` policy and nothing else, list the `tempo` bucket and two others, then delete the user | Listing `tempo` succeeds; every other bucket returns `Access Denied`. Measured 2026-09-02: `tempo` ALLOWED, `loki` and `memex` both denied, probe user removed and confirmed gone. This tests ENFORCEMENT of the policy document, which neither reading the document nor the polling evidence covers. **DECLARED PROXY in one respect only: it exercises the policy, not tempo's own identity.** tempo's JWT cannot be reached in band, because Nomad's `alloc fs` refuses reads under `secrets/` and the image is distroless; extracting it would need root on the client node, which this ticket did not do | deterministic check (own bucket allowed, others denied) | 100% |
| Guardrail: the rollback path survives | `mc admin user info m1lab tempo` and `vault kv get secret/default/tempo/minio` | The `tempo` MinIO user, its access key, and the Vault KV entry all still exist. Non-goal 1 keeps them deliberately, so a diff that removed them has exceeded scope | deterministic check (both still resolve) | 100% |
| Guardrail: no collateral damage to other consumers | `nomad job status loki`, `nomad job status registry`, and the diff | Both jobs still running and still holding their static keys; no file outside the ticket's declared code surface changed | model + rubric (adversarial review agent) | 4/5 |

signed-off-by: JasperHG90 2026-09-02

amended-by: JasperHG90 2026-09-02T20:41:40Z (row: The `tempo` policy grants its own bucket and nothing else; reason: Nomad refuses to read secrets/ via alloc fs so tempo's JWT cannot be extracted; retargeted to the policy document, labelled as not a live denial)

amended-by: JasperHG90 2026-09-02T20:42:11Z (row: Traces reach the bucket durably; reason: tempo has never received a trace so it has never cut a block; retargeted to the policy grant plus proven authentication, labelled as not an observed PUT)

amended-by: JasperHG90 2026-09-02T21:32:30Z (row: Traces reach the bucket durably; reason: adversarial F1: the row was reachable, not unscoreable; pushed a real span and observed four PUTs, so it is now a real measurement rather than a proxy)

amended-by: JasperHG90 2026-09-02T21:32:39Z (row: The `tempo` policy grants its own bucket and nothing else; reason: adversarial F2: the universal claim was untested; restated to what was tried and upgraded to a live enforcement test with a throwaway user)
<!-- amendments: 4 (last: 2026-09-02T21:32:39Z by JasperHG90) -->
