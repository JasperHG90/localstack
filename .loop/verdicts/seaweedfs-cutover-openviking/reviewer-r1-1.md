---
type: verdict
title: 'Verdict: seaweedfs-cutover-openviking reviewer round 1'
description: 'reviewer verdict for round 1 of seaweedfs-cutover-openviking: fail.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T07:19:43+00:00'
slug: seaweedfs-cutover-openviking
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The cutover worked. The live evidence shows OpenViking's tree and its 25
sampled hashes unchanged, empty directories included, and new writes landing
on SeaweedFS while MinIO stays flat. The keys, the IAM scope and the
OpenViking rewiring are correct. One defect blocks: the directory check that
the plan relies on, because `rclone check` misses lost markers, passes when
its GCS listing fails, since a pipe into `sort` hides rclone's exit status
(f1). `seaweedfs-cutover-registry` reuses this job, so fix it now. f2 is
non-blocking hardening.

## Checked

- `loopctl gate stamp` from the worktree: pass pre_commit, pass cli_tests,
  pass r1, pass r2, stamp green 8326dce2832e08654573112a78d1f2e5af4d9e0e810a25799a5f68b4d40f63c9.
- I read the change as `git diff --cached HEAD`. The worktree branches from
  93d4192, which is older than main, so `git diff --cached main` also shows
  main's seaweedfs-workload-identity work reversed. That is noise, not part of
  this change.
- restore-s3.hcl, read in full. I reproduced the pipe masking with
  `sh -c 'false | sort >/dev/null || exit 4; echo passed-through'`, which
  prints passed-through and exits 0.
- r1, tests/test_restore_s3.py: it checks the parameterized block, both marker
  flags plus the GCS one on the copy, `|| exit 1` and `|| exit 2`, the comm
  check with exit 3, and the key paths in both roots. It cannot see f1.
- r2: the restore user's policy uses `local.seaweedfs_write_actions` (`s3:*`)
  over `local.seaweedfs_durable_buckets`, and the test pins that set to the
  four durable buckets. The test also pins ov.conf.json and openviking.hcl to
  `$s3` and `default/openviking/seaweedfs`, and the endpoint to Consul
  `seaweedfs` on port 8333. No `openviking_minio_secret` is left.
- r3 (judgment), spike seaweedfs-cutover-openviking/3: the backup force ran
  with alloc 69dd293e and exited 0. Restores ran for models, datalake and
  openviking, each exit 0. models and datalake took the no-prefix path, which
  fits buckets that are empty today. `/ready` reports agfs ok. The 53-entry
  listing (11 empty dirs) and the 25 hashes match the 06:40 baseline. The
  SeaweedFS count went 47680 to 47682 while MinIO stayed at 45765. The
  API-level listing and hashes do not depend on the restore job's own
  listing, so f1 does not undo this evidence. r3 holds.
- Judged the two additions the plan did not name. `dispatch-job` on the
  deploy policy is fine: the policy already has `submit-job`, which can do
  more than dispatch. `--gcs-directory-markers` on every GCS-side read is
  right: the backup wrote markers with that flag, and reading without it
  could miss a directory that holds only a marker.
- Docs: gcs-backups (reference and okf), openviking (reference and okf),
  seaweedfs, minio, workload-identity, summary. They match the code, apart
  from the exit-code rows f1 names.

## Findings

- f1 (bug, blocking): two fixes would work. Write rclone's output to a file
  and then sort it as a separate step (`rclone lsf ... > /tmp/src-raw || exit 4`
  then `sort`), or add `set -o pipefail` (busybox ash supports it). Then add a
  test that fails when a listing feeds a pipe without either guard. Keep the
  exit-code table in the header and in docs/reference/gcs-backups.md true to
  whichever fix you choose.
- f2 (hardening, non-blocking): check `$b` against the four durable buckets
  before the GCS listing, and give that refusal its own exit code.

## Notes

- Merging this staged tree with current main conflicts in
  .okf/components/seaweedfs.md and .okf/log.md. main landed
  seaweedfs-workload-identity after this worktree branched. The code files
  merge cleanly, but whoever lands this must resolve the two doc conflicts.
- seaweedfs.md still says "Keyless access and the cutover come in later
  tickets". After the merge, keyless access has landed, so update that
  sentence while resolving the conflict.
