---
type: component
title: MinIO
description: "The single-node MinIO on orangepi4a: the infrastructure root runs it and owns the root key, the applications root owns every bucket, user and policy. Every workload, the nightly backup and the s3 route have moved to SeaweedFS, so nothing reads or writes MinIO any more. It still runs with its data, and the claim-mode policies and static keys remain with nothing using them."
tags: [minio, s3, object-storage, workload-identity, terraform, component]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: minio-jobspec
    resource: deployments/infrastructure/services/minio.hcl
  - id: infra-services
    resource: deployments/infrastructure/services.tf
  - id: infra-secrets
    resource: deployments/infrastructure/secrets.tf
  - id: app-storage
    resource: deployments/applications/storage.tf
  - id: bucket-module
    resource: deployments/applications/modules/bucket/main.tf
  - id: app-secrets
    resource: deployments/applications/secrets.tf
  - id: app-services
    resource: deployments/applications/services.tf
---

# MinIO

One MinIO server held every on-cluster bucket until the 2026-10-20 cutover to
[SeaweedFS](/components/seaweedfs.md). It still runs with its data, but no job,
backup or edge route reads or writes it, and `minio-removal` removes it. How a
job traded its Nomad
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
| Edge: `backend minio` (console). `backend s3` points at SeaweedFS since the cutover | `deployments/infrastructure/services/haproxy.hcl` |
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

No `nomad_job` depends on these policies any more. The registry's
`depends_on` went when it moved to SeaweedFS.

## Who holds a key

Keyless: none since 2026-10-20. Tempo (R9), loki (R13) and the registry (R13,
an AWS `credential_process` helper, because it vendors aws-sdk-go v1) were
keyless here until they moved to [SeaweedFS](/components/seaweedfs.md), the
registry last. The three `minio_iam_policy.*_wi` policies and the jobs'
static MinIO keys remain with nothing using them.

R13 replaced two stubs that were never built. R10 (loki) had found a
config-only route: loki 3.4.2's `use_thanos_objstore` reaches thanos-io's S3
provider, which has a real `sts_endpoint` field. But that swaps loki's whole
storage client and moves its config block, which puts the existing logs in
the `loki` bucket at risk. R11 (registry) had ruled config-only out, because
distribution v3.1.1 vendors aws-sdk-go v1, and found the Alpine-based image
could run a `credential_process` helper. R13 took R11's helper for both jobs,
so loki keeps its storage client. R12 (memex) was dropped by the operator
when the stubs were written (`a7aa595`): memex takes its key as two explicit
settings in its own config, so going keyless needs a web-identity provider
and credential refresh in the memex repo, not a jobspec change. R10 and R11
were still stubs, and R12 was dropped, in the loop ledger when `5b2ed1b` reset
the loop.

Still keyed: memex (its job is commented out, and its fix needs changes in
the memex repo, see R12 above). `backup-minio` read a copy of the ROOT key
until 2026-10-20, when it moved to SeaweedFS. That copy,
`default/backup-minio/minio`, is still written. Keys that nothing consumes are still minted for `ducklake_writer`,
`ducklake_reader`, `models_writer`, `models_reader`, `mlflow`, and
`openviking`, whose job left MinIO for SeaweedFS on 2026-10-20 and keeps a
static key there (ADR 0007). Removing the rollback keys is what actually
shrinks this list, and no ticket owns it yet.

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
- **Nothing here is backed up any more.** Since 2026-10-20 `backup-minio`
  reads the four durable buckets from SeaweedFS, into the same `minio/`
  prefixes in GCS. MinIO's own copies of them are frozen at the cutover, and
  `loki`, `tempo`, `memex` and `mlflow-artifacts` never had an off-site copy.
  See [GCS backups](/components/gcs-backups.md).
- **`mlflow-artifacts` outlived its service** on purpose. Emptying it and
  deleting the entry is a separate decision.
- **Human console tiers are not built.** M2 was blocked when `5b2ed1b` reset the loop and
  is not in the current loop. Whoever builds it
  replaces `POC2` rather than adding a third target.

## Planned, not built

MinIO is due to be replaced by SeaweedFS, which already runs beside it on
orangepi4a with its own buckets, users and keys
([SeaweedFS](/components/seaweedfs.md)). `minio-removal` plans the removal
of the MinIO job, provider, resources, routes and monitoring once nothing
uses it. The nightly [GCS backup](/components/gcs-backups.md) copies every
durable bucket, so the migration restores from off-site with the
`restore-s3` job. `openviking`, `models`, `datalake` and `registry` moved
that way on 2026-10-20, and the same day the backup job, the `s3` Consul tag,
the `s3.lab.orangecluster.nl` route and the dash tile followed
(`seaweedfs-cutover`). `minio.lab.orangecluster.nl` still serves the MinIO
console until `minio-removal`. The `minio_data` volume and its data stay until the operator
promotes the stub `minio-volume-destroy`. When `minio-removal` lands, this
page is marked superseded.

## Evidence

Built or recorded from these, which a `sources` entry cannot point at:

- loop ticket `M1-minio-poc-service-account` (its plan and any verdicts are under `.loop/` at commit `48f52e2`, from before the `5b2ed1b` loop reset)
- loop ticket `R9-rollout-tempo-keyless-minio` (its plan and any verdicts are under `.loop/` at commit `48f52e2`, from before the `5b2ed1b` loop reset)
- loop ticket `R13-rollout-loki-registry-keyless-minio` (its plan and any verdicts are under `.loop/` at commit `48f52e2`, from before the `5b2ed1b` loop reset)
- loop ticket `R10-rollout-loki-keyless-minio`, a stub superseded by R13 (its plan is `.loop/plans/` at commit `48f52e2`, with the premise answered in `64c656e`)
- loop ticket `R11-rollout-registry-keyless-minio`, a stub superseded by R13 (its plan is `.loop/plans/` at commit `48f52e2`, with the premise answered in `64c656e`)
- loop ticket `R12-rollout-memex-keyless-minio`, a stub the operator dropped (its plan is `.loop/plans/` at commit `48f52e2`, dropped in `a7aa595`)
- commit `84b69a1`, the R13 plan that supersedes R10 and R11
