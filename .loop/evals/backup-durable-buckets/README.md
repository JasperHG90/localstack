---
type: eval
title: 'Eval: backup-durable-buckets'
description: 'Definition of done for backup-durable-buckets: 4 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T17:56:41+00:00'
slug: backup-durable-buckets
signoff:
  signer: delegated:jasperginn@gmail.com/planner
  hash: 43d3c2be951595c239cdde7f722155a721cff9371de14f9e965e2ff354cd9ead
  at: '2026-10-19T17:56:41+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: The backup jobspec syncs exactly openviking, registry, models and datalake, each to gcs:${gcs_bucket}/minio/<bucket>/, and every synced bucket is declared in deployments/applications/storage.tf.
  Fails when: the jobspec syncs a bucket set other than those four, a bucket's GCS prefix differs from its name, or a synced bucket is missing from local.buckets
- r2 (judgment): A failed sync of any one bucket makes the backup task exit nonzero, while the other buckets are still attempted.
  Fails when: the task's command lets a failed rclone sync exit 0 (for example joined by ';' with no exit-status tracking), or stops before syncing later buckets after one fails
- r3 (judgment): After a deploy and one on-demand run, the backup job exits 0 and, for each of the four buckets, rclone size of the MinIO bucket and of its GCS prefix report the same object count and bytes.
  Fails when: the run exits nonzero, or any bucket's object count or bytes differ between MinIO and GCS beyond writes that landed during the run, or the evidence (job status and the eight rclone size outputs) is not recorded in the review
- r4 (judgment): docs/reference/gcs-backups.md and .okf/components/gcs-backups.md list the four backed-up buckets and say the 180-day lifecycle rule re-uploads unchanged objects.
  Fails when: either page still says only openviking is backed up, or omits the 180-day re-upload behavior
