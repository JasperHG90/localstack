# How to run a backup job on demand

## Introduction

`backup-postgres` and `backup-minio` run nightly. Use this to run one now,
without waiting for the nightly schedule, and to check what it did.

## Prerequisites

- A Nomad token, from `localstack login`.
- `gsutil`, authenticated to the GCP project that holds the backup bucket.

## Directions

### Step 1: Force a run

```bash
# Run now, without waiting for the nightly schedule
nomad job periodic force backup-postgres
nomad job periodic force backup-minio
```

### Step 2: Check registration and schedule

```bash
nomad job status backup-postgres
nomad job status backup-minio
```

### Step 3: Read the allocation logs

```bash
# Allocation logs, once you have an allocation ID
nomad alloc logs <alloc-id>        # pgdump task
nomad alloc logs <alloc-id> upload # upload task
```

Listing a job's child allocations requires a Nomad token with more privilege
than the default. Without it the query returns `403 Permission denied`, so the
`gsutil ls` commands in step 4 are the only check here that does not go
through Nomad at all.

### Step 4: Check what landed in GCS

```bash
# What actually landed in GCS
gsutil ls gs://<bucket>/postgres/
gsutil ls gs://<bucket>/minio/openviking/
```

They show what is in the bucket, not which run put it there: `nomad job
periodic force` writes a dump under today's date exactly as a 02:00 run does.

## Additional resources

- [GCS backups reference](../reference/gcs-backups.md)
