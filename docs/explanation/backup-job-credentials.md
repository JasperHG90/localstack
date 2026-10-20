---
description: Why each backup job reads its own copy of the PostgreSQL, SeaweedFS and GCS credentials under its own job path.
stale_after: 2027-04-20
sources:
  - resource: bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2
  - resource: deployments/infrastructure/secrets.tf
  - resource: deployments/infrastructure/services/backup-postgres.hcl
  - resource: deployments/infrastructure/services/backup-s3.hcl
  - resource: deployments/applications/secrets.tf
---

# Why each backup job has its own credentials

`backup-postgres` reads a copy of the root PostgreSQL credential.
`backup-s3` reads a read-only SeaweedFS key at
`default/backup-s3/seaweedfs`, which the applications root writes. Each job
reads its own copy of the GCS key. The paths are listed in the
[GCS backups reference](../reference/gcs-backups.md).

The Nomad workloads Vault policy
(`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`) scopes
secret reads to `secret/data/<namespace>/<job_id>/*`. Each backup job
therefore needs its own copies of credentials under its job ID path. This is
the same pattern the applications layer uses (memex gets its own copy of the
postgres credentials).

It also means renaming a job moves its secrets. When `backup-minio` became
`backup-s3` on 2026-10-20, both its keys moved to `default/backup-s3/`, and
the old paths were deleted once the old job was gone.
