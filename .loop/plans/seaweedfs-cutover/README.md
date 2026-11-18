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
  run `rclone check gcs:${gcs_bucket}/minio/<b>/ seaweedfs:<b> --one-way` for
  each durable bucket: every object in GCS must be on SeaweedFS. The other
  direction differs on purpose, because consumers write to SeaweedFS after
  their restore. Write the two kinds of mismatch to separate lists
  (`--missing-on-dst` and `--differ`). An object missing on SeaweedFS was
  deleted there after its restore, and an object that differs was rewritten
  there after it, such as the registry's tag `link` files on every re-push.
  For each, record the app that wrote it and check its SeaweedFS modtime is
  later than that bucket's restore. Stop if one cannot be explained that
  way. An empty bucket (`models`, `datalake`) may have no GCS prefix at all,
  which counts as nothing to check.
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

Outcome: the backup job's next run exits 0 against SeaweedFS, and after it
`rclone check seaweedfs:<b> gcs:${gcs_bucket}/minio/<b>/` exits 0 for each
durable bucket. `localstack`'s `s3` route resolves to `seaweedfs`.
`s3.lab.orangecluster.nl` serves SeaweedFS. No job other than `minio` itself
points an S3 client at MinIO's endpoint; Prometheus still scrapes MinIO until
`minio-removal`. MinIO's S3 request rate drops to zero for an hour, counted
from the last applications-root run, since that root still manages MinIO's
resources. `.devcontainer/.env.example` names which SeaweedFS key the `mc`
alias uses. `just pre_commit` and `uv run --directory cli pytest` pass.

## Could invalidate this plan

- none
