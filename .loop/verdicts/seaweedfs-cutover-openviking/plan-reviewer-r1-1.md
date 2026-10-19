---
type: verdict
title: 'Verdict: seaweedfs-cutover-openviking plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of seaweedfs-cutover-openviking: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-19T21:00:56+00:00'
slug: seaweedfs-cutover-openviking
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

Fail. The approach holds, but the plan needs three revisions. p1: the restore key and its Vault paths in both roots are not in scope. p2: a spike must show that a bucket restored through rclone works for OpenViking. p3: the outcome passes even when the restore is broken.

## Checked

- Risk 1 is settled by spike:seaweedfs-cutover-openviking/1. README, stdout and run.json show 28/28 passes with the prod S3 settings on SeaweedFS 4.48, using a key scoped to openviking. The bucket was fresh, not restored (see p2).
- spike:backup-durable-buckets/1: openviking 0.84 GB in 45,686 objects, models and datalake empty.
- seaweedfs-buckets plan: it mints consumer keys and a read-only backup key only (p1).
- Infrastructure secrets.tf and services.tf: Vault paths are per job (default/backup-minio/gcs). backup-minio.hcl uses default rclone flags.
- openviking.hcl and ov.conf.json: vectors and content live in Postgres (store_content true), and the host volume holds working state. Stopping the job before the final backup keeps Postgres and the bucket in step, and AGFS paths do not change.

## Findings

- p1 (missing): no ticket mints restore-s3's write key or its Vault paths.
- p2 (premise): the client spike did not cover a bucket restored from GCS. Directory markers and empty dirs may be lost. Needs a spike.
- p3 (test-mismatch): a search can pass from Postgres alone, so it does not prove the restore. Capture a baseline and read old content through AGFS.

## Notes

The approach holds. Stopping OpenViking, then forcing a fresh backup-minio run, then restoring keeps
Postgres (vectors, deltas) and the bucket in step. The host volume on radxa is working state, not the
store, and the restore keeps the AGFS paths the same, so URIs in Postgres still resolve. Risk 1 (client
compatibility) is settled by the spike's 28/28 run with prod settings. The spike sizes (openviking 0.84 GB
in 45,686 objects, models and datalake empty) make the restore cheap.

The three findings are revisions, not a rethink. p1 is scope: the restore key and its Vault paths in
both roots. p2 needs a spike before building. p3 is the contract.

Not findings, noted for the builder: between this ticket and seaweedfs-cutover, backup-minio keeps
syncing MinIO's frozen openviking bucket to GCS, so OpenViking's new writes on SeaweedFS have no off-site
copy until that ticket lands. That window is a choice to make knowingly. Also, a parameterized dispatch's
workload identity carries the parent job id, so the Vault paths go under default/restore-s3/. The periodic
backup-minio job relies on the same rule today.
