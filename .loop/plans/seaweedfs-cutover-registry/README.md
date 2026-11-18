---
type: plan
title: 'Plan: seaweedfs-cutover-registry'
description: Restore the registry bucket from GCS into SeaweedFS and switch the OCI registry to it with keyless per-job credentials.
slug: seaweedfs-cutover-registry
epic: seaweedfs-migration
depends_on:
- seaweedfs-workload-identity
- seaweedfs-cutover-openviking
priority: 7
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T20:52:58+00:00'
---

# seaweedfs-cutover-registry

Relayed from: none

## Intent

Move the OCI registry to SeaweedFS last among the consumers, so a mistake on
the others never costs image pulls.

1. Stop the registry (`deployments/applications/services/registry.hcl`),
   force `backup-minio`, wait for it to exit 0, and dispatch `restore-s3`
   (from `seaweedfs-cutover-openviking`) for `registry`.
2. Point the registry at SeaweedFS: identity audience `seaweedfs`, the
   `credential_process` helper adding `&RoleArn=<registry role>&RoleSessionName=registry`,
   and `regionendpoint` on SeaweedFS instead of the hardcoded
   `192.168.2.29:9000`. Start it.
3. Update the haproxy comment about multipart uploads in
   `deployments/infrastructure/services/haproxy.hcl` if the edge path for
   pushes changes.

Outcome: `rclone check` exits 0 for `registry`. An image pushed before the
switch pulls by tag and by digest. A new push succeeds and its blobs land in
SeaweedFS's `registry` bucket, and MinIO's object count for `registry` stays
fixed. `just pre_commit` and `uv run --directory cli pytest` pass.

## Could invalidate this plan

- Registry restore. The registry addresses blobs by digest under a fixed
  layout. If a restore through rclone changes anything the registry reads
  (multipart ETags, object metadata, prefixes), every image pushed before the
  cutover breaks and the registry needs a re-push instead of a restore.
  Settled by `spike:seaweedfs-cutover/3`: registry 3.1.1 images pushed to
  MinIO, one with a 40 MiB multipart-ETag blob, went through rclone to a
  directory (standing in for GCS) and into SeaweedFS 4.48 with 0 size
  differences. A fresh registry on SeaweedFS served both by tag and by
  digest, `crane validate --remote` passed, and every blob's sha256 matched.
- Pushes on SeaweedFS. The restore spike pushed only to MinIO and pulled from
  SeaweedFS with an admin key. A push writes blobs as multipart uploads,
  resumes them through ListMultipartUploads, commits each with CopyObject or
  UploadPartCopy, and garbage collection deletes objects. If SeaweedFS 4.48
  gets one of those wrong, or the per-job role's policy leaves out an action
  they need, the registry serves old images but refuses new pushes, and the
  cutover has to roll back.
  Settled by `spike:seaweedfs-cutover-registry/1`: registry 3.1.1 with only
  per-job role credentials from the fixed helper pushed a 110 MiB layer
  (UploadPartCopy) and a 1 MiB layer (CopyObject) to SeaweedFS 4.48, served
  both by digest, garbage-collected a deleted image and pushed again. The
  role needs at least `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` and
  `s3:ListBucket` on the bucket. `s3:*` on the bucket covers them.
