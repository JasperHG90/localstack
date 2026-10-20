---
type: spike
title: Spike backup-durable-buckets/2
description: after the deployed run, is every MinIO object and directory in the durable buckets present in GCS at the same size?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T04:41:33+00:00'
slug: backup-durable-buckets
n: 2
outcome_written: true
---

# Spike backup-durable-buckets/2

after the deployed run, is every MinIO object and directory in the durable buckets present in GCS at the same size?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/gcs-size/verify.sh
```

## Outcome

Void run: the spike's environment got 403 from `nomad job status`, though the same token worked in the operator shell a minute later, so `set -e` stopped the script before any comparison. Superseded by `spike:backup-durable-buckets/3`, which drops the Nomad calls. The run's status was read in the operator shell instead: allocation 8e84a792 of `backup-minio` (forced 2026-10-20 04:36:17 UTC, after the targeted apply of `nomad_job.backup_minio`) ended `complete`, Exit Code 0, at 04:38:21 UTC.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/verify.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/gcs-size/verify.sh`, which the command used
- `files/compare.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/gcs-size/compare.py`, which the command used
