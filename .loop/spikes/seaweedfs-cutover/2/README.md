---
type: spike
title: Spike seaweedfs-cutover/2
description: does a registry bucket with multipart-ETag blobs restored from MinIO through rclone into SeaweedFS still serve old images by tag and digest?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T18:15:50+00:00'
slug: seaweedfs-cutover
n: 2
outcome_written: true
---

# Spike seaweedfs-cutover/2

does a registry bucket with multipart-ETag blobs restored from MinIO through rclone into SeaweedFS still serve old images by tag and digest?

The command timed out:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-cutover-1/registry_restore.sh
```

## Outcome

Timed out (540 s). Not evidence on risk 1. The MinIO -> local dir -> SeaweedFS restore finished, then the direct S3-to-S3 sync into a second bucket got HTTP 500 from SeaweedFS on every PutObject: "No writable volumes and no free volumes left for collection registry-direct".
Each bucket is its own SeaweedFS collection and takes its own volumes, and the spike's single node ran out of volume slots under its default limits. Run 3 fixed this with -volume.max=64 -master.volumeSizeLimitMB=256.
Takeaway for seaweedfs-service: size -volume.max and the volume size limit for six buckets, or a bucket's first write fails with 500.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/registry_restore.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-cutover-1/registry_restore.sh`, which the command used
