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
- **UNVERIFIED, and the blocker for planning** — `credential_process` runs
  INSIDE the container, so the registry image needs a shell and an HTTP
  client. `docker.io/library/registry:3.1.1` has not been inspected. If it
  ships neither, the options are a thin derived image (the repo already
  builds custom images and runs its own OCI registry) or a different
  approach entirely.

## Non-goals

- Rebuilding or forking the registry unless the image inspection forces it.
- Removing the static key in the same ticket; keep the rollback path.
- Touching tempo, loki or memex.

## Open questions

- Q1. Does `registry:3.1.1` contain a shell and an HTTP client?
  Recommendation: settle this FIRST, before any planning. It decides
  between a small config change and an image build, which is the
  difference between a Small and a Medium ticket.
- Q2. If the image is minimal, is a derived image acceptable for the
  registry specifically? Note the circularity: the registry is where this
  cluster's custom images live, so an image built to fix the registry has
  to be pullable while the registry is degraded. Recommendation: operator
  call, and prefer any path that avoids it.
- Q3. Blast radius is higher than tempo's. A broken registry blocks every
  image pull that is not already cached, including the recovery path.
  Recommendation: schedule this deliberately, not at the end of a session,
  and confirm rollback works before cutting over.
