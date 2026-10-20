---
description: What the two nightly jobs copy to Google Cloud Storage, where their credentials come from, and how the GCS bucket is set up.
stale_after: 2027-04-20
sources:
  - resource: deployments/infrastructure/services/backup-postgres.hcl
  - resource: deployments/infrastructure/services/backup-s3.hcl
  - resource: deployments/infrastructure/services/restore-s3.hcl
  - resource: deployments/infrastructure/machine_roles.tf
  - resource: deployments/applications/storage.tf
  - resource: deployments/applications/secrets.tf
  - resource: deployments/infrastructure/storage.tf
  - resource: deployments/infrastructure/secrets.tf
  - resource: deployments/infrastructure/services.tf
  - resource: deployments/infrastructure/providers.tf
  - resource: deployments/infrastructure/variables.tf
---

# Nightly GCS Backup Jobs

Two Nomad periodic batch jobs copy cluster data off-site to Google Cloud
Storage: `backup-postgres` at 02:00 and `backup-s3` at 03:00, Europe/Amsterdam.

Without them, both datasets are on one disk each. PostgreSQL is on a host
volume pinned to `firebat` (`deployments/infrastructure/services.tf:13`) and
the SeaweedFS `openviking`, `registry`, `models` and `datalake` buckets on
`orangepi4a` (`deployments/infrastructure/services.tf:53`), so a single node
failure would take one of them with it.

`backup-s3` was called `backup-minio` until 2026-10-20, when MinIO was
removed. It still writes to the `minio/<bucket>/` prefixes in GCS, named
after the store it first backed up, so the backup history carries on. Its
first run under the new name exited 0.

A third job, `restore-s3`, runs only when dispatched. It copies one bucket's
GCS copy into SeaweedFS.

All GCS infrastructure (bucket, service account, IAM, key) is managed by
Terraform in `deployments/infrastructure/storage.tf`. There is no manual
`gcloud` setup.

## What this page does not cover

This page covers how backups are configured and run, and the job that
restores a bucket. It is not a recovery runbook.

- **Postgres restore is not documented.** Nothing in this repository reads a
  dump back, and no verified read-back is recorded. Bucket restores are
  proven: `restore-s3` brought `openviking` back into SeaweedFS on
  2026-10-20 with its tree and file hashes unchanged.
- **Run outcomes are not visible.** `nomad job status` shows both jobs
  registered and periodic, but the ACL denies the query that lists their
  child runs (`403 Permission denied`), so this page says what the jobs
  are configured to copy and does not claim any particular night succeeded.

## Architecture

### `deployments/infrastructure/`

The backup lifecycle spans four files, one per subsystem.

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
- `backup_s3_gcs_credentials` writes `default/backup-s3/gcs` (GCS service
  account JSON)
- `restore_s3_gcs_credentials` writes `default/restore-s3/gcs` (GCS service
  account JSON)

**Nomad jobs** (`deployments/infrastructure/services.tf`): three `nomad_job`
resources templating the job specs below.

**Nomad deploy policy** (`deployments/infrastructure/machine_roles.tf`): the
`deploy` policy carries `dispatch-job`, so its token can dispatch
`restore-s3`.

### `deployments/applications/`

The SeaweedFS keys of `backup-s3` and `restore-s3` come from this root,
where the SeaweedFS IAM provider is. The infrastructure root applies first, so
each job names its key's Vault path as a string, and on a rebuild from scratch
both fail until this root has applied:
- `storage.tf`: SeaweedFS user `backup`, with `s3:GetBucketLocation`,
  `s3:GetObject` and `s3:ListBucket` on the `openviking`, `registry`,
  `models` and `datalake` buckets, and user `restore`, with `s3:*` on the
  same four
