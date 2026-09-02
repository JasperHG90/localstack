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
- **VERIFIED (2026-09-02, after R9 shipped)** — the thanos route exists and
  exposes the endpoint properly. Loki 3.4.2 carries
  `use_thanos_objstore` (`pkg/storage/factory.go` lines 298 and 329,
  default `false`), which routes object storage through
  `thanos-io/objstore`. That library's S3 provider has a first-class
  `sts_endpoint` config field (`providers/s3/s3.go` line 138) which it
  passes straight to minio-go's IAM provider (lines 238-242), the same
  provider R9 drives for tempo. So the auth mechanism is proven available,
  and through a REAL config field rather than tempo's `TEST_IAM_ENDPOINT`,
  which is the nicer of the two.
- **NEW RISK, and the reason this is still a stub** — turning on
  `use_thanos_objstore` swaps Loki's entire storage client, and moves
  configuration from `storage_config.aws` to
  `storage_config.object_store`. That makes this a client migration with
  keyless auth as a side effect, NOT the auth-only change R9 was. Whether
  thanos reads the existing objects in the `loki` bucket identically, and
  what happens to data written by the old client, has to be settled before
  planning. Getting this wrong loses logs.
- **UNVERIFIED** — the `credential_process` fallback. aws-sdk-go v1
  supports it in the shared config file, which would let a small helper
  perform the exchange regardless of SDK limits. Needs a shell and an HTTP
  client inside the loki image, neither confirmed.
- **VERIFIED, upstream, and NOT a contradiction of the thanos finding
  above** — `grafana/loki#8014` is still open, but it asks for web identity
  in Loki's OWN S3 client, the `storage_config.aws` path built on
  aws-sdk-go v1. That request being open is why the default path cannot do
  this. The thanos route sidesteps it by using a different client
  entirely, so it is a supported configuration of a supported library, not
  a trick. Pin the Loki version regardless and re-check on upgrade.

## Non-goals

- Patching or vendoring Loki.
- Removing loki's static key in the same ticket. Keep it as the rollback
  path, as R9 does.
- Touching tempo, registry or memex.

## Open questions

- Q1. **Answered.** The thanos path allows a custom STS endpoint; see the
  verified premise above. The open question is no longer "can it" but "what
  does switching clients cost". Recommendation: treat the storage-client
  swap as the risk to plan around, and confirm read compatibility against
  the existing `loki` bucket before cutting over.
- Q2. If no config-only path exists, is a `credential_process` helper
  acceptable here, or does loki stay on a static key until upstream ships
  the feature? Recommendation: operator call. Losing log ingestion is worse
  than losing traces, so the bar for a clever workaround should be higher
  than it was for tempo.
- Q3. Should this wait for R9 to prove itself in production first?
  Recommendation: yes, hence `depends_on`.
