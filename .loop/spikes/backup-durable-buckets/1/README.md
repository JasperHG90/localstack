---
type: spike
title: Spike backup-durable-buckets/1
description: how many bytes and objects are in each MinIO bucket (registry, models, datalake, openviking)?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T17:53:09+00:00'
slug: backup-durable-buckets
n: 1
outcome_written: true
---

# Spike backup-durable-buckets/1

how many bytes and objects are in each MinIO bucket (registry, models, datalake, openviking)?

The command exited 0:

```
python3 -I /tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-backup-1/bucket_sizes.py
```

## Outcome

MinIO's public bucket metrics (`/minio/v2/metrics/bucket` on 192.168.2.29:9000, read-only GET) show the four durable buckets hold 6.18 GB in total: registry 5.34 GB / 399 objects, openviking 0.84 GB / 45,686 objects, models and datalake both empty (0 bytes, 0 objects).
For context: tempo 7.10 GB / 6,470, loki 0.93 GB / 13,564, memex 0.74 GB / 1,635, mlflow-artifacts 0.31 GB / 2,867.
At GCS Standard europe-west4 (about $0.020/GB-month) the durable set costs roughly $0.12/month, before versioning or retained old copies.
This rules out the "hundreds of GB" case and settles risk 1 for today's data. Limits: the numbers come from MinIO's background scanner, so they can lag recent writes by minutes, and models/datalake being empty means their future size is still unknown. openviking's 45k small objects matter more for sync time than its bytes.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/bucket_sizes.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-backup-1/bucket_sizes.py`, which the command used
