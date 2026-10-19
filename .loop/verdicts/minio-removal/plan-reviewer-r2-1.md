---
type: verdict
title: 'Verdict: minio-removal plan-reviewer round 2'
description: 'plan-reviewer verdict for round 2 of minio-removal: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-19T18:10:39+00:00'
slug: minio-removal
pass: plan-reviewer
round: 2
body_schema: verdict/1
---

## Summary

Both round-1 findings are settled. The removed-block approach with a dummy
provider is backed by two spikes that answer the risk directly. The backup
naming is decided. One gap remains (p3). The rename moves the job to a new
Vault prefix, but the backup key that seaweedfs-buckets writes from the
applications root is not covered, and the step order does not say when it
moves relative to the job. The fix is a line in the plan, not a rethink.

## Checked

- Spike 1 (exit 1, as expected): with the provider deleted, plan fails with
  "requires explicit configuration" and all 9 resources stay in state. Spike 2
  (exit 0): a dummy provider (`127.0.0.1:1`) and removed blocks empty state
  with MinIO stopped. The second commit then plans clean. Data was still on
  MinIO afterward in both runs. The local run covered module.buckets and root
  minio_* resources of the same types the applications root has
  (storage.tf: minio_iam_policy *_wi, minio_iam_user, minio_accesskey).
- The applications provider reads data.consul_service.minio and an ephemeral
  Vault read (providers.tf:44-47, services.tf:1). Step 1A replaces both
  before step 2 deletes the service and key, so the order holds.
- Vault scoping: identity.tf and the secrets.tf:284 comment confirm the
  per-job_id prefix. That is why the rename must move every key the job
  reads, in both roots.

## Findings

- p1 (resolved): the removed blocks and the dummy provider, backed by spikes 1 and 2.
- p2 (resolved): the job is renamed to backup-s3, and the GCS prefix minio/ is kept on purpose.
- p3 (open, blocking): the backup job's SeaweedFS key at
  default/backup-minio/seaweedfs (applications root, from seaweedfs-buckets)
  is not covered by the rename, and the step order does not place it.

## Notes

nomad_job resources here do not set purge_on_destroy. A stopped periodic job
can show in `nomad job status backup-minio` until GC runs, so the plan's
"the old one is purged" needs an explicit purge. The builder will see this
when checking the outcome, so it is not a finding.
