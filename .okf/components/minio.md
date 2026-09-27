---
type: component
title: MinIO
description: "The single-node MinIO on orangepi4a: the infrastructure root runs it and owns the root key, the applications root owns every bucket, user and policy. Three jobs reach their bucket keylessly through a claim-mode policy named after the job, and every other consumer, plus the backup job, still holds a static key."
tags: [minio, s3, object-storage, workload-identity, terraform, component]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: minio-jobspec
    resource: git:3ec5d1e:deployments/infrastructure/services/minio.hcl
  - id: infra-services
    resource: git:3ec5d1e:deployments/infrastructure/services.tf
  - id: infra-secrets
    resource: git:3ec5d1e:deployments/infrastructure/secrets.tf
  - id: app-storage
    resource: git:3ec5d1e:deployments/applications/storage.tf
  - id: bucket-module
    resource: git:3ec5d1e:deployments/applications/modules/bucket/main.tf
  - id: app-secrets
    resource: git:3ec5d1e:deployments/applications/secrets.tf
  - id: app-services
    resource: git:3ec5d1e:deployments/applications/services.tf
  - id: M1-minio-poc-service-account
    resource: loop:M1-minio-poc-service-account
  - id: R9-rollout-tempo-keyless-minio
    resource: loop:R9-rollout-tempo-keyless-minio
  - id: R13-rollout-loki-registry-keyless-minio
    resource: loop:R13-rollout-loki-registry-keyless-minio
---

# MinIO

One MinIO server holds every on-cluster bucket. How a job trades its Nomad
JWT for MinIO credentials is `docs/explanation/workload-identity.md` ("Keyless
MinIO access"), and the procedure is
`docs/how-to/give-a-job-keyless-minio-access.md`. This page is how the parts
are laid out across the repository and what bites when you change them.

## The pieces

| Piece | Where |
| --- | --- |
| Job `minio`, pinned to orangepi4a, `RELEASE.2025-09-07T16-13-09Z` | `deployments/infrastructure/services/minio.hcl` |
| Host volume `minio_data` (1 to 3.5 TiB) | `deployments/infrastructure/services.tf` |
| Firewall: 9000 (S3) and 9001 (console) from `192.168.0.0/16` | `local.firewall_rules`, same file |
| Edge: `backend s3` and `backend minio` | `deployments/infrastructure/services/haproxy.hcl` |
| Root key: access key `minio`, secret `random_password.minio_secret_key` | KV `default/minio/localstack`, `deployments/infrastructure/secrets.tf` |
| OIDC targets `NOMAD` (claim mode) and `POC2` | env template in `minio.hcl` |
| Buckets, users, access keys | `local.buckets` in `deployments/applications/storage.tf` |
| Per-bucket policies and attachments | `deployments/applications/modules/bucket/main.tf` |
| Claim-mode policies `tempo`, `loki`, `registry` | `minio_iam_policy.*_wi` in `storage.tf` |

The applications root's `minio` provider finds the server through Consul
(`data.consul_service.minio`) and logs in with the root key read ephemerally
from `default/minio/localstack`. So the infrastructure root applies first, and
the MinIO job must be registered in Consul before the applications root can
plan.

## Two kinds of policy, one namespace

Each entry in `local.buckets` becomes a bucket plus two policies from the
module, `<bucket>_read_write` and `<bucket>_read_only` (hyphens turned to
underscores), attached to the users listed as writers and readers. Every
listed user also gets a `minio_accesskey`, and
`vault_kv_secret_v2.minio_credentials` writes each key to
`default/minio/<user>`. A job that uses its key reads a second copy under its
own prefix (for example `default/openviking/minio`), because `nomad-workloads`
only grants a job its own path.

The claim-mode policies are different. MinIO applies the policy whose NAME
equals the JWT's `nomad_job_id`, so `minio_iam_policy.tempo_wi` is named
`tempo` and has no attachment. Three rules follow:

- **The name is the grant.** Any MinIO policy whose name matches a job id
  grants that job, whatever you meant it for. That is why OpenViking's static
  key has no `openviking` policy beside it
  ([ADR 0007](/decisions/0007-openviking-static-key-has-no-claim-policy.md)).
  The module's `_read_write`/`_read_only` suffixes keep its policies out of
  the way.
- **Claim mode ignores the namespace.** A job with the same name in another
  Nomad namespace would get the same policy (R9 follow-up). Every job here is
  in `default` today.
- **The policies stay out of the module**, deliberately, until a second
  pattern proves the shape (comment on `minio_iam_policy.tempo_wi`). The bucket
  name inside each policy is a plain string because `module.buckets` exports
  nothing.

Each keyless job's `nomad_job` in `deployments/applications/services.tf`
carries `depends_on` on its policy. Without the policy, tempo falls back to
anonymous and reports a plain permission error, and loki's and registry's
helper exits non-zero.

## Who holds a key

Keyless: tempo (R9, minio-go's web-identity provider), loki and registry (R13,
an AWS `credential_process` helper, because both vendor aws-sdk-go v1). Their
static keys, users and KV entries stay provisioned as the rollback path and
are simply not rendered into the jobs.

Still keyed: openviking (by design, ADR 0007), memex (its job is commented
out, and its fix needs changes in the memex repo), and `backup-minio`, which
reads a copy of the ROOT key. Keys that nothing consumes are still minted for
`ducklake_writer`, `ducklake_reader`, `models_writer`, `models_reader` and
`mlflow`. Removing the rollback keys is what actually shrinks this list, and
no ticket owns it yet.

## Invariants and what enforces them

- **Exactly one claim-mode target.** MinIO refuses a second one
  (`errSingleProvider`), so `POC2` carries a `role_policy`. That policy,
  `poc2-intentionally-undefined`, must never be created: MinIO's only
  principal check is `aud` against `client_id`, and a jobspec author picks
  their own `aud`. M1 first pointed it at `memex_read_write`, which handed
  `s3:*` on the memex bucket to anyone who asked. Nothing enforces this but the
  comment.
- **Every configured discovery URL must be live.** `LookupConfig` aborts the
  whole OIDC load if any one document fails to parse, so a placeholder takes
  the `NOMAD` target down too.
- **The target is `NOMAD`, in capitals.** MinIO takes the env var suffix
  verbatim.
- **The discovery URL follows the Nomad server's `oidc_issuer`** in
  `bootstrap/roles/nomad_server/templates/nomad.hcl.j2`. It is a literal in
  `nomad_job.minio`. See
  [Nomad's OIDC discovery document](/components/nomad-oidc-discovery.md).

## Traps

- **Metrics are public.** `MINIO_PROMETHEUS_AUTH_TYPE="public"` is why the
  Prometheus `minio` job needs no token, and why 9000 serves metrics to the
  whole LAN.
- **Only one bucket is backed up.** `backup-minio` syncs `openviking` and
  nothing else. The registry's images and ModelKits, `models`, `loki`, `tempo`,
  `datalake` and `mlflow-artifacts` have no off-site copy. See
  [GCS backups](/components/gcs-backups.md).
- **`mlflow-artifacts` outlived its service** on purpose. Emptying it and
  deleting the entry is a separate decision.
- **The registry names MinIO twice.** Its STS helper uses the Consul address,
  its storage config a literal `192.168.2.29`. Moving MinIO means changing
  both.
- **Human console tiers are not built.** M2 is blocked. Whoever builds it
  replaces `POC2` rather than adding a third target.
