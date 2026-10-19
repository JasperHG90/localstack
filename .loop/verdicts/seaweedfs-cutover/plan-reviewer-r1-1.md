---
type: verdict
title: 'Verdict: seaweedfs-cutover plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of seaweedfs-cutover: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-19T20:56:35+00:00'
slug: seaweedfs-cutover
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

The approach holds. The verdict is fail on two contract findings: the
pre-apply `rclone check` gate and two outcome clauses cannot be met as
written. Neither one invalidates the plan.

## Checked

- `backup-minio.hcl` uses a bare `vault {}`, so
  `default/backup-minio/seaweedfs` is readable without a policy change.
- `_sole_tag_carrier` in `cli/src/localstack_cli/api/services.py` resolves
  `s3` only when one service carries the tag, so the tag has to leave
  `minio.hcl` in the same change that adds it to `seaweedfs`. "Moves" covers
  that.
- `cli/tests/test_backup_coverage.py` checks buckets against
  `deployments/applications/storage.tf`, which still declares them until
  `minio-removal`.
- The haproxy `s3` backend is the hardcoded `192.168.2.29:9000`, and the
  dash tile and the hardcoded Loki/Tempo endpoints are where the plan says.
- The plan lists no risks and cites no spikes. Spikes `seaweedfs-cutover/1-3`
  now belong to the registry ticket (it cites /3), and none is needed here.
  Nothing in this plan calls for a spike. The scope is broad but every item
  is mechanical, so no split is needed.

## Findings

- p1: the pre-apply `rclone check` must run one way, GCS to SeaweedFS. As
  written it fails every time, because the consumers wrote to SeaweedFS after
  the restore. The outcome "GCS count unchanged or higher" fails too when an
  app deleted an object after the switch.
- p2: "no job's rendered config names MinIO or port 9000" is false by
  design: `backup-minio`'s id and GCS prefix, the running `minio` job, and
  Prometheus's MinIO scrape all still name it.

## Notes

- The applications root still manages `minio_*` resources until
  `minio-removal`, so any `terraform plan` or `apply` there refreshes them
  through MinIO's S3 API. That includes this ticket's own dash change. Start
  the one-hour zero-request window after the last applications-root run.
- `.devcontainer/.env` gives the `mc` alias MinIO's own key
  (`AWS_ACCESS_KEY_ID=minio`, endpoint `192.168.2.29:9000`). Pointing the
  alias at SeaweedFS also needs a SeaweedFS key in that file, and the docs
  should say which one.
