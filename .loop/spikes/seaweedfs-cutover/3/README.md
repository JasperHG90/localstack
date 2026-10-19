---
type: spike
title: Spike seaweedfs-cutover/3
description: does a registry bucket with multipart-ETag blobs restored from MinIO through rclone into SeaweedFS still serve old images by tag and digest?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T18:15:54+00:00'
slug: seaweedfs-cutover
n: 3
outcome_written: true
---

# Spike seaweedfs-cutover/3

does a registry bucket with multipart-ETag blobs restored from MinIO through rclone into SeaweedFS still serve old images by tag and digest?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-cutover-1/registry_restore.sh
```

## Outcome

Restore works. Registry 3.1.1 on MinIO (RELEASE.2025-09-07T16-13-09Z built from source) held a 3-layer image and an image with a 40 MiB layer whose blob MinIO stored with a multipart ETag. rclone sync MinIO -> local dir (GCS stand-in) -> rclone copy into SeaweedFS 4.48, and a direct S3-to-S3 rclone sync, each gave 30/30 objects, 45646483 bytes, 0 size differences.
A fresh registry on each SeaweedFS bucket served both images by tag and by digest: same manifest digests, `crane validate --remote` passed, and every blob's sha256 matched its digest. The registry reads only keys and bytes, so changed ETags and lost object metadata do not matter. Settles risk 1.
Limits: a local directory stood in for GCS, so GCS's own metadata handling was not tested, though it can only change ETags and metadata, which this run shows the registry ignores. Static keys, not STS. One SeaweedFS node with -volume.max=64 (see run 2).

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/registry_restore.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-cutover-1/registry_restore.sh`, which the command used
