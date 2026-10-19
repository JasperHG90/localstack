---
type: spike
title: Spike minio-removal/1
description: can terraform drop minio resources from state with removed blocks once provider minio and its required_providers entry are deleted and MinIO is down
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T18:01:38+00:00'
slug: minio-removal
n: 1
outcome_written: true
---

# Spike minio-removal/1

can terraform drop minio resources from state with removed blocks once provider minio and its required_providers entry are deleted and MinIO is down

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-removal-1/spike.sh
```

## Outcome

With `removed { lifecycle { destroy = false } }` blocks for `module.buckets` and every root `minio_*` resource, and with `provider "minio"` and its `required_providers` entry deleted, `terraform init` succeeds (it installs aminueza/minio from the lock file because state needs it) but `terraform plan` fails: "Missing required argument: minio_server" and "Provider aminueza/minio requires explicit configuration". All 9 resources stay in state.
Terraform must configure the provider even for resources it only forgets, so dropping state and dropping the provider cannot happen in one change. This confirms risk 1. MinIO was stopped, so the run did not test whether a configured provider also needs MinIO reachable (see spike 2).
Local run: terraform 1.16.5, aminueza/minio 3.8.3, and community image pgsty/minio because the repo's minio/minio image no longer pulls. Bucket, object, user and policies were all still on MinIO afterward.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-removal-1/spike.sh`, which the command used
