---
type: verdict
title: 'Verdict: seaweedfs-cutover-observability reviewer round 1'
description: 'reviewer verdict for round 1 of seaweedfs-cutover-observability: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T07:16:50+00:00'
slug: seaweedfs-cutover-observability
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The cutover is correct and live. Loki and Tempo log in to SeaweedFS with the
`seaweedfs` audience and their own role ARNs, find it through
`data.consul_service.seaweedfs`, and no longer name 192.168.2.29:9000. MinIO is
untouched and its buckets are flat. One defect: two of the twelve dashboard
panels query a metric name that does not exist, so they render empty. That is
a plain rename at lines 236 and 438, so I am not asking to see it again.

## Checked

- Gates, run by me from the worktree with `loopctl gate stamp`: pass
  pre_commit, pass cli_tests, pass r1, pass r2, "stamp green:
  08b8449941a125d1f56f853685509f448e29701f605bcbfaf57a0c9591bd83cd".
- Code read in full: loki.hcl, tempo.hcl, applications services.tf (the new
  `s3_host` from `data.consul_service.seaweedfs`, which exists at line 6),
  grafana.hcl, infrastructure services.tf, alert-rules.yaml, seaweedfs.json and
  the new test. The loki and tempo roles in `local.seaweedfs_iam` grant `s3:*`
  on their own bucket, so Loki's compactor can delete for 30-day retention.
  Dropping `depends_on = [minio_iam_policy.*_wi]` is right because the roles
  are in the other root. The rollback keys that the new comments name,
  `default/{loki,tempo}/seaweedfs`, exist (`vault_kv_secret_v2.seaweedfs_credentials`).
  tempo.hcl now goes through `templatefile` with a variable. It contained no
  `${` before (it ran with `{}`), so nothing else gets interpolated.
- r1: the test checks audience and JWT path in the identity block, that the
  literal address is gone and `${s3_host}:8333` is present, RoleArn and
  RoleSessionName inside loki's STS URL, and tempo's AWS_ROLE_ARN. Every
  `fails_when` clause would turn it red.
- r2: the test pulls the ScrapeJobMissing expression and checks that it has
  both `seaweedfs` and `minio`, that both dashboard files exist, that the
  SeaweedFS and MinIO alert uids are present, and that grafana.hcl renders
  the dashboard. That matches `fails_when`.
- r3 (judgment): the spike recorded both deployments successful, tempo
  going 86 to 98, and MinIO flat at 13581 and 6502. In its two-minute window
  loki stayed at 7, so I took my own listing at 07:14:31 UTC and got loki 8,
  tempo 106, and MinIO still 13581 and 6502. Both SeaweedFS buckets are
  growing and MinIO is not. The spike recorded Grafana returning 1866 log
  lines and 5 traces for the 10 minutes after the switch, and the rules
  loaded with health=ok. I queried Prometheus through Grafana for every
  dashboard metric. `up`, disk_error_status, volumes, bucket_size_bytes,
  in_flight, request_total, request_seconds and both traffic series exist.
  `SeaweedFS_s3_bucket_object` does not (f1). The disk-error alert's metric
  exists and reads 0.
- Docs: the okf and docs edits match the code: the role and audience,
  `local/s3-creds.sh`, the static keys, the dashboard count of 14, eleven
  ScrapeJobMissing jobs, registry as the only MinIO keyless job still holding
  `depends_on` (services.tf:390), and orangepi4a's list of hand-written
  addresses.

## Findings

- f1: in `seaweedfs.json`, the "Objects" (line 236) and "Bucket objects"
  (line 438) panels query `SeaweedFS_s3_bucket_object`. Prometheus has
  `SeaweedFS_s3_bucket_object_count` (listed through
  `/api/v1/label/__name__/values`), so both panels are empty. The fix is to
  rename the metric in both expressions and re-apply Grafana. Non-blocking
  because the fix is a plain rename.

## Notes

The Grafana apply also delivered two OpenViking alert rules that were on main
but had never been applied. That is outside this diff and does no harm.
