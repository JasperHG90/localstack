---
type: verdict
title: 'Verdict: backup-durable-buckets reviewer round 1'
description: 'reviewer verdict for round 1 of backup-durable-buckets: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T04:45:23+00:00'
slug: backup-durable-buckets
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The jobspec change is correct and was proven live. It runs four syncs, each with `|| rc=1` and both marker flags, and ends with `exit $rc`. Every bucket is attempted, and any failure fails the task. The deployed run exited 0, and the per-key comparison shows all four buckets fully in GCS. What blocks a pass is consistency. The manifesto cites a renamed test and still calls I11 planned, and five other pages still say only openviking is backed up. These are plain text fixes, so none of them blocks.

## Checked

- Gates: I ran `loopctl gate stamp` from the worktree. Result: `pass gate pre_commit`, `pass gate cli_tests`, `pass eval-row r1`, `stamp green: d1abcc95545281d0d1e91e6a7616eab45c192b4572b41b109378c121e91e0217`. `tests/test_backup_coverage.py` reported 8 passed.
- r1: I read the tests. `test_minio_backup_syncs_the_durable_buckets` compares the sorted source list with the four names, so an extra bucket, a missing one or a duplicate fails it, and it checks that each destination prefix equals its source. `test_minio_backup_syncs_declared_buckets` checks each source against `local.buckets`. Each case in fails_when is asserted, within the limit in f3.
- r2 (judgment): `/bin/sh -c` runs four lines, each `rclone sync ... || rc=1`, with no `set -e` and no `&&`. A failed sync sets rc=1 and the next line still runs. `exit $rc` exits nonzero if any sync failed. `test_minio_backup_fails_when_any_sync_fails` pins `|| rc=1` on every line, `rc=0` and `exit $rc`. In templatefile, `$rc` without braces passes through unchanged, which the live run confirms. Met.
- r3 (judgment): allocation 8e84a792 ended complete with exit 0, recorded in the spike 2 and 3 READMEs. I read spike 3's `compare.py` and `stdout.txt`. For each bucket it lists both sides and compares every file key and size. It also checks that every MinIO directory key has a directory in GCS. Results: openviking 37,137 files and 836,331,631 B on both sides, registry 399 files and 5,340,847,012 B on both sides, models and datalake empty on both sides, with 0 missing, 0 differing and 0 directories lost. The check is one-way, but equal file counts on both sides rule out extra files in GCS. That is stricter than equal `rclone size` totals, so I accept it in place of the eight `rclone size` outputs. Object counts differ only because of directory markers, which the README explains. Met.
- r4 (judgment): `docs/reference/gcs-backups.md` lists the four buckets and says that an object unchanged for 180 days is deleted and uploaded again the next night. `.okf/components/gcs-backups.md` lists the four in its description and coverage section and keeps the 180-day trap for each `minio/<bucket>/` prefix. Met. Other pages fall short, see f1 and f2.
- Code read: the full diff and the full text of all five changed files, plus a grep of docs/ and .okf/ for backup claims that are now stale.

## Findings

- f1 (docs, non-blocking): manifesto I10 names `test_minio_backup_syncs_a_declared_bucket`, which no longer exists. I11 still says planned. The summary says the widening has not happened yet.
- f2 (docs, non-blocking): the 'Planned, not built' section and the 'safety net' quote in `.okf/components/gcs-backups.md` are now false. minio.md, container-registry.md, orangepi4a.md, the how-to's Step 4 prose and the components index still say only openviking is backed up.
- f3 (test-strength, non-blocking): a sync line outside the regex's exact shape escapes every check. Assert that every `rclone sync` or `rclone copy` in the args was parsed.

## Notes

Spike 3 found that registry got 725 directory markers in GCS that MinIO never had. A restore with `--s3-directory-markers` would create those keys in SeaweedFS. That belongs to the cutover ticket, but it would be worth a line in the gcs-backups traps so it does not live only in a spike.
