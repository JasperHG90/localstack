---
type: plan
title: 'Plan: seaweedfs-cutover-openviking'
description: Restore openviking, models and datalake from GCS into SeaweedFS with a reusable restore job, then switch OpenViking to its SeaweedFS key.
slug: seaweedfs-cutover-openviking
epic: seaweedfs-migration
depends_on:
- seaweedfs-buckets
- backup-durable-buckets
priority: 6
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T20:52:58+00:00'
---

# seaweedfs-cutover-openviking

Relayed from: none

## Intent

Move OpenViking's data and the two buckets with no consumer onto SeaweedFS.

Add a Nomad parameterized batch job `restore-s3` in the infrastructure root
(`new:deployments/infrastructure/services/restore-s3.hcl`). Dispatched with a
bucket name, it runs `rclone copy gcs:${gcs_bucket}/minio/<bucket>/
seaweedfs:<bucket>` and then `rclone check` between the two, failing on any
difference. It reads the GCS key and a SeaweedFS key that can write the
durable buckets. `seaweedfs-cutover-registry` reuses it.

Order, for openviking:

1. Stop OpenViking, so nothing lands on MinIO after the copy.
2. `nomad job periodic force backup-minio`, and wait for it to exit 0.
3. Dispatch `restore-s3` for `openviking`, then for `models` and `datalake`
   (empty today, per `spike:backup-durable-buckets/1`).
4. Point OpenViking at SeaweedFS: `minio_endpoint` in
   `deployments/applications/services.tf` (rename it to say S3) and its key
   from `default/openviking/seaweedfs`, read by
   `deployments/applications/services/openviking/ov.conf.json`. Start it.

Outcome: `rclone check` exits 0 for each of the three buckets. OpenViking
is healthy and its readiness check passes, a search returns results that
existed before the switch, and a new write lands in SeaweedFS's
`openviking` bucket while MinIO's object count for it stays fixed.
`just pre_commit` and `uv run --directory cli pytest` pass.

## Could invalidate this plan

- OpenViking's S3 client may need something SeaweedFS does not do (virtual
  host addressing, a region check, a checksum header). If it cannot talk to
  SeaweedFS with path-style requests and a static key, OpenViking cannot
  move without an upstream fix, and MinIO cannot be removed.
  Settled by `spike:seaweedfs-cutover-openviking/1`: OpenViking's storage
  client is the Rust AGFS `s3fs` backend in the deployed image. Driven
  through `create_agfs_client` with the prod S3 settings (path style,
  us-east-1, no SSL) and a static key scoped to `openviking`, it passed 28 of
  28 operations on SeaweedFS 4.48, server-side copy and recursive delete
  included.
