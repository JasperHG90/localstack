---
type: spike
title: Spike seaweedfs-cutover/1
description: does a registry bucket restored from MinIO through rclone into SeaweedFS still serve old images by tag and digest?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T08:09:29+00:00'
slug: seaweedfs-cutover
n: 1
outcome_written: true
---

# Spike seaweedfs-cutover/1

does a registry bucket restored from MinIO through rclone into SeaweedFS still serve old images by tag and digest?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-cutover-1/registry_restore.sh
```

## Outcome

Passed (exit 0), but did not test multipart blobs. The 30 MiB layer's blob landed on MinIO with a single-part MD5 ETag, because registry 3 commits a blob with one CopyObject below multipartcopythresholdsize (32 MiB default). Both restore paths served both images by tag and digest with matching blob sha256s.
Run 3 replaces this one with a 40 MiB layer and a check that its blob has a multipart ETag.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/registry_restore.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-cutover-1/registry_restore.sh`, which the command used
