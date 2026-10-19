---
type: verdict
title: 'Verdict: seaweedfs-cutover plan-reviewer round 2'
description: 'plan-reviewer verdict for round 2 of seaweedfs-cutover: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-19T21:00:49+00:00'
slug: seaweedfs-cutover
pass: plan-reviewer
round: 2
body_schema: verdict/1
---

## Summary

Both round-1 findings are fixed. One new contract gap of the same kind keeps
the verdict at fail. The pre-apply rule covers objects deleted after the
restore, but not objects overwritten after it. The registry overwrites tag
links on every repeat push, so the gate as written will stop the operator.
The fix is a one-line change to the rule. The approach still holds.

## Checked

- `backup-minio.hcl` today runs a single `rclone sync` for `openviking`.
  `backup-durable-buckets` widens it to four buckets, and this ticket depends
  on it through `seaweedfs-cutover-openviking`. `test_backup_coverage.py`
  parses `rclone sync minio:` and the `gcs:${gcs_bucket}/minio/<b>/` prefix,
  so changing the remote name means changing that regex, as the plan says.
- The outcome check `rclone check seaweedfs:<b> gcs:.../minio/<b>/` after the
  sync: sync makes the destination match the source, so it passes unless a
  consumer writes between the sync and the check. A rerun clears that, so it
  is not a finding.
- The applications root is the only root with the `minio` provider
  (`deployments/applications/providers.tf`), so counting the one-hour window
  from the last run of that root is enough.
- `.devcontainer/.env.example` has `MINIO_*` keys today, and
  `bootstrap.sh` reads `AWS_*`. The plan's note on which SeaweedFS key the
  alias uses fixes the gap I raised in round 1.
- `memex.hcl` still points at `${minio_host}:9000`, but its `nomad_job` is
  commented out, so it does not break the "no S3 client at MinIO" outcome.

## Findings

- p1: resolved.
- p2: resolved.
- p3: open. The pre-apply rule must also cover objects overwritten after
  the restore, not only deleted ones.

## Notes

- `models` and `datalake` are empty (`spike:backup-durable-buckets/1`), so
  their GCS prefixes may not exist. rclone can report "directory not found"
  for a missing root and exit non-zero. `restore-s3` in
  `seaweedfs-cutover-openviking` runs the same check on the same buckets
  first, so whatever that ticket learns applies here. Building will answer
  it, so it is not a finding.
