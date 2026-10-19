---
type: plan
title: 'Plan: seaweedfs-cutover'
description: Once every consumer is on SeaweedFS, move the backup job, the s3 route and tag, the edge routes, the dash tile and the user docs onto it.
slug: seaweedfs-cutover
epic: seaweedfs-migration
depends_on:
- seaweedfs-cutover-observability
- seaweedfs-cutover-openviking
- seaweedfs-cutover-registry
priority: 8
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T17:50:32+00:00'
---

# seaweedfs-cutover

Relayed from: none

## Intent

The last switch, after `seaweedfs-cutover-observability`,
`seaweedfs-cutover-openviking` and `seaweedfs-cutover-registry` have moved
every consumer. MinIO keeps running untouched until `minio-removal`.

- The backup job, `deployments/infrastructure/services/backup-minio.hcl`,
  reads SeaweedFS with its read-only key from `default/backup-minio/seaweedfs`
  (`seaweedfs-buckets`), rclone `provider = SeaweedFS`. It keeps writing to
  the same `gcs:${gcs_bucket}/minio/<bucket>/` prefixes, so the history
  carries on. This switch waits for every restore: `rclone sync` makes the
  destination match the source, so a sync from a SeaweedFS bucket that was
  not yet restored would delete that bucket's GCS copy. Before the apply,
  `rclone check` each durable bucket between SeaweedFS and GCS.
  `cli/tests/test_backup_coverage.py` follows the remote name.
- The `s3` Consul tag moves from `minio` to `seaweedfs`, so the CLI's `s3`
  route follows it (`cli/src/localstack_cli/api/services.py`). The CLI tests
  and fixtures under `cli/tests/` change to match.
- The edge routes in `deployments/infrastructure/services/haproxy.hcl`:
  `s3.lab.orangecluster.nl` points at SeaweedFS's S3 port. The
  `minio.lab.orangecluster.nl` console route stays on MinIO until
  `minio-removal`. SeaweedFS's master UI is loopback-only by design
  (`seaweedfs-service`) and gets no route.
- The dash tile in `deployments/applications/services/dash/tiles.json` and
  its test, and every remaining hardcoded `192.168.2.29:9000`, which becomes
  a Consul lookup or a template variable.
- The devcontainer's `mc` alias in `.devcontainer/bootstrap.sh` points at
  SeaweedFS, and the user docs under `docs/` that tell a reader to use MinIO
  are rewritten for SeaweedFS.

Outcome: the backup job's next run exits 0 against SeaweedFS, and the GCS
object count for each durable bucket is unchanged or higher. `localstack`'s
`s3` route resolves to `seaweedfs`. `s3.lab.orangecluster.nl` serves
SeaweedFS. MinIO's S3 request rate in Prometheus drops to zero for an hour,
and no job's rendered config names MinIO or port 9000. `just pre_commit` and
`uv run --directory cli pytest` pass.

## Could invalidate this plan

- none
