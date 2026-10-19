---
type: plan
title: 'Plan: backup-durable-buckets'
description: Back up every durable MinIO bucket to GCS nightly, so the SeaweedFS migration restores from an off-site copy.
slug: backup-durable-buckets
epic: seaweedfs-migration
priority: 1
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T17:50:22+00:00'
---

# backup-durable-buckets

Relayed from: none

## Intent

MinIO is end of life and the cluster moves to SeaweedFS (epic
`seaweedfs-migration`). The operator chose to move data by backing it up to
GCS and restoring from there (2026-10-19), not by copying between the two
stores. Today the nightly job in
`deployments/infrastructure/services/backup-minio.hcl` syncs one bucket,
`openviking`. Every other bucket exists only on orangepi4a.

This ticket widens that job to the four durable buckets: `openviking`,
`registry`, `models` and `datalake`. Each syncs to
`gcs:${gcs_bucket}/minio/<bucket>/`, the prefix `openviking` already uses.
`loki` and `tempo` are left out because they keep 30 days and start empty on
SeaweedFS. `memex` and `mlflow-artifacts` are left out because the operator
chose to drop them.

Update `cli/tests/test_backup_coverage.py` from one expected bucket to the
set of four, keeping its check that every synced bucket is declared in
`deployments/applications/storage.tf`. Update
`docs/reference/gcs-backups.md` and `.okf/components/gcs-backups.md` to
match.

The GCS bucket deletes objects older than 180 days
(`deployments/infrastructure/storage.tf`). `rclone sync` uploads only changed
objects, so an unchanged model or image layer is deleted after 180 days and
uploaded again the next night. That is churn, not loss, while the job runs
nightly, and the cutover ticket runs a fresh sync right before it restores.
Say so in the docs page.

Outcome: after a deploy and one on-demand run of the job
(`docs/how-to/run-a-backup-job-on-demand.md`), the job exits 0. For
each of the four buckets, `rclone size` of the MinIO bucket and of its GCS
prefix report the same object count and total bytes. `just pre_commit` and
`uv run --directory cli pytest` pass.

## Could invalidate this plan

- Size. Nobody has measured how much data is in `registry`, `models` and
  `datalake` (the inventory found only the declared volume capacity, 1.0 to
  3.5 TiB). If it is hundreds of GB, the first sync may not finish in a
  nightly window on a 512 MB task, or GCS storage may cost more than the
  operator wants. The operator then has to pick which buckets are worth
  keeping, and the restore plan changes.
  Settled by `spike:backup-durable-buckets/1`: the four hold 6.18 GB
  (registry 5.34 GB in 399 objects, openviking 0.84 GB in 45,686 objects,
  models and datalake empty), about $0.12 a month on GCS. openviking's object
  count, not its bytes, sets the first sync's time.
