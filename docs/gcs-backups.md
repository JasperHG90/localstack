# Nightly GCS Backup Jobs

## Context

No off-site backups exist. PostgreSQL data lives on a single host volume on `firebat`, and the MinIO memex bucket lives on `orangepi4a`. A disk failure on either node means total data loss. This change adds two Nomad periodic batch jobs that back up to Google Cloud Storage nightly.

## Vault Policy Constraint

The Nomad workloads Vault policy (`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`) scopes secret reads to `secret/data/<namespace>/<job_id>/*`. This means each backup job needs its own copies of credentials under its job ID path. This is the same pattern used in the applications layer (e.g., memex gets its own copy of postgres creds).

## Files to Create

### `deployments/infrastructure/services/backup-postgres.hcl`

Periodic batch job running at 2:00 AM Europe/Amsterdam:
- **Task group** with two tasks sharing the `/alloc/data/` directory
- **Prestart task** (`pgdump`): uses `docker.io/library/postgres:18` image, runs `pg_dumpall | gzip` to `/alloc/data/pgdumpall-YYYY-MM-DD.sql.gz`
  - Vault template injects `PGUSER`/`PGPASSWORD` from `secret/data/default/backup-postgres/postgres`
  - Constrained to `firebat` (co-located with postgres, avoids network transfer)
  - Resources: 1000 MHz CPU, 512 MB memory
- **Main task** (`upload`): uses `docker.io/rclone/rclone:latest`, runs a shell script that:
  1. `rclone copy /alloc/data/ gcs:<bucket>/postgres/` -- uploads today's dump
  2. `rclone delete gcs:<bucket>/postgres/ --min-age 14d` -- prunes dumps older than 14 days
  - Vault template writes GCS service account JSON to `secrets/gcs-key.json`
  - Passes `--gcs-service-account-credentials` flag to both commands
  - Resources: 500 MHz CPU, 256 MB memory

### `deployments/infrastructure/services/backup-minio.hcl`

Periodic batch job running at 3:00 AM Europe/Amsterdam (staggered):
- **Single task** (`sync`): uses `docker.io/rclone/rclone:latest`, runs `rclone sync minio:memex gcs:<bucket>/minio/memex/`
- Two Vault templates:
  1. `secrets/rclone.conf` -- rclone config with `[minio]` remote (S3/Minio provider, creds from Vault) and `[gcs]` remote (service_account_file pointing to the key file)
  2. `secrets/gcs-key.json` -- GCS service account JSON from Vault
- No node constraint (any node with network access to MinIO)
- Resources: 1000 MHz CPU, 512 MB memory

## Files to Modify

### `deployments/infrastructure/variables.tf`

Add two variables:
```hcl
variable "gcs_service_account_json" {
  description = "GCS service account key JSON for backup uploads"
  type        = string
  sensitive   = true
}

variable "gcs_backup_bucket" {
  description = "GCS bucket name for backup storage"
  type        = string
}
```

### `deployments/infrastructure/secrets.tf`

Add 4 `vault_kv_secret_v2` resources:
- `backup_postgres_db_credentials` -> `default/backup-postgres/postgres` (copies root PG creds)
- `backup_postgres_gcs_credentials` -> `default/backup-postgres/gcs` (GCS service account JSON)
- `backup_minio_s3_credentials` -> `default/backup-minio/minio` (copies root MinIO creds)
- `backup_minio_gcs_credentials` -> `default/backup-minio/gcs` (GCS service account JSON)

### `deployments/infrastructure/services.tf`

Add 2 `nomad_job` resources:
```hcl
resource "nomad_job" "backup_postgres" {
  jobspec = templatefile("${path.module}/services/backup-postgres.hcl", {
    postgres_secret = vault_kv_secret_v2.backup_postgres_db_credentials.path
    gcs_secret      = vault_kv_secret_v2.backup_postgres_gcs_credentials.path
    postgres_host   = "192.168.2.30"
    gcs_bucket      = var.gcs_backup_bucket
  })
}

resource "nomad_job" "backup_minio" {
  jobspec = templatefile("${path.module}/services/backup-minio.hcl", {
    minio_secret = vault_kv_secret_v2.backup_minio_s3_credentials.path
    gcs_secret   = vault_kv_secret_v2.backup_minio_gcs_credentials.path
    minio_host   = "192.168.2.29"
    gcs_bucket   = var.gcs_backup_bucket
  })
}
```

### `deployments/infrastructure/vars/prod.tfvars`

Add bucket name (GCS key is passed via env var, never committed):
```hcl
gcs_backup_bucket = "<user-chosen-bucket-name>"
```

## GCS Path Structure

```
gs://<bucket>/
  postgres/
    pgdumpall-2026-03-25.sql.gz
    pgdumpall-2026-03-26.sql.gz
    ...
  minio/
    memex/
      <mirror of memex bucket>
```

- Postgres: dated dumps retained for 14 days, automatically pruned by the upload task via `rclone delete --min-age 14d`.
- MinIO: `rclone sync` maintains a live mirror (no accumulation -- GCS always matches current bucket state).

## GCS Setup Instructions (One-Time)

1. Create a GCS bucket:
   ```bash
   gcloud storage buckets create gs://<bucket-name> --location=<region>
   ```

2. Create a service account:
   ```bash
   gcloud iam service-accounts create localstack-backup \
     --display-name="Localstack Backup"
   ```

3. Grant Storage Object Admin on the bucket:
   ```bash
   gcloud storage buckets add-iam-policy-binding gs://<bucket-name> \
     --member="serviceAccount:localstack-backup@<project>.iam.gserviceaccount.com" \
     --role="roles/storage.objectAdmin"
   ```

4. Create and download JSON key:
   ```bash
   gcloud iam service-accounts keys create gcs-backup-key.json \
     --iam-account=localstack-backup@<project>.iam.gserviceaccount.com
   ```

5. Export for Terraform:
   ```bash
   export TF_VAR_gcs_service_account_json=$(cat gcs-backup-key.json | jq -c .)
   ```

## Verification

```bash
# Deploy
cd deployments/infrastructure && just apply

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
