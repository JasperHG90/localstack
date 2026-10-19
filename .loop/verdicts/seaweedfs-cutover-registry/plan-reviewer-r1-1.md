---
type: verdict
title: 'Verdict: seaweedfs-cutover-registry plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of seaweedfs-cutover-registry: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-19T20:56:05+00:00'
slug: seaweedfs-cutover-registry
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

The restore half is settled. spike:seaweedfs-cutover/3 is direct evidence
that rclone through a directory into SeaweedFS keeps every blob the registry
reads, by tag and by digest, including a multipart-ETag blob. The other
half of the switch is the push path: new blobs written through SeaweedFS
with keyless role credentials. Nothing has exercised it, and the plan does
not list it. That is p1. A cheap spike settles it, so the verdict is fail,
not reject.

## Checked

- The plan's one listed risk against spike seaweedfs-cutover/3 (README,
  stdout, script, run.json, exit 0). The evidence covers restore and pull,
  with static keys only. No push to SeaweedFS was made.
- The client fit for the registry helper against seaweedfs-workload-identity
  spikes 3 and 4. Adding RoleArn and RoleSessionName to the query string
  works, and the registry helper matches loki's byte for byte. Only
  PutObject was tried with role credentials.
- `deployments/applications/services/registry.hcl`: the helper, the
  hardcoded `regionendpoint`, `delete.enabled: true`, and aws-sdk via
  credential_process. All match what the plan assumes.
- The caller's question, whether stopping the registry breaks image pulls.
  Every `image =` in both roots comes from docker.io, ghcr.io or quay.io.
  That covers the registry's own image (`docker.io/library/registry:3.1.1`),
  rclone (`docker.io/rclone/rclone:latest`) and the images from
  seaweedfs-service. No node manages registries.conf, so there is no mirror
  through the cluster registry (services.tf comment). Stopping the registry
  breaks no container pull.
- The only registry consumer at task start is embark's `model-pull`
  prestart. `services/embark/pull.sh` skips a model whose `.ref` marker
  already matches, so a restart during the window starts cleanly. It fails
  only if models.json changes or the embark_data volume is lost in the window.
  registry-ui reads through the registry API, so it shows errors during the
  window and nothing breaks.
- Dependencies. backup-minio syncs only `openviking` today. Widening it to
  `registry` belongs to backup-durable-buckets, which this plan reaches
  through seaweedfs-cutover-openviking's depends_on. The `registry` bucket on
  SeaweedFS comes from seaweedfs-buckets. The registry is 5.34 GB in 399
  objects (spike:backup-durable-buckets/1), so the restore window is short.
- Measurability. Every outcome clause can be observed: rclone check exit,
  pull by tag and by digest, a push followed by a list of SeaweedFS's
  `registry` bucket, and MinIO's object count. registry-ui does not write to
  S3, so nothing else moves MinIO's count.

## Findings

- p1: the push path on SeaweedFS with role credentials is unproven. This
  covers multipart write, ListMultipartUploads, the UploadPartCopy and
  CopyObject commit, delete for GC, and the role policy's action list. If any
  of them fails, the registry takes no new images after the switch. The fix
  is a spike, described in the finding, before the build.

## Notes

The plan's step 3 ("update the haproxy comment if the edge path changes")
only touches a comment. The edge does not change, because HAProxy still
points at the registry on ubuntu. The 1800s `timeout server` exists for the
multipart finalize pause. Whether SeaweedFS's finalize is shorter or longer
is part of what the p1 spike will show for large layers. One real risk does
not call for a split.
