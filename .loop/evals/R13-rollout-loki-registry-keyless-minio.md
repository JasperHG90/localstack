# Eval: R13 loki and registry keyless MinIO via credential_process

eval: R13-rollout-loki-registry-keyless-minio

**Definition of Done:** loki and registry both authenticate to MinIO by
exchanging their Workload Identity JWTs through a `credential_process`
helper, holding no static credential in their jobspecs, each scoped by a
policy named for its job id and denied every other bucket, with both static
keys left provisioned as rollback paths and tempo and memex untouched.

**Applies to every row:** each service is scored separately. loki is cut over
and verified before registry is touched, so a failure on loki never costs the
ability to pull images.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| Each job runs with a rendered Workload Identity JWT | `nomad job status <job>`, then `nomad alloc fs <alloc> <job>/secrets` | Healthy allocation, and the secrets dir lists `nomad_minio.jwt`. Scored once for loki and once for registry | deterministic check (`nomad alloc fs` lists the JWT) | 100% |
| No static MinIO credential is reachable by either task | `nomad job inspect <job>` for each, checking BOTH the nine env names and registry's YAML keys | Neither jobspec contains `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_ACCESS_KEY`, `AWS_SECRET_KEY`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` or `AWS_WEB_IDENTITY_TOKEN_FILE`, no `minio.env` is rendered, and registry's inspected jobspec contains no `accesskey` or `secretkey` line. Nine names, not eight: `AWS_WEB_IDENTITY_TOKEN_FILE` is what tempo sets, so it is what an implementer copies, and it pre-empts `credential_process` before the shared-config profile is read. The YAML check is separate because registry's static key is two config lines, not an env var, so a name-only check would pass a registry that never changed | deterministic check (grep the submitted jobspec, both shapes) | 100% |
| The helper returns usable credentials from inside each container | Run `/local/minio-creds.sh` via `nomad alloc exec` in each task | Prints a single JSON document carrying `Version`, `AccessKeyId`, `SecretAccessKey`, `SessionToken` and an `Expiration` roughly an hour out, and nothing else on stdout | deterministic check (output parses as JSON with all five keys) | 100% |
| The SDK actually invokes the helper rather than falling through to anonymous | After cutover, each service's own logs for one poll or push interval | No `AccessDenied` and no anonymous-request error. This is the row that catches `AWS_SDK_LOAD_CONFIG` being unset, where the config file is never read, the helper never runs, and the client goes anonymous with no mention of the script | deterministic check (log scan, no auth errors) | 100% |
| Each service does real S3 work through the exchanged credentials | loki: a new object appears under the `loki` bucket after cutover (`mc ls --recursive m1lab/loki`, count rises). registry: an image pull through the registry succeeds, or a new object appears under the `registry` bucket | The count rises for loki; the registry serves a pull or writes a blob. Observed work, not merely a granted policy | deterministic check (object count rises / pull succeeds) | 100% |
| Each policy grants its own bucket and denies the others | Bind a throwaway MinIO user to only the `loki` policy, list `loki`, `tempo` and `registry`; repeat with the `registry` policy; delete both users | The own bucket lists; every other bucket returns `Access Denied`. Tests that MinIO ENFORCES each document, which reading the document does not. R9 established this method | deterministic check (own allowed, others denied) | 100% |
| Guardrail: both rollback paths survive | `mc admin user info m1lab loki`, `... registry`, and `vault kv get` on both `default/<svc>/minio` entries | Both MinIO users, both access keys and both Vault KV entries still exist. Non-goal 1 keeps them deliberately, so a diff that removed them has exceeded scope | deterministic check (all four still resolve) | 100% |
| Guardrail: no collateral damage | `nomad job status tempo` and `memex`, plus `mc ls --recursive m1lab/tempo`, plus the diff | tempo still runs keyless and its bucket still receives writes; memex still runs on its static key; no file outside the ticket's declared code surface changed | model + rubric (adversarial review agent) | 4/5 |

signed-off-by: JasperHG90 2026-09-03

amended-by: JasperHG90 2026-09-03T07:25:01Z (row: No static MinIO credential is reachable by either task; reason: plan review required fixes 2 and 3: AWS_WEB_IDENTITY_TOKEN_FILE pre-empts credential_process and was missing, and registry's key is two YAML lines that a name-only check would miss)
<!-- amendments: 1 (last: 2026-09-03T07:25:01Z by JasperHG90) -->
