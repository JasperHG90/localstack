---
type: spike
title: Spike seaweedfs-service/1
description: does the pinned arm64 SeaweedFS 4.48 image run weed server -s3 within a 512 MB memory limit, with S3, a health endpoint and Prometheus metrics?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T17:56:01+00:00'
slug: seaweedfs-service
n: 1
outcome_written: true
---

# Spike seaweedfs-service/1

does the pinned arm64 SeaweedFS 4.48 image run weed server -s3 within a 512 MB memory limit, with S3, a health endpoint and Prometheus metrics?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-service-1/spike.sh
```

## Outcome

`chrislusf/seaweedfs:4.48` (arm64 digest `sha256:f1f30347…75a1`, newest release, >= 4.40) ran `weed server -s3` on aarch64 under docker with a 512 MB limit: S3 answered in 4 s, an admin identity from a `-s3.config` JSON file was enforced (wrong key got InvalidAccessKeyId), and 40 objects (25 MiB) went through put, get, list and delete.
Health: `GET /healthz` on the S3 port (8333) returns 200, as do master `/cluster/healthz` (9333) and filer/volume `/healthz`. Metrics: `-metricsPort=9327` serves `/metrics` with 185 `SeaweedFS_` series.
Memory: cgroup 64 MiB idle, 140 MiB after the load, 175 MiB 15 s later (VmRSS peak 220 MiB); no OOM, no restart. A 256 to 512 MB reservation is enough, far below MinIO's 2560 MB.
Rules out an arm64 image gap, a crash, or a memory need that would not fit beside MinIO. Limits: docker on an orbstack kernel, not podman on orangepi4a's kernel; light load only; orangepi4a's free RAM is not recorded, so whether 256 to 512 MB is free there is still open.
Settles risk 1 for image, arch and footprint; podman and the node's actual free memory are unverified.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-service-1/spike.sh`, which the command used
