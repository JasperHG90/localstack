---
type: spike
title: Spike minio-removal/3
description: after the applies in plan order, is the applications state free of MinIO, do both roots plan clean, are minio and backup-minio gone, does backup-s3 run, and is ov-dash back?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T08:53:29+00:00'
slug: minio-removal
n: 3
outcome_written: true
---

# Spike minio-removal/3

after the applies in plan order, is the applications state free of MinIO, do both roots plan clean, are minio and backup-minio gone, does backup-s3 run, and is ov-dash back?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/rm-verify/verify.sh
```

## Outcome

Void run: `set -e` with pipefail stopped the script at the first expected 404 from `nomad job status minio`, and the infrastructure plan was filtered in a way that hid its summary. Superseded by `spike:minio-removal/4`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/verify.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/rm-verify/verify.sh`, which the command used
