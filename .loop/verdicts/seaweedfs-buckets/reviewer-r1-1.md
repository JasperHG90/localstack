---
type: verdict
title: 'Verdict: seaweedfs-buckets reviewer round 1'
description: 'reviewer verdict for round 1 of seaweedfs-buckets: fail.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T06:05:36+00:00'
slug: seaweedfs-buckets
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The change mostly works. The six buckets, the user derivation from
`local.buckets`, the Vault paths, the Consul grant and the backup user's
read-only scope are right, and the live evidence in spike 3 backs r2 and r3.
One contract gap blocks: bucket readers gain `s3:ListBucket`, which MinIO
does not give them, and r1 counts that as a failure. The r1 test cannot
catch it, and two .okf pages now say false things about the deploy policy
and the provider set.

## Checked

- `loopctl gate stamp` from the worktree: pre_commit pass, cli_tests pass,
  eval-row r1 pass, stamp green
  0b81e29cf780547709588d7d98c0e1d3de8ac4390fe363c6b385e0b982d2ee2b.
- Read the full diff against main (excluding `.loop/`) and all of
  `deployments/applications/storage.tf` and `modules/bucket/main.tf` to
  compare grants. Writers: `s3:*` on bucket and `bucket/*`, same as MinIO's
  read_write. Readers: MinIO has GetBucketLocation and GetObject. SeaweedFS
  has those plus ListBucket.
- r1: ran a mutation in a scratch copy (write actions set to
  `["s3:GetObject"]`). All 8 tests still pass. The bucket-set and
  backup-scope checks do assert their part of `fails_when`.
- r2 (judgment): spike seaweedfs-buckets/3 stdout shows the admin key lists
  exactly the six buckets, every user is denied on another bucket, readers
  and backup are refused writes, and backup reads all four durable buckets
  and is denied on loki. The README records 38 added and a clean second
  plan. I accept that as evidence for r2. It also shows readers can list,
  which is f1.
- r3 (judgment): the playbook grant is at
  `bootstrap/playbooks/enable_consul_secrets.yml:52-54`. `secrets.tf` writes
  new resources at `default/<job>/seaweedfs` for loki, tempo, registry and
  openviking (the user names match the job ids), and
  `default/backup-minio/seaweedfs`. The MinIO resources are untouched, and
  the spike shows both keys present at each prefix. r3 holds.
- `.terraform.lock.hcl` is gitignored under `deployments/`, so its absence
  from the diff is expected.
- The ov-dash corrections in seaweedfs.md and ov-dash.md match the spike's
  side finding.

## Findings

- f1: `seaweedfs_read_actions` is shared by bucket readers and the backup
  user. The backup user needs ListBucket to copy a bucket, but
  ducklake_reader and models_reader did not have it on MinIO. Either give
  bucket readers MinIO's set (GetBucketLocation, GetObject) and keep
  ListBucket for backup only, or record the widening as a decision the
  operator accepts and change r1. A careless fix that drops ListBucket from
  the shared local would break the backup's listing, so the fix and a
  re-run of the live check come back for review.
- f2: `test_users_keep_their_minio_split` checks only that the
  comprehension names `local.seaweedfs_write_actions` and
  `local.seaweedfs_read_actions`, not what those hold. Pin writer actions
  to `["s3:*"]` and reader actions to MinIO's read-only set, best by parsing
  them from `modules/bucket/main.tf` so drift on either side fails.
- f3: `.okf/components/terraform-roots.md:99` ("exactly two services") and
  `.okf/architecture/deployment-layers.md:160-166` and `:195` predate the
  seaweedfs grant and the aws provider. Update them to name seaweedfs and
  the fourth provider, and fix the cited line range.
