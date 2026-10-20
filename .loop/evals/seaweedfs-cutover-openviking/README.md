---
type: eval
title: 'Eval: seaweedfs-cutover-openviking'
description: 'Definition of done for seaweedfs-cutover-openviking: 3 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T04:37:30+00:00'
slug: seaweedfs-cutover-openviking
signoff:
  signer: delegated:jasperginn@gmail.com/planner
  hash: 83c92ae8b507da7cae8c826a631a668a0d3d98a0fc9f224d8a07c782a6108434
  at: '2026-10-20T04:37:30+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: restore-s3.hcl is a parameterized batch job that takes a bucket name, copies gcs:<bucket>/minio/<bucket>/ to seaweedfs:<bucket> with --create-empty-src-dirs --s3-directory-markers, then runs rclone check, then fails if any directory rclone lsf -R --dirs-only lists under the GCS prefix is missing on SeaweedFS, and reads its keys from default/restore-s3/gcs and default/restore-s3/seaweedfs.
  Fails when: the job is not parameterized, either marker flag is missing, the check or the one-way directory check is missing or does not fail the run, or a key is read from another path
- r2: The applications root creates SeaweedFS user restore with write on the four durable buckets only, and OpenViking's ov.conf.json reads its S3 key from default/openviking/seaweedfs and its endpoint from the renamed S3 endpoint variable.
  Fails when: restore reaches another bucket or lacks write on a durable one, or OpenViking still reads a MinIO key or endpoint
- r3 (judgment): Following steps 0 to 4: the backup run before the restore exits 0, rclone check exits 0 for openviking, models and datalake, OpenViking is healthy, every baseline URI reads back with the same content hash, the recursive ls matches the baseline with empty directories, and a new write lands on SeaweedFS while MinIO's openviking count stays fixed.
  Fails when: any step fails or is skipped, a hash or the ls differs, MinIO's count rises, or the evidence is not recorded in the review
