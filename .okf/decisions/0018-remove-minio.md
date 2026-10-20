---
type: decision
title: "ADR 0018: MinIO is removed without destroying its data"
description: "Once every consumer had moved to SeaweedFS, the MinIO job, its routes, monitoring and keys were deleted and its Terraform resources dropped from state with destroy = false, keeping the minio_data volume for the operator. Destroying the volume in the same step was rejected because it cannot be undone."
tags: [adr, decision, minio, seaweedfs, s3, object-storage, terraform]
generated:
  by: claude-opus/5.5
  at: 2026-10-20T00:00:00Z
status: stable
sources:
  - resource: "deployments/infrastructure/services.tf"
  - resource: "deployments/applications/storage.tf"
  - resource: "deployments/infrastructure/services/backup-s3.hcl"
---

# ADR 0018: MinIO is removed without destroying its data

## Context

MinIO is end of life, and its published image no longer downloads
([ADR 0016](/decisions/0016-seaweedfs-replaces-minio.md)). By 2026-10-20
every consumer had moved to SeaweedFS: OpenViking, Loki, Tempo, the registry,
the nightly backup, the `s3` Consul tag, the `s3.lab` route and the dash
tile. MinIO still ran with its data and used memory on orangepi4a that ov-dash
needed, and a reader had to ask which store was live.

The applications root's `minio` provider read its address from Consul and its
login from Vault, and its `minio_s3_bucket` resources had no
`force_destroy` while the buckets still held objects. A plain delete would
have made Terraform try to destroy buckets through a provider that was about
to lose its server.

## Decision

Remove MinIO and its Terraform state, and keep its data:

- The applications root drops every `minio_*` resource and `module.buckets`
  from state with `removed { lifecycle { destroy = false } }`, under a
  provider given static dummy values, then deletes the `removed` blocks and
  the `aminueza/minio` provider in a second commit with a clean plan.
- The infrastructure root deletes `nomad_job.minio`, its firewall entry, root
  key, dashboard, alert, scrape job and `minio.lab` route. The Consul deploy
  policy loses its `service "minio"` grant.
- The backup job is renamed `backup-s3`, with its keys under
  `default/backup-s3/`. Its GCS prefix stays `minio/`, so the backup history
  carries on.
- The `minio_data` host volume and the data on it stay.

Rejected: destroying the `minio_data` volume in the same step. It is the one
change that cannot be undone, and MinIO's `loki`, `tempo`, `memex` and
`mlflow-artifacts` buckets have no off-site copy. It is its own ticket,
`minio-volume-destroy`, which only the operator promotes.

## Consequences

- No MinIO job, provider, module or key is left in the code. The GCS prefix
  `minio/` and `nomad_dynamic_host_volume.minio_data` are the MinIO names that
  remain.
- The volume keeps its disk on orangepi4a until `minio-volume-destroy` runs.
- The ufw rules for 9000 and 9001 were deleted on orangepi4a by hand, because
  the Terraform `null_resource` that writes ufw rules cannot remove one.
- ov-dash, stopped to give SeaweedFS room, runs again.
- memex, still staged, needs a SeaweedFS bucket and key before its job is
  uncommented ([memex](/components/memex.md)).
