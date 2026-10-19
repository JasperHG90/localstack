---
type: verdict
title: 'Verdict: seaweedfs-cutover plan-reviewer round 3'
description: 'plan-reviewer verdict for round 3 of seaweedfs-cutover: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-19T21:02:04+00:00'
slug: seaweedfs-cutover
pass: plan-reviewer
round: 3
body_schema: verdict/1
---

## Summary

p3 is fixed. The pre-apply rule now covers both kinds of one-way mismatch,
objects deleted on SeaweedFS after the restore (`--missing-on-dst`) and
objects rewritten there after it (`--differ`), and it says what to do with an
empty bucket that has no GCS prefix. No other risk I found would break the
plan.

## Checked

- `rclone check` takes `--missing-on-dst FILE` and `--differ FILE`, so the
  split the plan asks for is something rclone can actually do.
- The sibling tickets stop each consumer before `backup-minio` is forced and
  `restore-s3` runs (`seaweedfs-cutover-openviking` step 1,
  `seaweedfs-cutover-registry` step 1). `restore-s3`'s own `rclone check`
  proves GCS and SeaweedFS matched at restore. After that MinIO has no
  writer, so the nightly MinIO-to-GCS sync keeps GCS at the restored state.
  The GCS 180-day lifecycle only deletes and re-uploads identical objects.
  So any one-way mismatch at cutover time must come from a consumer writing
  to SeaweedFS, which is what the rule explains.
- Hash comparability between GCS and SeaweedFS is the same question
  `restore-s3` already answers with its own `rclone check`, so it does not
  add a new risk here.
- Nothing in round 2's checks changed: the remote-name regex in
  `cli/tests/test_backup_coverage.py`, the applications root as the only
  holder of the `minio` provider, and `memex.hcl` being commented out.

## Findings

- p1: resolved.
- p2: resolved.
- p3: resolved. The rule splits `--missing-on-dst` from `--differ`,
  explains each by the writing app, and treats a missing prefix of an empty
  bucket as nothing to check.

## Notes

- A deleted object has no SeaweedFS modtime, so the "check its modtime"
  part of the rule only applies to the `--differ` list. For `--missing-on-dst`
  the evidence is the writing app (registry GC, OpenViking deletes) and the
  fact that `restore-s3` proved equality at restore. A builder will read it
  that way; if not, the cost is a question to the operator, not a broken
  cutover.
