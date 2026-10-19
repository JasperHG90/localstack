---
type: spike
title: Spike minio-removal/2
description: can terraform drop minio resources from state with removed blocks and a dummy static provider minio block while MinIO is down, then delete the provider
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T18:02:21+00:00'
slug: minio-removal
n: 2
outcome_written: true
---

# Spike minio-removal/2

can terraform drop minio resources from state with removed blocks and a dummy static provider minio block while MinIO is down, then delete the provider

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-removal-1/spike.sh
```

## Outcome

A working sequence, with MinIO stopped the whole time. (a) Add the `removed { lifecycle { destroy = false } }` blocks, keep `required_providers.minio`, and replace `provider "minio"` with static dummy values (`minio_server = "127.0.0.1:1"`, dummy user and password, no Consul or Vault reads). Plan lists all 9 resources as "will no longer be managed", then apply empties state (0 left). (b) Delete the provider block and the `required_providers` entry, run init and `plan -detailed-exitcode`: exit 0, no changes.
So the provider must be configured but never contacts MinIO when it only forgets resources. Neither MinIO nor its Consul service nor its Vault key has to exist. Risk 1 is real (spike 1) but costs only a second, no-op commit inside step 1. It does not force step 2 to wait on a running MinIO.
Afterward the bucket, the object, the user and the policies were all still on MinIO. Local run only: terraform 1.16.5, aminueza/minio 3.8.3, image pgsty/minio. Not tried on the live applications root.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-removal-1/spike.sh`, which the command used