- `secrets.tf`: `backup_s3_seaweedfs_credentials` writes
  `default/backup-s3/seaweedfs` and `restore_seaweedfs_credentials` writes
  `default/restore-s3/seaweedfs` (each user's key)

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

### `deployments/infrastructure/services/backup-s3.hcl`

Periodic batch job, cron `0 3 * * *` (3:00 AM Europe/Amsterdam, staggered an
hour after the postgres job):
- **Single task** (`sync`): uses `docker.io/rclone/rclone:latest`, runs `rclone sync seaweedfs:<name> gcs:<bucket>/minio/<name>/` once for each of `openviking`, `registry`, `models` and `datalake`. Each sync runs even if an earlier one failed, and the task exits nonzero if any of them failed. Each sync passes `--create-empty-src-dirs --gcs-directory-markers`, because OpenViking stores a directory as a zero-byte key ending in `/` and rclone otherwise drops those keys without `rclone check` noticing. `loki` and `tempo` are not backed up: they keep 30 days and are rebuilt from new data.
- Two Vault templates:
  1. `secrets/rclone.conf`: rclone config with a `[seaweedfs]` remote (S3/SeaweedFS provider, `http://192.168.2.29:8333`, read-only key from `default/backup-s3/seaweedfs`) and a `[gcs]` remote (`service_account_file` pointing to the key file)
  2. `secrets/gcs-key.json`: GCS service account JSON from
     `default/backup-s3/gcs`
- Pinned to `radxa-dragon-q6a` by a node constraint, like
  `deployments/infrastructure/services/backup-postgres.hcl`
- `network_mode = "host"` for SeaweedFS access
- Overrides entrypoint: `entrypoint = ["/bin/sh", "-c"]`
- Resources: 1000 MHz CPU, 512 MB memory

### `deployments/infrastructure/services/restore-s3.hcl`

Parameterized batch job, no schedule. Dispatch one run per bucket:

```
nomad job dispatch -meta bucket=<name> restore-s3
```

- **Single task** (`restore`): uses `docker.io/rclone/rclone:1.75.2`, then:
  1. Lists `gcs:<bucket>/minio/`. If `<name>/` is not there, the bucket was
     empty when backed up: it prints "nothing to restore" and exits 0.
  2. `rclone copy gcs:<bucket>/minio/<name>/ seaweedfs:<name>
     --create-empty-src-dirs --gcs-directory-markers --s3-directory-markers`
  3. `rclone check` between the two.
  4. Lists every directory under the GCS prefix and on SeaweedFS, and fails if
     any GCS directory is missing on SeaweedFS. `rclone check` alone passes
     with every directory marker missing.
- Exit codes, because the operator token cannot read alloc logs:

  | Code | Failed step |
  |---|---|
  | 0 | none, or nothing to restore |
  | 1 | the copy |
  | 2 | `rclone check` |
  | 3 | a GCS directory missing on SeaweedFS, or the SeaweedFS listing |
  | 4 | a GCS listing |
  | 5 | the bucket is not one of the four durable buckets (checked first) |

- Two Vault templates:
  1. `secrets/rclone.conf`: a `[seaweedfs]` remote (S3/SeaweedFS provider,
     `http://192.168.2.29:8333`, key from `default/restore-s3/seaweedfs`) and
     a `[gcs]` remote
  2. `secrets/gcs-key.json`: GCS service account JSON from
     `default/restore-s3/gcs`
- Pinned to `radxa-dragon-q6a`, `network_mode = "host"`
- No restarts and no rescheduling: a failed run stays failed
- Copies, does not sync: an object already in the SeaweedFS bucket that GCS
  lacks stays, and `rclone check` then fails the run. Restore into an empty
  bucket.
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
- Buckets: the prefix is still `minio/`, named after the store the job first backed up, though the source is SeaweedFS. `rclone sync` maintains a live mirror (no accumulation: GCS matches the current bucket state). The 180-day rule deletes by age, so an object unchanged for 180 days, such as an old image layer, is deleted from GCS and uploaded again by the next nightly sync. For up to a day it has no off-site copy.

## See also

- [How to run a backup job on demand](../how-to/run-a-backup-job-on-demand.md)
- [How to apply a backup infrastructure change](../how-to/apply-a-backup-infrastructure-change.md)
- [Why each backup job has its own credentials](../explanation/backup-job-credentials.md)
