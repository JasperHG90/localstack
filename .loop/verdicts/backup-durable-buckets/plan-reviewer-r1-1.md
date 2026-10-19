---
type: verdict
title: 'Verdict: backup-durable-buckets plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of backup-durable-buckets: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-19T17:55:11+00:00'
slug: backup-durable-buckets
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

Round 1. No open risk breaks this plan. The one listed risk, size, is settled
by spike:backup-durable-buckets/1, and the claims the plan rests on hold
against the repo.

## Checked

- Size risk: spike:backup-durable-buckets/1 shows the four durable buckets
  hold 6.18 GB. registry has 5.34 GB in 399 objects, openviking has 0.84 GB in
  45,686 objects, and models and datalake are empty. That is a small first
  sync for a 512 MB rclone task. The same task already syncs openviking, the
  bucket with the most objects, every night. The cost is negligible. The
  evidence answers the risk.
- All four buckets are keys of `local.buckets` in
  deployments/applications/storage.tf, so the test's check that each synced
  bucket is declared still holds when it widens to a set.
- Root MinIO key: secrets.tf `backup_minio_s3_credentials` copies the root
  credential. This helps the plan. Root can read every bucket, so widening the
  sync needs no new MinIO policy or key. A read-only key would be hardening
  outside this ticket, and the cutover ticket replaces this credential for
  SeaweedFS anyway.
- GCS bucket (deployments/infrastructure/storage.tf) has a 180-day age Delete
  rule and no versioning. `rclone sync` finds an aged-out object missing and
  uploads it again, as the plan says. The gap is at most one night. The
  seaweedfs-cutover plan runs a fresh sync and stops writers before it
  restores, so the gap cannot lose data at restore time.
- The service account has roles/storage.objectAdmin on the bucket, which
  covers writes under new `minio/<bucket>/` prefixes.
- docs/reference/gcs-backups.md, .okf/components/gcs-backups.md and
  docs/how-to/run-a-backup-job-on-demand.md exist. test_backup_coverage.py
  pins the jobspec's `rclone sync` line and the doc section. Its
  `re.search` finds only the first sync, so the build has to change the
  parsers together with the jobspec. That is build work, not a plan risk.

## Findings

None.

## Notes

- Left to the build: how the four syncs chain in the shell. `&&` stops at the
  first failure, and `;` hides failures from the exit code. The build has to
  pick a form where any failed sync still fails the job.
- The outcome's `rclone size` comparison can be off by a few objects if
  openviking or registry gets writes during the run.
- The eval has no rows yet. The Outcome paragraph is a checkable definition
  of done to write them from.
