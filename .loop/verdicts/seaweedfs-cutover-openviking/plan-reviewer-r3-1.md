---
type: verdict
title: 'Verdict: seaweedfs-cutover-openviking plan-reviewer round 3'
description: 'plan-reviewer verdict for round 3 of seaweedfs-cutover-openviking: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-19T21:17:10+00:00'
slug: seaweedfs-cutover-openviking
pass: plan-reviewer
round: 3
body_schema: verdict/1
---

## Summary

Pass. The round-2 finding p4 is fixed. The one-way directory check has no
false failure on a GCS prefix with mixed marker history, and it fails when a
restore drops empty directories. No other risk I found could break the plan.

## Checked

- p4: I ran it with rclone v1.75.2 against SeaweedFS 4.48. An S3 bucket stood
  in for the GCS prefix, the way spike 2 and round 2 did it. I wrote a tree
  with two empty directories to the source using a plain sync, then a flagged
  sync, to copy the real backup history. Then I ran the plan's flagged
  `rclone copy` into a fresh bucket.
  - `rclone lsf -R --dirs-only` listed the same 6 directories on both sides,
    with and without `--fast-list`. That covers directories that exist only
    because files sit under them, and empty directories that exist only as
    markers. Nothing was missing on the target, so the check passes.
  - Negative case: an unflagged `rclone copy` into a second bucket. `rclone
    check` still passed (2 matching files), but the one-way diff named
    `a/b/deeper/` and `a/empty1/` as missing. So the check catches the
    failure spike 2 showed `rclone check` misses.
  - Resolved.
- p1 to p3 stay resolved: the plan text they rest on has not changed.

## Findings

- p1 (resolved): restore-s3 has its own GCS key and a write-capable `restore` user.
- p2 (resolved): spike 2 settles directory markers, and backup-durable-buckets adds the backup flags.
- p3 (resolved): the outcome reads baseline content back through AGFS.
- p4 (resolved): the one-way `lsf --dirs-only` check passes on a GCS prefix with mixed marker history and fails when a restore drops empty directories.

## Notes

These are not findings. They are for the builder:

- The stand-in source was SeaweedFS, which is filer-backed, so it lists
  directories whether or not markers exist. The real GCS side has not been
  tested: does rclone's GCS backend list a `/` marker object as a directory?
  If it does not, the source list would leave out empty directories and the
  one-way check would pass without checking them. Step 0's baseline `ls`,
  with empty directories included, still catches that, and MinIO is
  untouched until `minio-removal`, so OpenViking can be rolled back. One
  `rclone lsf -R --dirs-only` on the real GCS prefix after step 2 settles it.
- Round 2's notes still hold. The backup-durable-buckets change must be
  applied to the cluster before the forced run. Until seaweedfs-cutover,
  OpenViking's new writes have no off-site copy.
