# Why each backup job has its own credentials

The backup jobs read copies of the root PostgreSQL and MinIO credentials, and
each job reads its own copy of the GCS key. The paths are listed in the
[GCS backups reference](../reference/gcs-backups.md).

The Nomad workloads Vault policy
(`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`) scopes
secret reads to `secret/data/<namespace>/<job_id>/*`. Each backup job
therefore needs its own copies of credentials under its job ID path. This is
the same pattern the applications layer uses (memex gets its own copy of the
postgres credentials).
