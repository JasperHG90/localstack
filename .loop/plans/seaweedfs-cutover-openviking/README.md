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
bucket name, it runs `rclone copy --create-empty-src-dirs
--s3-directory-markers gcs:${gcs_bucket}/minio/<bucket>/ seaweedfs:<bucket>`,
then `rclone check` between the two, then a one-way directory check: every
directory `rclone lsf -R --dirs-only` lists under the GCS prefix must also
be listed on SeaweedFS. It fails on any directory missing there. The marker
counts are not compared, because they differ by design: a flagged sync onto
the existing GCS copy adds markers only for empty directories, while a
fresh flagged copy writes one for every directory. `rclone check` alone
passes with every marker missing (`spike:seaweedfs-cutover-openviking/2`). `seaweedfs-cutover-registry` reuses it. A job reads only
`secret/data/default/<job id>/*`, and a dispatched job carries its parent's
id, so it gets its own keys:

- `default/restore-s3/gcs`: the GCS key, in
  `deployments/infrastructure/secrets.tf`, as `backup-minio` has its own.
- `default/restore-s3/seaweedfs`: a SeaweedFS user `restore` with write on
  the four durable buckets, created in the applications root where the IAM
  provider is (`deployments/applications/storage.tf`), its key written from
  `deployments/applications/secrets.tf`. This is the cross-root pattern the
  backup user follows. The user is removed in `minio-removal`.

Order, for openviking:

0. Record a baseline: a handful of resource URIs across the tree, their
   content hashes as OpenViking's API returns them, and a recursive `ls` of
   the tree, including empty directories.
1. Stop OpenViking, so nothing lands on MinIO after the copy.
2. `nomad job periodic force backup-minio`, and wait for it to exit 0. The
   run must carry the marker flags from `backup-durable-buckets`: copies
   made before them hold no empty directories.
3. Dispatch `restore-s3` for `openviking`, then for `models` and `datalake`
   (empty today, per `spike:backup-durable-buckets/1`).
4. Point OpenViking at SeaweedFS: `minio_endpoint` in
   `deployments/applications/services.tf` (rename it to say S3) and its key
   from `default/openviking/seaweedfs`, read by
   `deployments/applications/services/openviking/ov.conf.json`. Start it.

Outcome: `rclone check` exits 0 for each of the three buckets. OpenViking
is healthy and its readiness check passes. Every baseline URI reads back
through OpenViking's API with the same content hash, which goes through the
bucket rather than Postgres, and the recursive `ls` matches the baseline,
empty directories included. A new write lands in SeaweedFS's
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
- Directory markers. OpenViking's storage stores a directory as a zero-byte
  key ending in `/`, and rclone skips such keys by default. If the GCS copy
  (made by the backup job) and the restore drop them, empty directories and
  marker-dependent paths vanish after the restore while `rclone check`
  still exits 0. This would also mean the backup job itself needs another
  flag.
  Real, and fixed, per `spike:seaweedfs-cutover-openviking/2`: the backup
  job's plain `rclone sync` kept 0 of 6 markers, `rclone check` still
  exited 0, and OpenViking then lost all 4 empty directories. With
  `--create-empty-src-dirs` on the backup leg and `--create-empty-src-dirs
  --s3-directory-markers` on the restore, all 24 views and every move step
  matched. `backup-durable-buckets` adds `--create-empty-src-dirs
  --gcs-directory-markers` to the backup job, both flags present in rclone
  v1.75.2, the image it runs.
