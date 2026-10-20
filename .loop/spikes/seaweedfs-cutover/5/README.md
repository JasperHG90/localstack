---
type: spike
title: Spike seaweedfs-cutover/5
description: after the cutover, does the first backup from SeaweedFS match GCS file for file, do the s3 route and s3.lab serve SeaweedFS, and do MinIO counts stay fixed for ten minutes?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T08:25:26+00:00'
slug: seaweedfs-cutover
n: 5
outcome_written: true
---

# Spike seaweedfs-cutover/5

after the cutover, does the first backup from SeaweedFS match GCS file for file, do the s3 route and s3.lab serve SeaweedFS, and do MinIO counts stay fixed for ten minutes?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/cut/verify.sh
```

## Outcome

Yes. On 2026-10-20 the infrastructure root updated `backup_minio` (source SeaweedFS), `seaweedfs` (gains the `s3` tag) and `haproxy` (s3.lab to 8333). The applications root updated `dash` (the SeaweedFS tile). `nomad_job.minio` dropped its `s3` tag as an in-place service update: Nomad's plan said in-place, and alloc 4cf10997 kept running with no restart. Its pinned image can no longer be downloaded, so a restart had to be avoided.

stdout.txt: the first backup from SeaweedFS (periodic-1792483971, alloc d12af9d8) exited 0. After it, GCS matches SeaweedFS file for file in all four durable buckets: 37,207 openviking files, 404 registry files, models and datalake empty, with nothing missing, extra or differing. `localstack service` resolves `s3` to `seaweedfs` by tag, passing, backend 192.168.2.29:8333. `s3.lab.orangecluster.nl` answers with `server: SeaweedFS 30GB 4.48`. MinIO's object counts are identical at 08:12:58 and 08:24:46 UTC (openviking 45,765, registry 399, loki 13,581, tempo 6,502, models 0, datalake 0), so nothing writes to MinIO. The one-way check before the switch is `spike:seaweedfs-cutover/4`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/verify.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/cut/verify.sh`, which the command used
- `files/after.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/cut/after.py`, which the command used
