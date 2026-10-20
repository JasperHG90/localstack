---
type: spike
title: Spike minio-volume-destroy/2
description: after purging the missed openfang key, does a scan of every path under secret/default find no MinIO key, with the volume, host directory and plan still as before?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T09:45:16+00:00'
slug: minio-volume-destroy
n: 2
outcome_written: true
---

# Spike minio-volume-destroy/2

after purging the missed openfang key, does a scan of every path under secret/default find no MinIO key, with the volume, host directory and plan still as before?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/vol-verify/verify.sh
```

## Outcome

Yes. Review round 1 found `default/openfang/minio`, a key soft-deleted in April by the retired openfang job, which spike 1 missed because it checked only six named jobs. That key was purged with `vault kv metadata delete`, and the check now lists every path under secret/default/ two levels deep. stdout.txt shows no path naming minio is left, Nomad lists no `minio_data`, its host directory on orangepi4a is gone, and the infrastructure plan lists only the 15 always-run firewall replacements. 18 MinIO key paths were purged in all.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/verify.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/vol-verify/verify.sh`, which the command used
