---
type: verdict
title: 'Verdict: seaweedfs-buckets reviewer round 2'
description: 'reviewer verdict for round 2 of seaweedfs-buckets: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T06:11:01+00:00'
slug: seaweedfs-buckets
pass: reviewer
round: 2
body_schema: verdict/1
---

## Summary

Both findings sent back are fixed. Readers now get exactly MinIO's read set,
the backup user alone adds ListBucket, and spike 4 shows that live. The two
.okf pages now name seaweedfs and the aws provider. One small docs slip
remains: the same change shifted `services.tf` by 10 lines, and two other
cites in deployment-layers.md now point at the wrong lines. That is a plain
fix, so the label is fix.

## Checked

- `loopctl gate stamp` from the worktree: pre_commit pass, cli_tests pass,
  eval-row r1 pass, stamp green
  52d0a0c681b57cb2fe8ac16eed4ea5734d260965a3adc0d6373e965921789ebd.
- `storage.tf:196-264`: `seaweedfs_read_actions` is
  `["s3:GetBucketLocation", "s3:GetObject"]`, the same as
  `minio_iam_policy.policy_read_only` in `modules/bucket/main.tf:38`.
  Writers get `["s3:*"]`, the same as `policy_read_write`. The new
  `seaweedfs_backup_actions` is the read set plus ListBucket and is used only
  in `aws_iam_user_policy.seaweedfs_backup`. The header comment matches.
- Spike seaweedfs-buckets/4 stdout: ducklake_reader and models_reader read
  but list=False and write=False. Writers read, list and write. Backup reads
  and lists all four durable buckets, cannot write, and is denied on loki.
  Every user is denied on another bucket. The README records 0 added,
  2 changed, and a clean second plan.
- Tests: `test_actions_match_minio` parses both action lists out of the
  MinIO module and compares them with the SeaweedFS locals, so drift on
  either side fails. `test_backup_actions_are_read_plus_list` pins the
  concat expression. This also covers f2.
- Docs: terraform-roots.md now says three services, matching
  `enable_consul_secrets.yml:49-57`. deployment-layers.md names four
  providers, and the cited ranges `providers.tf:48-94` and
  `services.tf:1-29` are right. The handoff rows name `default/seaweedfs/admin`,
  which infrastructure `secrets.tf:17` writes. seaweedfs.md's buckets section
  matches the code.

## Findings

- f1: resolved at `deployments/applications/storage.tf:200-202` and `:263`,
  backed by spike 4.
- f2: resolved by `test_actions_match_minio` in
  `cli/tests/test_seaweedfs_buckets.py`.
- f3: resolved in `.okf/components/terraform-roots.md:99-100` and
  `.okf/architecture/deployment-layers.md:160-171` and `:196-197`.
- f4: this change added 10 lines at the top of
  `deployments/applications/services.tf`. Two cites in
  `.okf/architecture/deployment-layers.md` were right on main and are now
  off by 10: `:198` cites `services.tf:34-46` for the OIDC client-creds
  reads, now at `44-56`, and `:295` cites `services.tf:383` for
  `nomad_job.registry`, now at `393`. Update both numbers.
