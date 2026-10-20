---
type: component
title: MinIO
description: "Superseded by SeaweedFS. The single-node MinIO on orangepi4a held every bucket until the 2026-10-20 cutover, and minio-removal took out its job, routes, monitoring, keys and Terraform state the same day. minio-volume-destroy then deleted its minio_data volume and data. Nothing of it remains on the cluster, and only the GCS backup prefix minio/ keeps the name. Kept as the history of how MinIO and its claim-mode keyless access were laid out."
tags: [minio, s3, object-storage, workload-identity, terraform, component, history]
status: deprecated
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: infra-services
    resource: deployments/infrastructure/services.tf
  - id: app-storage
    resource: deployments/applications/storage.tf
  - id: app-secrets
    resource: deployments/applications/secrets.tf
---

# MinIO

**Superseded by [SeaweedFS](/components/seaweedfs.md).** One MinIO server
held every on-cluster bucket until the 2026-10-20 cutover. `minio-removal`
removed it the same day
([ADR 0018](/decisions/0018-remove-minio.md)): the `minio` job, its firewall
rule, root key, dashboard, alert, scrape job, `minio.lab` route and Consul
grant are gone, and the applications root dropped every `minio_*` resource
and `module.buckets` from state without destroying anything. The
`aminueza/minio` provider and `modules/bucket` are deleted.

**What remains.** Nothing on the cluster. `minio-volume-destroy` removed
`nomad_dynamic_host_volume.minio_data` from
`deployments/infrastructure/services.tf` on 2026-10-20, with the operator's
approval, and the apply deleted the volume (`cb07eebf`) and MinIO's last data
on orangepi4a. Everything durable was already in SeaweedFS and backed up in
GCS. Loki's and Tempo's 30 days from before the cutover, which the operator
chose not to migrate, and the frozen copies of the other buckets went with
it. Every old MinIO key in Vault, `default/minio/*` and
`default/<job>/minio`, was purged with all its versions. Only the GCS backup
prefix `minio/` keeps the name, so the backup history carries on
([GCS backups](/components/gcs-backups.md)).

Everything below is history: how MinIO was laid out and what bit people who
changed it. How a job gets keyless S3 access today is
`docs/explanation/workload-identity.md` ("Keyless SeaweedFS access").

## The pieces, as they were

| Piece | Where it was |
| --- | --- |
| Job `minio`, pinned to orangepi4a, `RELEASE.2025-09-07T16-13-09Z` | `deployments/infrastructure/services/minio.hcl` |
| Host volume `minio_data` (1 to 3.5 TiB), deleted in `minio-volume-destroy` | `deployments/infrastructure/services.tf` |
| Firewall: 9000 (S3) and 9001 (console) from `192.168.0.0/16` | `local.firewall_rules`, same file |
| Edge: `backend minio` (console) | `deployments/infrastructure/services/haproxy.hcl` |
| Root key: access key `minio`, secret `random_password.minio_secret_key` | KV `default/minio/localstack`, `deployments/infrastructure/secrets.tf` |
| OIDC targets `NOMAD` (claim mode) and `POC2` | env template in `minio.hcl` |
| Buckets, users, access keys | `local.buckets` in `deployments/applications/storage.tf` |
| Per-bucket policies and attachments | `deployments/applications/modules/bucket/main.tf` |
| Claim-mode policies `tempo`, `loki`, `registry` | `minio_iam_policy.*_wi` in `storage.tf` |

The applications root's `minio` provider found the server through Consul
(`data.consul_service.minio`) and logged in with the root key read
ephemerally from `default/minio/localstack`. So the infrastructure root
applied first, and the MinIO job had to be registered in Consul before the
applications root could plan.

The firewall rules for 9000 and 9001 were deleted on orangepi4a by hand,
because the Terraform `null_resource` that writes ufw rules cannot remove one
([the host firewall](/components/host-firewall.md)).

## Two kinds of policy, one namespace

Each entry in `local.buckets` became a bucket plus two policies from the
module, `<bucket>_read_write` and `<bucket>_read_only` (hyphens turned to
underscores), attached to the users listed as writers and readers. Every
listed user also got a `minio_accesskey`, and
`vault_kv_secret_v2.minio_credentials` wrote each key to
`default/minio/<user>`. A job that used its key read a second copy under its
own prefix (for example `default/openviking/minio`), because
`nomad-workloads` only grants a job its own path.

The claim-mode policies were different. MinIO applied the policy whose NAME
equalled the JWT's `nomad_job_id`, so `minio_iam_policy.tempo_wi` was named
`tempo` and had no attachment. Three rules followed:

