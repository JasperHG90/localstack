---
type: verdict
title: 'Verdict: seaweedfs-cutover-openviking reviewer round 3'
description: 'reviewer verdict for round 3 of seaweedfs-cutover-openviking: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T07:35:21+00:00'
slug: seaweedfs-cutover-openviking
pass: reviewer
round: 3
body_schema: verdict/1
---

## Summary

f3 and f4 are fixed. Both pages name exit 5, and the branch now sits on
f86fe61. main has moved on since, but only by this ticket's own loop commits
under .loop/. The resolved .okf pages are true to the code. One slip from the
merge is left: in orangepi4a.md the new OpenViking paragraph splits a bullet
list in two (f5). It is a plain fix and does not block.

## Checked

- `loopctl gate stamp` from the worktree: pass pre_commit, pass cli_tests,
  pass r1, pass r2, stamp green
  9d9f7c95acb9469b0ab1bee1dece72a2bf32538401eb59dc37a33491fa607721.
- Base: merge-base HEAD main is f86fe61. `git diff f86fe61 main` touches
  only .loop/ files for this ticket (lifecycle, findings, stamps,
  reviewer-r3.json). `git diff --cached f86fe61` shows 25 files, all of them
  this ticket's work. None of the observability files are reverted now.
- f3: docs/reference/gcs-backups.md now has a row for 5 ("checked first"),
  and .okf/components/gcs-backups.md says "5 a bucket other than the four
  durable ones, checked first". Both match the `case` arm in restore-s3.hcl
  lines 52 to 55, which runs before any rclone call.
- f4: I read the diffs of the five conflicted pages against f86fe61.
  seaweedfs.md: OpenViking, the models and datalake restores, and Loki and
  Tempo are all there, along with the restore user and its Vault path
  (`default/restore-s3/seaweedfs`, which matches secrets.tf). host-volumes.md:
  "four durable MinIO buckets", and OpenViking blobs in SeaweedFS. log.md:
  the new entry sits beside the observability entry and does not replace it.
  summary.md: both cutovers are named, and the closing line now limits "no
  restore test" to the Postgres dump. orangepi4a.md: `restore-s3`'s
  `seaweedfs_host` really is the literal `192.168.2.29`
  (infrastructure/services.tf:820). OpenViking really does take its S3
  endpoint from `data.consul_service.seaweedfs` (applications/services.tf:485).
  So the claims hold, but see f5.

## Findings

- f1 (resolved): unchanged since round 2. The listings write to files with
  their own exit guards.
- f2 (resolved): unchanged since round 2. The case allowlist exits 5.
- f3 (resolved): exit 5 is in the reference table and on the component page,
  as described under Checked.
- f4 (resolved): rebased onto f86fe61, and the five .okf conflicts each cover
  both cutovers.
- f5 (docs, non-blocking): in .okf/nodes/orangepi4a.md the paragraph
  "OpenViking also takes its S3 address from `data.consul_service.seaweedfs`
  and names no literal." lands between the `backup-minio` bullet and the
  "HAProxy's `minio`, `s3` and `ovdash` backends" bullet. That ends the list
  early and leaves HAProxy as a one-item list under a paragraph about
  OpenViking. Move the paragraph below the last bullet.

## Notes

- The f3 ask also covered mentioning the SeaweedFS listing under exit 3 on the
  component page. .okf/components/gcs-backups.md still says only "3 a
  directory missing on SeaweedFS". The reference page and the job header
  both say "or its listing". You could add those words when you fix f5. This
  is not a separate finding.
