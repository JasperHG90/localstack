---
type: verdict
title: 'Verdict: minio-removal plan-reviewer round 3'
description: 'plan-reviewer verdict for round 3 of minio-removal: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-19T20:51:47+00:00'
slug: minio-removal
pass: plan-reviewer
round: 3
body_schema: verdict/1
---

## Summary

The p3 fix holds. No open risk could break the plan.

## Checked

- Key order. Step 1A writes `default/backup-s3/seaweedfs` beside the old copy,
  so `backup-minio` keeps its key until step 2 replaces it. Step 2 moves the
  GCS key (`deployments/infrastructure/secrets.tf:376`, now
  `default/backup-minio/gcs`) to `default/backup-s3/gcs`, registers
  `backup-s3`, and purges `backup-minio`. Step 5 removes the old SeaweedFS
  path only after that. At no point does a registered backup job point at a
  missing key.
- Per-job Vault scoping is confirmed by the `secrets.tf:284` comment, so moving
  every key the job reads is the right fix. The jobspec (`backup-minio.hcl`)
  reads only the two keys passed in through `templatefile`.
- Purge: `nomad_job.backup_minio` (`services.tf:713`) sets no
  `purge_on_destroy`, so the explicit `nomad job stop -purge` is needed for the
  `nomad job status backup-minio` outcome. The plan now says so.
- Spikes 1 and 2 still settle the provider risk as recorded in round 2.

## Findings

- p1 (resolved): removed blocks with a dummy provider, backed by spikes 1 and 2.
- p2 (resolved): backup job renamed to backup-s3, GCS prefix kept.
- p3 (resolved): the SeaweedFS backup key is written under the new prefix in 1A, the job moves and the old one is purged in step 2, and the old key goes in step 5.

## Notes

Not findings. The builder will hit these when building:
- `backup_minio_s3_credentials` (`default/backup-minio/minio`, `secrets.tf:360`)
  references `random_password.minio_secret_key`, which step 2 deletes. If
  `seaweedfs-cutover` has not already removed that key, step 2 must remove it
  too, or `terraform validate` fails on the dangling reference.
- Renaming `nomad_job.backup_minio` to `backup_s3` makes Terraform deregister
  the old job in the same apply. The manual `-purge` then only clears the dead
  job from the list.
