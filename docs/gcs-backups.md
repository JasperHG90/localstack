# Nightly GCS Backup Jobs

## Context

No off-site backups exist. PostgreSQL data lives on a single host volume on `firebat`, and the MinIO memex bucket lives on `orangepi4a`. A disk failure on either node means total data loss. This change adds two Nomad periodic batch jobs that back up to Google Cloud Storage nightly.

All GCS infrastructure (bucket, service account, IAM, key) is managed by Terraform in `backup.tf` -- no manual `gcloud` setup needed.

## Prerequisites

Authenticate with GCP before running `terraform apply`:

```bash
gcloud auth application-default login
```

This stores credentials at `~/.config/gcloud/application_default_credentials.json` which the Google Terraform provider picks up automatically.

On a headless machine (e.g. SSH):

```bash
gcloud auth application-default login --no-launch-browser
```

## Vault Policy Constraint

The Nomad workloads Vault policy (`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`) scopes secret reads to `secret/data/<namespace>/<job_id>/*`. This means each backup job needs its own copies of credentials under its job ID path. This is the same pattern used in the applications layer (e.g., memex gets its own copy of postgres creds).

## Architecture

### `deployments/infrastructure/backup.tf`

Manages the full GCS backup lifecycle in one file:

**Google Cloud resources:**
- `google_storage_bucket.backups` -- bucket with 180-day lifecycle delete rule
- `google_service_account.backup` -- `localstack-backup` service account
- `google_storage_bucket_iam_member.backup_writer` -- grants `roles/storage.objectAdmin` on the bucket
- `google_service_account_key.backup` -- JSON key (stored in Terraform state, written to Vault)

**Vault secrets** (credentials scoped per job):
- `backup_postgres_db_credentials` -> `default/backup-postgres/postgres` (copies root PG creds)
- `backup_postgres_gcs_credentials` -> `default/backup-postgres/gcs` (GCS service account JSON)
- `backup_minio_s3_credentials` -> `default/backup-minio/minio` (copies root MinIO creds)
- `backup_minio_gcs_credentials` -> `default/backup-minio/gcs` (GCS service account JSON)

**Nomad jobs:** two `nomad_job` resources referencing the HCL job specs below.

### `deployments/infrastructure/services/backup-postgres.hcl`

Periodic batch job running at 2:00 AM Europe/Amsterdam:
- **Task group** with two tasks sharing the `/alloc/data/` directory
- **Prestart task** (`pgdump`): uses `docker.io/library/postgres:18` image, runs `pg_dumpall | gzip` to `/alloc/data/pgdumpall-YYYY-MM-DD.sql.gz`
  - Vault template injects `PGUSER`/`PGPASSWORD` from `secret/data/default/backup-postgres/postgres`
  - Constrained to `firebat` (co-located with postgres, avoids network transfer)
  - Overrides entrypoint: `entrypoint = ["/bin/sh", "-c"]` (postgres image has `docker-entrypoint.sh` as ENTRYPOINT)
  - Resources: 1000 MHz CPU, 512 MB memory
- **Main task** (`upload`): uses `docker.io/rclone/rclone:latest`, runs `rclone copy` to upload today's dump
  - Vault template writes GCS service account JSON to `secrets/gcs-key.json`
  - Uses on-the-fly backend syntax (`:gcs:`) with `--gcs-service-account-file` flag (no rclone.conf needed)
  - Overrides entrypoint: `entrypoint = ["/bin/sh", "-c"]` (rclone image has `rclone` as ENTRYPOINT)
  - Resources: 500 MHz CPU, 256 MB memory
  - No pruning step -- 180-day bucket lifecycle handles retention

### `deployments/infrastructure/services/backup-minio.hcl`

Periodic batch job running at 3:00 AM Europe/Amsterdam (staggered):
- **Single task** (`sync`): uses `docker.io/rclone/rclone:latest`, runs `rclone sync minio:memex gcs:<bucket>/minio/memex/`
- Two Vault templates:
  1. `secrets/rclone.conf` -- rclone config with `[minio]` remote (S3/Minio provider, creds from Vault) and `[gcs]` remote (`service_account_file` pointing to the key file)
  2. `secrets/gcs-key.json` -- GCS service account JSON from Vault
- No node constraint (any node with network access to MinIO)
- `network_mode = "host"` for MinIO access
- Overrides entrypoint: `entrypoint = ["/bin/sh", "-c"]`
- Resources: 1000 MHz CPU, 512 MB memory

## Configuration

### `deployments/infrastructure/variables.tf`

Two variables:
- `gcp_project` (string) -- GCP project ID
- `gcs_backup_bucket` (string) -- GCS bucket name

### `deployments/infrastructure/vars/prod.tfvars`

```hcl
gcp_project       = "<your-gcp-project-id>"
gcs_backup_bucket = "<your-bucket-name>"
```

### `deployments/infrastructure/providers.tf`

Google provider added (`hashicorp/google ~>6.0.0`), authenticated via ADC.

## GCS Path Structure

```
gs://<bucket>/
  postgres/
    pgdumpall-2026-04-07.sql.gz
    pgdumpall-2026-04-08.sql.gz
    ...
  minio/
    memex/
      <mirror of memex bucket>
```

- Postgres: dated dumps accumulate and are automatically deleted after 180 days by the bucket lifecycle rule.
- MinIO: `rclone sync` maintains a live mirror (no accumulation -- GCS always matches current bucket state). Lifecycle rule serves as a safety net for orphaned objects.

## Verification

```bash
# Authenticate with GCP
gcloud auth application-default login

# Deploy (re-init needed first time to fetch google provider)
cd deployments/infrastructure
just init
just apply

# Force-run to test (don't wait for nightly schedule)
nomad job periodic force backup-postgres
nomad job periodic force backup-minio

# Check status
nomad job status backup-postgres
nomad job status backup-minio

# Check allocation logs
nomad alloc logs <alloc-id>        # pgdump task
nomad alloc logs <alloc-id> upload # upload task

# Verify GCS contents
gsutil ls gs://<bucket>/postgres/
gsutil ls gs://<bucket>/minio/memex/
```
