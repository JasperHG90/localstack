---
type: eval
title: 'Eval: seaweedfs-cutover'
description: 'Definition of done for seaweedfs-cutover: 4 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T08:01:50+00:00'
slug: seaweedfs-cutover
signoff:
  signer: delegated:jasperginn@gmail.com/planner
  hash: 8939bab47d465b3c4472dda0d5ac1af555ca4b03cbdcbff76504348e2e706b20
  at: '2026-10-20T08:01:50+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: The backup job syncs the four durable buckets from a seaweedfs remote (provider SeaweedFS) to the same gcs minio/<bucket>/ prefixes with the marker flags, using the key at default/backup-minio/seaweedfs.
  Fails when: a durable bucket is missing, the source is still MinIO, the GCS prefix changes, a marker flag is dropped, or the key is read from another path
- r2: The s3 Consul tag is on the seaweedfs service and not on minio, the CLI's s3 route resolves to seaweedfs, haproxy's s3.lab route points at SeaweedFS's S3 port while minio.lab stays on MinIO, the dash tile and devcontainer mc alias point at SeaweedFS, and no jobspec outside minio.hcl and prometheus.hcl hardcodes 192.168.2.29:9000.
  Fails when: any of those still points at MinIO, or a hardcoded MinIO endpoint remains outside those two files
- r3 (judgment): Before the apply, a one-way rclone check from each durable bucket's GCS prefix to SeaweedFS is recorded, with --missing-on-dst and --differ lists, and each listed object is named with the app that rewrote or deleted it and a SeaweedFS modtime after that bucket's restore.
  Fails when: a bucket's check is missing, or any listed object is unexplained
- r4 (judgment): The backup job's next run exits 0 against SeaweedFS and rclone check seaweedfs:<b> against its GCS prefix then exits 0 for each durable bucket, s3.lab serves SeaweedFS, MinIO's object counts stay fixed across two readings at least 10 minutes apart after the last applications-root run (operator, 2026-10-20: remove MinIO once the data is synced, without the long wait), the docs under docs/ point readers at SeaweedFS, and .devcontainer/.env.example names the mc alias's key.
  Fails when: any of those fails, or the evidence is not recorded in the review
