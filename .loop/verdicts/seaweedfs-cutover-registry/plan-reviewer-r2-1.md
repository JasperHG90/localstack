---
type: verdict
title: 'Verdict: seaweedfs-cutover-registry plan-reviewer round 2'
description: 'plan-reviewer verdict for round 2 of seaweedfs-cutover-registry: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-19T21:05:29+00:00'
slug: seaweedfs-cutover-registry
pass: plan-reviewer
round: 2
body_schema: verdict/1
---

## Summary

p1 is resolved. spike:seaweedfs-cutover-registry/1 ran registry 3.1.1
against SeaweedFS 4.48 with production `weed server` flags, `copy_1 = 2`,
`defaultEffect: Deny`, and only RegistryRole STS creds from the real
`registry.hcl` helper. It pushed a layer committed by UploadPartCopy and
one committed by CopyObject, served both by digest, ran GC and pushed
again, under `s3:*` and under the narrowed list. Nothing else found could
break the plan. The directory-marker risk on the sibling plan does not
reach the registry bucket.

## Checked

- Spike seaweedfs-cutover-registry/1: README, run.json (exit 0, not timed
  out), stdout, stderr and files/spike.sh. The script extracts the helper
  from `deployments/applications/services/registry.hcl` and fails if the
  template changed. It rewrites only the STS host and appends RoleArn and
  RoleSessionName. The registry container got no static keys. The big
  blob's stored ETag ends `-4` (UploadPartCopy). The small one ends `-1`.
  Both phases printed `RESULT ok=1`. GC removed only the deleted image's
  blobs. The ablation shows Get, Put, Delete and List are each needed.
  The stray `HTTP ` lines after each ETag come from the awk status parse
  (`-F': '` leaves `$2` empty on the status line). They are cosmetic, and
  the ETag was read.
- Spike limits: no resumed interrupted upload and no `uploadpurging`.
  Neither can stop the cutover. A failed resume makes the client restart
  the upload. Purging needs Delete and List, which the role has.
- Directory markers, as the caller asked. Distribution's S3 driver writes
  only file keys (blob `data`, `link`, `startedat`, hashstates). It never
  writes a zero-byte key ending in `/`, and it finds paths by prefix
  listing, so it does not depend on markers. spike:seaweedfs-cutover/3
  confirms it end to end: 30/30 objects, the same on MinIO, the
  directory stand-in and SeaweedFS, and a fresh registry served every
  image after the rclone round trip. A zero-byte blob `data` file (empty
  digest) has no trailing slash, so rclone copies it.
- restore-s3 reuse: in seaweedfs-cutover-openviking it has its own GCS key
  and a SeaweedFS `restore` user with write on the four durable buckets,
  `registry` among them (backup-durable-buckets lists the four).
  backup-minio covers `registry` through that dependency.
- Other MinIO endpoint users. The hardcoded `192.168.2.29:9000` also shows
  up in haproxy's s3 backend, loki, tempo, prometheus and the health
  checks. Those belong to other tickets. The registry's HAProxy backend
  points at the registry on ubuntu, so the edge does not change.

## Findings

- p1: resolved. See Checked.

## Notes

Step 2 says to change the audience, add RoleArn and RoleSessionName, and
move `regionendpoint`. The helper's STS URL (`${minio_host}:9000`) has to
move to SeaweedFS's S3 port too, as the spike did. That is a build detail,
not a plan risk. One risk is left, so no split is needed.
