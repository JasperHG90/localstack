---
epic = "rollout"
depends_on = ["R9-rollout-tempo-keyless-minio"]
priority = 15
summary = "Move the loki job off its static MinIO access key onto Workload Identity. Mechanism UNVERIFIED: loki carries three S3 clients and the reachable one may not allow a custom STS endpoint."
stub = true
---

# Ticket: R10-rollout-loki-keyless-minio

## Triggered by

M1 landed keyless MinIO access; R9 makes tempo the first real consumer.
Loki holds the same shape of long-lived static key
(`deployments/applications/services/loki.hcl:68-69,121-122`) and should
follow. Whether it CAN is unsettled, which is why this is a stub rather
than a plan.

## Vision & rough premises

Same end state as R9: a named `identity` block for the `minio` audience, a
`minio_iam_policy` named `loki`, no static key in the job, and the Vault KV
entry kept as the rollback path.

The mechanism is the open part. Loki 3.4.2 vendors THREE candidate S3
clients (`go.mod` at `v3.4.2`): `aws-sdk-go v1.55.6`,
`minio-go/v7 v7.0.84`, and `thanos-io/objstore`. Which one serves a given
config path decides whether this is env-vars-only like R9 or needs real
work.

- **UNVERIFIED** — Loki's default `storage_config.aws` path uses
  aws-sdk-go v1, which has no environment variable for redirecting STS to
  a non-AWS endpoint. If that is the reachable path, the R9 approach does
  not transfer.
- **UNVERIFIED** — Loki 3.x can route object storage through
  `thanos-io/objstore`, which uses minio-go underneath. If that path is
  reachable AND exposes the IAM provider's endpoint the way tempo does,
  this becomes an R9 copy. Thanos may hardcode an empty endpoint, in which
  case minio-go falls back to `sts.<region>.amazonaws.com` and the call
  leaves the LAN.
- **UNVERIFIED** — the `credential_process` fallback. aws-sdk-go v1
  supports it in the shared config file, which would let a small helper
  perform the exchange regardless of SDK limits. Needs a shell and an HTTP
  client inside the loki image, neither confirmed.
- **VERIFIED, upstream** — Loki has no native support for this today:
  `grafana/loki#8014`, the feature request for AssumeRoleWithWebIdentity
  against S3, is still open. So any path here is a configuration trick, not
  a supported feature, and should be pinned and re-checked on upgrade.

## Non-goals

- Patching or vendoring Loki.
- Removing loki's static key in the same ticket. Keep it as the rollback
  path, as R9 does.
- Touching tempo, registry or memex.

## Open questions

- Q1. Which of the three clients actually serves the configured storage
  path, and does it allow a custom STS endpoint? This is the whole ticket.
  Recommendation: settle it by reading the pinned source before writing
  the plan, the way R9's premises were settled, rather than by trying
  configurations against the live cluster.
- Q2. If no config-only path exists, is a `credential_process` helper
  acceptable here, or does loki stay on a static key until upstream ships
  the feature? Recommendation: operator call. Losing log ingestion is worse
  than losing traces, so the bar for a clever workaround should be higher
  than it was for tempo.
- Q3. Should this wait for R9 to prove itself in production first?
  Recommendation: yes, hence `depends_on`.
