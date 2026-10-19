---
type: verdict
title: 'Verdict: seaweedfs-cutover-openviking plan-reviewer round 2'
description: 'plan-reviewer verdict for round 2 of seaweedfs-cutover-openviking: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-19T21:14:56+00:00'
slug: seaweedfs-cutover-openviking
pass: plan-reviewer
round: 2
body_schema: verdict/1
---

## Summary

Fail on one new finding, p4. The round-1 fixes hold. p1 (the restore keys),
p2 (directory markers) and p3 (a baseline read back through the bucket) are
resolved. p4 is a small revision: the restore job's marker-count check
compares an incrementally synced GCS prefix with a freshly copied bucket. Those
two hold different numbers of markers even when the restore is correct, so the
job fails every time on openviking.

## Checked

- p1: `default/backup-minio/gcs` sits in `deployments/infrastructure/secrets.tf`,
  so `default/restore-s3/gcs` follows an existing pattern. The seaweedfs-buckets
  plan puts the IAM provider and the backup user in the applications root and
  writes the key across roots, the same pattern the plan now uses for the
  `restore` user. The per-job key `default/openviking/seaweedfs` is in
  seaweedfs-buckets' `default/<job>/seaweedfs` scheme. Resolved.
- p2: I read spike 2's README, stdout and run.json (exit 0, 30 s, rclone
  v1.75.2, the deployed OpenViking image). With today's flags all 4 empty dirs
  were lost and `rclone check` still exited 0. With the chosen flags, 24 of 24
  views matched. The backup-durable-buckets worktree's `backup-minio.hcl`
  carries `--create-empty-src-dirs --gcs-directory-markers` on all four syncs.
  The backup goes straight from MinIO to GCS, and the spike covered MinIO as
  the source. The GCS backend itself went untested, and the spike says so.
  The marker check in the restore job is meant to catch a GCS failure, which
  is how p4 came up. Resolved.
- p3: `FSService.read` in the deployed image
  (`openviking/service/fs_service.py:593`) reads through
  `viking_fs.read_file`, which is AGFS, so the bucket and not Postgres
  `content`. So a baseline of content hashes read back through the API does
  test the restore. Resolved.
- p4: I reproduced it with rclone v1.75.2 against SeaweedFS 4.48, using an S3
  bucket as the GCS stand-in, the same way spike 2 did. A plain sync, then a
  flagged sync onto the same prefix, left 2 markers (`a/b/deeper/`,
  `a/empty1/`). A flagged copy of that prefix into a fresh bucket left 5
  (`a/`, `a/b/`, `a/b/deeper/`, `a/empty1/`, `c/`). In spike 2 the counts
  matched only because scenario c's stand-in bucket started empty.

## Findings

- p1 (resolved): restore-s3 now has its own GCS key in infrastructure secrets.tf and a write-capable `restore` user minted in the applications root.
- p2 (resolved): spike 2 settles directory markers, and backup-durable-buckets adds the backup flags.
- p3 (resolved): the outcome reads baseline content back through AGFS, so a broken restore fails it.
- p4 (premise): the restore job's GCS-against-SeaweedFS marker-count equality
  check fails against the real backup prefix, which was first written without
  marker flags. Only empty dirs gain markers there, while the fresh restore
  marks every directory. Check that every GCS marker exists in SeaweedFS, or
  compare the directory sets.

## Notes

Not findings, for the builder:

- The GCS backend's handling of `--gcs-directory-markers` on write and of `/`
  objects on read is still taken from the docs. Step 0's baseline `ls`
  (empty directories included) and a one-way marker check will catch a gap
  there at build time.
- Step 2 needs the backup-durable-buckets change applied to the cluster, not
  only merged, before the forced run. The plan already says so.
- The window from round 1 still holds: until seaweedfs-cutover, OpenViking's
  new writes on SeaweedFS have no off-site copy.
