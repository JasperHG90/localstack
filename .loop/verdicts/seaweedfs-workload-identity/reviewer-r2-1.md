---
type: verdict
title: 'Verdict: seaweedfs-workload-identity reviewer round 2'
description: 'reviewer verdict for round 2 of seaweedfs-workload-identity: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T06:37:31+00:00'
slug: seaweedfs-workload-identity
pass: reviewer
round: 2
body_schema: verdict/1
---

## Summary

f2 is fixed: the registry now has a seaweedfs row. f1 is fixed too. The fix
added one new false claim. The paragraph under the table says "The last two
rows share a verifier", and the last two rows are now minio-poc2 and
seaweedfs. That needs a one-line fix, so the label is fix.

## Checked

- `loopctl gate stamp` from the worktree: pass pre_commit, pass cli_tests,
  pass eval-row r1, "stamp green:
  ea06296c375c08873e978fc234c8ced569a369353ddaa2c7355f286adb3af0db".
- docs/explanation/workload-identity.md: I read the diff (one added table
  row) and the registry section around it.
- cli/tests/test_seaweedfs_iam_config.py: the fixture now reads the STS
  secret name from secrets.tf and renders nomad_job.seaweedfs's own
  templatefile call from services.tf, with only the two resource references
  swapped for their paths. It fails if any other vault_kv_secret_v2
  reference is left.

## Findings

- f1 (resolved): the test takes the templatefile arguments from services.tf
  and checks that secrets.tf's `vault_kv_secret_v2.seaweedfs_sts` name gives
  the path the template reads. A drift in iam_members or in the STS path now
  reaches the assertions.
- f2 (resolved): docs/explanation/workload-identity.md:235 lists `seaweedfs`
  with SeaweedFS STS as its verifier and services.tf (`local.seaweedfs_iam`)
  as its source.
- f3 (docs, non-blocking): the row sits below `minio-poc2`, so the next
  paragraph's "The last two rows share a verifier" now points at minio-poc2
  and seaweedfs. Move the seaweedfs row above the two minio rows, or name
  them: "The `minio` and `minio-poc2` rows share a verifier".
