---
type: verdict
title: 'Verdict: seaweedfs-service reviewer round 2'
description: 'reviewer verdict for round 2 of seaweedfs-service: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T05:45:34+00:00'
slug: seaweedfs-service
pass: reviewer
round: 2
body_schema: verdict/1
---

## Summary

f1 and f3 are fixed, and f2 is resolved as well. One new non-blocking
finding, f4: the restart step in the minio-removal plan names a command
that does not start a stopped job. The other option on the same line, an
applications-root apply, does start it, and step 1A applies that root
before step 6 anyway. So the outcome still holds, but the wording should
be corrected.

## Checked

- Gates: I ran `loopctl gate stamp` from the worktree myself: `pass gate
  pre_commit`, `pass gate cli_tests`, `pass eval-row r1`, `stamp green:
  1b9c6ca89fa6a0d8a4f070ba967a60af4541696a701fcabca0fedf2ef75c1f47`.
- f1: `.okf/components/ov-dash.md` has a new section that says when and why
  ov-dash stopped, that it holds no state, that minio-removal restarts it,
  and that applications-root applies in the meantime queue it. The
  orangepi4a jobs table marks the row stopped until minio-removal, adds the
  seaweedfs row, and adds a quirk entry. `.okf/components/seaweedfs.md`
  agrees. The minio-removal plan (main checkout) has step 6 and an outcome
  bullet saying ov-dash runs healthy and answers on its route. That is the
  documented-handoff option from round 1, not the Terraform option, which
  is fine.
- f3: the summary line now says SeaweedFS runs beside MinIO and is replacing
  it, and notes that ov-dash is stopped.
- f2: `test_master_toml_is_mounted_where_weed_reads_it` asserts both the
  template destination and the exact volume mount string.

## Findings

- f1 (resolved): recorded in ov-dash.md, orangepi4a.md, seaweedfs.md and
  minio-removal step 6 plus its outcome bullet.
- f2 (resolved): the mount test is at cli/tests/test_seaweedfs_jobspec.py:58.
- f3 (resolved): .okf/summary.md has been updated.
- f4 (docs, non-blocking): `nomad job eval` on a stopped job asks the
  scheduler to evaluate a job whose desired state is stopped, so it places
  nothing. Step 6 should say to re-register the job (an applications-root
  apply, or `nomad job run`). If step 1A's apply has already re-registered
  it, the queued allocation places by itself once MinIO's memory is freed.
  This is a plain wording fix and does not need another review.

## Notes

The ov-dash.md text calls a re-registered ov-dash a queued allocation, and
that matches how Nomad blocks an eval that cannot place. The SSH host-key
note from round 1 is now a quirk entry on the orangepi4a page.
