---
description: What the two nightly jobs copy to Google Cloud Storage, where their credentials come from, and how the GCS bucket is set up.
stale_after: 2027-01-19
sources:
  - resource: deployments/infrastructure/services/backup-postgres.hcl
  - resource: deployments/infrastructure/services/backup-minio.hcl
  - resource: deployments/infrastructure/storage.tf
  - resource: deployments/infrastructure/secrets.tf
  - resource: deployments/infrastructure/services.tf
  - resource: deployments/infrastructure/providers.tf
  - resource: deployments/infrastructure/variables.tf
---

# Nightly GCS Backup Jobs

Two Nomad periodic batch jobs copy cluster data off-site to Google Cloud
Storage: `backup-postgres` at 02:00 and `backup-minio` at 03:00, Europe/Amsterdam.

Without them, both datasets are on one disk each. PostgreSQL is on a host
volume pinned to `firebat` (`deployments/infrastructure/services.tf:13`) and
the MinIO `openviking`, `registry`, `models` and `datalake` buckets on `orangepi4a`
(`deployments/infrastructure/services.tf:33`), so a single node failure would
take one of them with it.

All GCS infrastructure (bucket, service account, IAM, key) is managed by
Terraform in `deployments/infrastructure/storage.tf`. There is no manual
`gcloud` setup.

## What this page does not cover

This page covers the write path: how backups are configured and run. It
is not a recovery runbook.

- **Restore is not documented here.** Nothing in this repository describes
  how to read a backup back, and no verified read-back is recorded. Treat the
  backups as unproven until someone restores one.
- **Run outcomes are not visible.** `nomad job status` shows both jobs
  registered and periodic, but the ACL denies the query that lists their
  child runs (`403 Permission denied`), so this page says what the jobs
  are configured to copy and does not claim any particular night succeeded.

## Architecture

### `deployments/infrastructure/`

The backup lifecycle spans three files, one per subsystem.

**Google Cloud resources** (`deployments/infrastructure/storage.tf`):
- `google_storage_bucket.backups`: bucket with a 180-day lifecycle delete rule
- `google_service_account.backup`: the `localstack-backup` service account
- `google_storage_bucket_iam_member.backup_writer`: grants `roles/storage.objectAdmin` on the bucket
- `google_service_account_key.backup`: JSON key (stored in Terraform state, written to Vault)

**Vault secrets** (`deployments/infrastructure/secrets.tf`, credentials scoped
per job):
- `backup_postgres_db_credentials` writes `default/backup-postgres/postgres`
  (copies root PG creds)
- `backup_postgres_gcs_credentials` writes `default/backup-postgres/gcs` (GCS
  service account JSON)
- `backup_minio_s3_credentials` writes `default/backup-minio/minio` (copies root
  MinIO creds)
- `backup_minio_gcs_credentials` writes `default/backup-minio/gcs` (GCS service
  account JSON)

**Nomad jobs** (`deployments/infrastructure/services.tf`): two `nomad_job`
resources templating the job specs below.

### `deployments/infrastructure/services/backup-postgres.hcl`

Periodic batch job, cron `0 2 * * *` (2:00 AM Europe/Amsterdam):
- **Task group** with two tasks sharing the `/alloc/data/` directory
- **Prestart task** (`pgdump`): uses `docker.io/library/postgres:18` image, runs `pg_dumpall | gzip` to `/alloc/data/pgdumpall-YYYY-MM-DD.sql.gz`
  - Vault template injects `PGUSER`/`PGPASSWORD` from `secret/data/default/backup-postgres/postgres`
  - Constrained to `radxa-dragon-q6a`, so it reads postgres over the network at `192.168.2.30`
  - Overrides entrypoint: `entrypoint = ["/bin/sh", "-c"]` (postgres image has `docker-entrypoint.sh` as ENTRYPOINT)
  - Resources: 500 MHz CPU, 512 MB memory
- **Main task** (`upload`): uses `docker.io/rclone/rclone:latest`, runs `rclone copy` to upload today's dump
  - Vault template writes GCS service account JSON to `secrets/gcs-key.json`
  - Uses on-the-fly backend syntax (`:gcs:`) with `--gcs-service-account-file` flag (no rclone.conf needed)
  - Overrides entrypoint: `entrypoint = ["/bin/sh", "-c"]` (rclone image has `rclone` as ENTRYPOINT)
  - Resources: 200 MHz CPU, 256 MB memory
  - No pruning step: the 180-day bucket lifecycle handles retention

### `deployments/infrastructure/services/backup-minio.hcl`

Periodic batch job, cron `0 3 * * *` (3:00 AM Europe/Amsterdam, staggered an
hour after the postgres job):
- **Single task** (`sync`): uses `docker.io/rclone/rclone:latest`, runs `rclone sync minio:<name> gcs:<bucket>/minio/<name>/` once for each of `openviking`, `registry`, `models` and `datalake`. Each sync runs even if an earlier one failed, and the task exits nonzero if any of them failed. Each sync passes `--create-empty-src-dirs --gcs-directory-markers`, because OpenViking stores a directory as a zero-byte key ending in `/` and rclone otherwise drops those keys without `rclone check` noticing. `loki` and `tempo` are not backed up: they keep 30 days and are rebuilt from new data.
- Two Vault templates:
  1. `secrets/rclone.conf`: rclone config with a `[minio]` remote (S3/Minio provider, creds from Vault) and a `[gcs]` remote (`service_account_file` pointing to the key file)
  2. `secrets/gcs-key.json`: GCS service account JSON from Vault
- Pinned to `radxa-dragon-q6a` by a node constraint, like
  `deployments/infrastructure/services/backup-postgres.hcl`
- `network_mode = "host"` for MinIO access
- Overrides entrypoint: `entrypoint = ["/bin/sh", "-c"]`
- Resources: 1000 MHz CPU, 512 MB memory

## Configuration

### `deployments/infrastructure/variables.tf`

Two variables:
- `gcp_project` (string): GCP project ID
- `gcs_backup_bucket` (string): GCS bucket name

### `deployments/infrastructure/vars/prod.tfvars`

```hcl
gcp_project       = "<your-gcp-project-id>"
gcs_backup_bucket = "<your-bucket-name>"
```

### `deployments/infrastructure/providers.tf`

The Google provider is `hashicorp/google ~>7.27.0`, authenticated via ADC.

## GCS path structure

```
gs://<bucket>/
  postgres/
    pgdumpall-2026-04-07.sql.gz
    pgdumpall-2026-04-08.sql.gz
    ...
  minio/
    openviking/
      <mirror of openviking bucket>
    registry/
    models/
    datalake/
```

- Postgres: dated dumps accumulate, and the bucket lifecycle rule deletes them after 180 days.
- MinIO: `rclone sync` maintains a live mirror (no accumulation: GCS matches the current bucket state). The 180-day rule deletes by age, so an object unchanged for 180 days, such as an old image layer, is deleted from GCS and uploaded again by the next nightly sync. For up to a day it has no off-site copy.

## See also

- [How to run a backup job on demand](../how-to/run-a-backup-job-on-demand.md)
- [How to apply a backup infrastructure change](../how-to/apply-a-backup-infrastructure-change.md)
- [Why each backup job has its own credentials](../explanation/backup-job-credentials.md)
