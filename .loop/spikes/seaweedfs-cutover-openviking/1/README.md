---
type: spike
title: Spike seaweedfs-cutover-openviking/1
description: does OpenViking's AGFS s3fs backend (image v0.4.17.1-9) read, write, list, copy and delete on SeaweedFS 4.48 with path-style requests and a static IAM key scoped to its bucket
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T20:57:46+00:00'
slug: seaweedfs-cutover-openviking
n: 1
outcome_written: true
---

# Spike seaweedfs-cutover-openviking/1

does OpenViking's AGFS s3fs backend (image v0.4.17.1-9) read, write, list, copy and delete on SeaweedFS 4.48 with path-style requests and a static IAM key scoped to its bucket

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ov-1/spike.sh
```

## Outcome

OpenViking's own storage path worked against SeaweedFS 4.48: the AGFS Rust `s3fs` backend from `ghcr.io/jasperhg90/openviking:v0.4.17.1-9`, mounted through `create_agfs_client` with the prod `ov.conf.json` S3 settings (path style, `region` us-east-1, no SSL), passed all 27 checks using a static IAM key whose inline policy grants `s3:*` on `openviking` only.
The checks covered mkdir, ensure_parent_dirs, write (including a 12 MB object and a key with `space+@#%`), full and ranged read, stat, ls, touch, create, copy_within_mount (server-side CopyObject), tree, glob, grep, rm, recursive rm, and the directory move that VikingFS.mv does (stat, recursive cp, recursive rm). The mount itself succeeded.
This rules out a virtual-host, region or checksum-header incompatibility. Settles risk 1.
Limits: the spike drove the storage binding directly, without the full server (no Postgres, embedder or HTTP API), and ran on one local container. The binding's raw `mv` on a directory failed with NoSuchKey on the `dir/` marker CopyObject. OpenViking never calls it (VikingFS.mv is cp+rm), and the spike did not check whether MinIO behaves the same.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ov-1/spike.sh`, which the command used
- `files/ov_probe.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ov-1/ov_probe.py`, which the command used
- `files/iam.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ov-1/iam.py`, which the command used
