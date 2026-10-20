---
description: Force the nightly Postgres or object storage backup job to run now, and check its logs and what landed in GCS.
stale_after: 2027-04-20
sources:
  - resource: deployments/infrastructure/services/backup-postgres.hcl
  - resource: deployments/infrastructure/services/backup-s3.hcl
---

# How to run a backup job on demand

## Introduction

`backup-postgres` runs nightly at 02:00 and `backup-s3` at 03:00. Use this to
run one now, without waiting for the schedule, and to check what it did.
`backup-s3` copies the SeaweedFS buckets. It was called `backup-minio` until
2026-10-20.

## Prerequisites

- A Nomad token, from `localstack login`.
- `gsutil`, authenticated to the GCP project that holds the backup bucket.

## Directions

### Step 1: Force a run

```bash
# Run now, without waiting for the nightly schedule
nomad job periodic force backup-postgres
nomad job periodic force backup-s3
```

### Step 2: Check registration and schedule

```bash
nomad job status backup-postgres
nomad job status backup-s3
```

### Step 3: Read the allocation logs

```bash
# backup-postgres, once you have an allocation ID
nomad alloc logs <alloc-id> pgdump
nomad alloc logs <alloc-id> upload

# backup-s3 has one task
nomad alloc logs <alloc-id> sync
```

Listing a job's child allocations requires a Nomad token with more privilege
than the default. Without it the query returns `403 Permission denied`, so the
`gsutil ls` commands in step 4 are the only check here that does not go
through Nomad at all.

### Step 4: Check what landed in GCS

```bash
# What actually landed in GCS
gsutil ls gs://<bucket>/postgres/
gsutil ls gs://<bucket>/minio/   # openviking/ openviking-v2/ registry/ models/ datalake/
```

The bucket copies keep the `minio/` prefix, named after the store the job
first backed up, so older and newer runs land in the same place.

They show what is in the bucket, not which run put it there: `nomad job
periodic force` writes a dump under today's date exactly as the 02:00 run
does, and `backup-s3` syncs the five buckets the same way the 03:00 run does.

## Additional resources

- [GCS backups reference](../reference/gcs-backups.md)