- **The name is the grant.** Any MinIO policy whose name matched a job id
  granted that job, whatever it was meant for. That is why OpenViking's static
  key had no `openviking` policy beside it
  ([ADR 0007](/decisions/0007-openviking-static-key-has-no-claim-policy.md)).
- **Claim mode ignores the namespace.** A job with the same name in another
  Nomad namespace would have got the same policy (R9 follow-up). SeaweedFS
  closes this by matching `sub` as well
  ([ADR 0017](/decisions/0017-seaweedfs-keyless-roles-bound-per-job.md)).
- **The policies stayed out of the module** until a second pattern proved
  the shape.

## Who held a key

Tempo (R9), loki (R13) and the registry (R13, an AWS `credential_process`
helper, because it vendors aws-sdk-go v1) were keyless here until they moved
to [SeaweedFS](/components/seaweedfs.md) on 2026-10-20, the registry last.

R13 replaced two stubs that were never built. R10 (loki) had found a
config-only route: loki 3.4.2's `use_thanos_objstore` reaches thanos-io's S3
provider, which has a real `sts_endpoint` field. But that swaps loki's whole
storage client and moves its config block, which put the existing logs in
the `loki` bucket at risk. R11 (registry) had ruled config-only out, because
distribution v3.1.1 vendors aws-sdk-go v1, and found the Alpine-based image
could run a `credential_process` helper. R13 took R11's helper for both jobs,
so loki kept its storage client. R12 (memex) was dropped by the operator
when the stubs were written (`a7aa595`): memex takes its key as two explicit
settings in its own config, so going keyless needs a web-identity provider
and credential refresh in the memex repo, not a jobspec change.

Memex held a static key. Its job is still commented out, and its bucket and
key went with MinIO, so it needs a SeaweedFS bucket and key before it comes
back ([memex](/components/memex.md)). `backup-minio` read a copy of the ROOT
key until 2026-10-20. Every MinIO key in Vault, `default/<job>/minio` and
`default/minio/<user>`, was deleted in `minio-removal`, and
`minio-volume-destroy` purged every version of them.

## What bit people

- **Exactly one claim-mode target.** MinIO refused a second one
  (`errSingleProvider`), so `POC2` carried a `role_policy` naming
  `poc2-intentionally-undefined`, a policy that must never exist: MinIO's only
  principal check was `aud` against `client_id`, and a jobspec author picks
  their own `aud`. M1 first pointed it at `memex_read_write`, which handed
  `s3:*` on the memex bucket to anyone who asked.
- **Every configured discovery URL had to be live.** `LookupConfig` aborted
  the whole OIDC load if any one document failed to parse, so a placeholder
  took the `NOMAD` target down too.
- **The target was `NOMAD`, in capitals.** MinIO took the env var suffix
  verbatim.
- **Metrics were public.** `MINIO_PROMETHEUS_AUTH_TYPE="public"` let the
  Prometheus `minio` job scrape without a token, and served metrics to the
  whole LAN on 9000.
- **`loki`, `tempo`, `memex` and `mlflow-artifacts` never had an off-site
  copy.** Their MinIO data was on the `minio_data` volume only, and went with
  it in `minio-volume-destroy`.

## Evidence

Built or recorded from these, which a `sources` entry cannot point at:

- loop ticket `M1-minio-poc-service-account` (its plan and any verdicts are under `.loop/` at commit `48f52e2`, from before the `5b2ed1b` loop reset)
- loop ticket `R9-rollout-tempo-keyless-minio` (its plan and any verdicts are under `.loop/` at commit `48f52e2`, from before the `5b2ed1b` loop reset)
- loop ticket `R13-rollout-loki-registry-keyless-minio` (its plan and any verdicts are under `.loop/` at commit `48f52e2`, from before the `5b2ed1b` loop reset)
- loop ticket `R10-rollout-loki-keyless-minio`, a stub superseded by R13 (its plan is `.loop/plans/` at commit `48f52e2`, with the premise answered in `64c656e`)
- loop ticket `R11-rollout-registry-keyless-minio`, a stub superseded by R13 (its plan is `.loop/plans/` at commit `48f52e2`, with the premise answered in `64c656e`)
- loop ticket `R12-rollout-memex-keyless-minio`, a stub the operator dropped (its plan is `.loop/plans/` at commit `48f52e2`, dropped in `a7aa595`)
- commit `84b69a1`, the R13 plan that supersedes R10 and R11
- loop ticket `minio-removal` (its plan, spikes and verdicts are under `.loop/`)
- loop ticket `minio-volume-destroy` (its plan is `.loop/plans/minio-volume-destroy.md`)
