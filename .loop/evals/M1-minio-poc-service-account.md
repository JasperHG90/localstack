# Eval: M1 MinIO OIDC POC — keyless machine access via Nomad Workload Identity

eval: M1-minio-poc-service-account

**Definition of Done:** A throwaway Nomad job assumes STS credentials from
MinIO using only its Workload Identity JWT (no static keys), reading its own
bucket in both role-policy and claim modes while being denied every other
bucket, with the `NOMAD` OIDC provider coexisting with a second named IdP and
existing static-key consumers untouched.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| Operator sees the `NOMAD` OIDC provider live on MinIO (phase one) | `mc admin config get <alias> identity_openid` after subticket 2 applied | A `NOMAD`-named `identity_openid` block (target name is the uppercase env-var suffix, e.g. `MINIO_IDENTITY_OPENID_CONFIG_URL_NOMAD`; MinIO does no case-folding) with `config_url` = Nomad OIDC discovery URL, `client_id=minio` (matching `aud=["minio"]`), `role_policy` set to the phase-one policy, and no `claim_name` | deterministic check (`mc admin config get <alias> identity_openid`) | 100% |
| Operator confirms the throwaway consumer is running with a rendered WI JWT | `nomad job status m1-poc` after subticket 3 applied | `Status = running` with one healthy allocation; the `identity` stanza has rendered the WI JWT (e.g. to `secrets/nomad_minio.jwt`) | deterministic check (`nomad job status m1-poc`) | 100% |
| Job exchanges its WI JWT for STS credentials (role-policy mode) | from inside the alloc: `curl -sS -X POST "http://<minio>:9000/?Action=AssumeRoleWithWebIdentity&Version=2011-06-15&RoleArn=<RoleArn-from-row-1>&WebIdentityToken=$(cat secrets/nomad_minio.jwt)"` | XML `<Credentials>` carrying `<AccessKeyId>`, `<SecretAccessKey>`, `<SessionToken>` and a short `<Expiration>` | deterministic check (STS POST returns `<Credentials>`) | 100% |
| Assumed identity reads its own target bucket | carry the row-3 credentials in a session-token alias, then list: `MC_HOST_sts="http://<AccessKeyId>:<SecretAccessKey>:<SessionToken>@<minio>:9000" mc ls sts/memex` | The object listing returns with exit 0 | deterministic check (`mc ls sts/memex`) | 100% |
| Reviewer judges that both trust modes prove Nomad-to-MinIO trust and dynamic per-job RBAC | Recorded row-3 (role-policy `RoleArn`) outcomes plus the claim-mode run: repeat the STS POST with no `RoleArn` under `CLAIM_NAME_NOMAD=nomad_job_id`, then `MC_HOST_sts=... mc ls sts/memex` | Role-policy mode isolates trust before RBAC, then claim mode grants the same own-bucket read purely from `nomad_job_id` mapping to a same-named policy (no `RoleArn`); the two-phase proof is sound and phase one preceded phase two | model + rubric (adversarial review agent) | 4/5 |
| Cross-bucket access is denied, proving per-job policy == `nomad_job_id` | reusing the claim-mode credentials: `MC_HOST_sts="http://<AccessKeyId>:<SecretAccessKey>:<SessionToken>@<minio>:9000" mc ls sts/<other-bucket>` | `AccessDenied` (the `m1-poc` policy grants exactly the `memex` bucket and nothing else) | deterministic check (`mc ls sts/<other-bucket>` refused) | 100% |
| Reviewer judges the multi-IdP shape leaves room for the Vault-as-IdP sibling | `mc admin config get <alias> identity_openid` after subticket 6 | Two named `identity_openid` configs coexist (`NOMAD` plus a second real target, e.g. `POC2`, pointed at the SAME reachable Nomad discovery URL under a different `client_id` — never a fake/unreachable URL, since MinIO's `LookupConfig` aborts the whole config load if any one target's discovery document fails to parse), confirming the multi-IdP shape is real rather than assumed, with `NOMAD` still working | model + rubric (adversarial review agent) | 4/5 |

signed-off-by: JasperHG90 2026-08-03

amended-by: JasperHG90 2026-09-02T08:39:42Z (row: Job exchanges its WI JWT for STS credentials (role-policy mode); reason: operator directed: prove the same behavior without the AWS CLI, so the throwaway POC image need not ship it)

amended-by: JasperHG90 2026-09-02T08:39:49Z (row: Reviewer judges that both trust modes prove Nomad-to-MinIO trust and dynamic per-job RBAC; reason: operator directed: prove the same behavior without the AWS CLI, so the throwaway POC image need not ship it)

amended-by: JasperHG90 2026-09-02T08:40:50Z (row: Assumed identity reads its own target bucket; reason: operator directed: prove the same behavior without the AWS CLI, so the throwaway POC image need not ship it)

amended-by: JasperHG90 2026-09-02T08:40:50Z (row: Cross-bucket access is denied, proving per-job policy == `nomad_job_id`; reason: operator directed: prove the same behavior without the AWS CLI, so the throwaway POC image need not ship it)
<!-- amendments: 4 (last: 2026-09-02T08:40:50Z by JasperHG90) -->
