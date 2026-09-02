---
epic = "rollout"
depends_on = ["R9-rollout-tempo-keyless-minio"]
priority = 12
summary = "Move the OCI registry off its static MinIO access key onto Workload Identity. Config-only is ruled OUT: registry vendors aws-sdk-go v1, which cannot be pointed at a non-AWS STS. Needs a credential_process helper."
stub = true
---

# Ticket: R11-rollout-registry-keyless-minio

## Triggered by

M1 landed keyless MinIO access; R9 makes tempo the first real consumer.
The registry holds the same shape of long-lived static key, rendered
straight into its config file
(`deployments/applications/services/registry.hcl:79-80`).

## Vision & rough premises

Same end state as R9: a named `identity` block for the `minio` audience, a
`minio_iam_policy` named `registry`, no static key in the job, Vault KV
entry kept as rollback.

The mechanism differs from R9 and is the reason this is a stub.

- **VERIFIED** — the registry's S3 driver falls back to the AWS credential
  chain when `accesskey` and `secretkey` are omitted (distribution's S3
  storage-driver docs: "omit to fetch temporary credentials from IAM").
  So there is a hook.
- **VERIFIED** — the R9 approach does NOT transfer. distribution v3.1.1
  vendors `aws-sdk-go v1.55.5` (`go.mod` at tag `v3.1.1`), not v2. SDK v1
  has no `AWS_ENDPOINT_URL_STS`, so its web-identity provider would call
  Amazon's STS, not MinIO's. Config-only is ruled out.
- **UNVERIFIED** — `credential_process` is the likely path. aws-sdk-go v1
  supports it in the shared config file, and the SDK re-invokes the process
  when the returned credentials expire, giving refresh with no restarts.
  Because the helper performs the exchange itself, MinIO's claim mode works
  unchanged and no new OIDC target is needed.
- **VERIFIED (2026-09-02, after R9 shipped)** — the image can run a helper.
  distribution's Dockerfile at tag `v3.1.1` builds its final stage
  `FROM alpine` (line 62), not `scratch`, so `/bin/sh` and busybox (with
  `wget` for the HTTPS call) are present. `credential_process` is viable
  and no derived image is needed, which also kills the circularity Q2
  worried about.

## Non-goals

- Rebuilding or forking the registry unless the image inspection forces it.
- Removing the static key in the same ticket; keep the rollback path.
- Touching tempo, loki or memex.

## Open questions

- Q1. **Answered: yes.** The final image is Alpine-based, so a
  `credential_process` helper can run in it. This is a Small ticket, not a
  Medium one.
- Q2. **Moot.** No derived image is needed, so the circularity (the
  registry being where this cluster's custom images live) does not arise.
  The remaining design choice is where the helper script comes from: a
  Nomad `template` rendering it into `local/` is the obvious answer and
  needs no image change at all.
- Q3. Blast radius is higher than tempo's. A broken registry blocks every
  image pull that is not already cached, including the recovery path.
  Recommendation: schedule this deliberately, not at the end of a session,
  and confirm rollback works before cutting over.
