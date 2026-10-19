---
type: eval
title: 'Eval: minio-removal'
description: 'Definition of done for minio-removal: 4 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T20:54:57+00:00'
slug: minio-removal
signoff:
  signer: delegated:jasperginn@gmail.com/planner
  hash: 63fadf6adeabfeaf6fcbf5677a5c605726dec4e638cec583051c163b7a22f402
  at: '2026-10-19T20:54:57+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: No file under deployments/, bootstrap/, cli/src or .devcontainer/Dockerfile names MinIO, except the GCS prefix minio/ and its one comment in the backup-s3 jobspec.
  Fails when: any other case-insensitive match for minio exists in those paths
- r2 (judgment): After the applies in the plan's order, terraform state list in the applications root has no minio_ address and nothing under module.buckets, and terraform plan in both roots reports no changes.
  Fails when: a MinIO address remains in state, a plan shows changes, or a bucket or object on MinIO was deleted, or the evidence is not recorded
- r3 (judgment): nomad job status minio and nomad job status backup-minio report no such job, and backup-s3's next run exits 0 reading its keys from default/backup-s3/.
  Fails when: either old job is still listed, or backup-s3's run fails
- r4 (judgment): The MinIO keyless how-tos are replaced by SeaweedFS ones, docs/explanation/workload-identity.md describes SeaweedFS, .okf/components/minio.md is marked superseded, and a decision record covers the removal.
  Fails when: a docs page still tells a reader to use MinIO, or the superseded mark or decision record is missing
