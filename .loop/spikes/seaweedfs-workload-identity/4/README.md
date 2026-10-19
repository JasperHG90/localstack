---
type: spike
title: Spike seaweedfs-workload-identity/4
description: with RoleArn and RoleSessionName added, do the loki shell helper and tempo minio-go get SeaweedFS creds for their own per-job role, write their bucket, and get refused on the other job role
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T18:14:45+00:00'
slug: seaweedfs-workload-identity
n: 4
outcome_written: true
---

# Spike seaweedfs-workload-identity/4

with RoleArn and RoleSessionName added, do the loki shell helper and tempo minio-go get SeaweedFS creds for their own per-job role, write their bucket, and get refused on the other job role

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-wi-4/spike.sh
```

## Outcome

With the plan's fixes, both clients work on SeaweedFS 4.48 against per-job trust-policy roles (spike 2's role config: `oidc:nomad_job_id` plus `oidc:sub` conditions, `defaultEffect: Deny`). All 4 of 4 checks passed.
- Shell helper from `loki.hcl`, with only `&RoleArn=<LokiRole>&RoleSessionName=loki` added to the query string: a loki token got creds and the `sed` parsed them, and a PutObject to `loki` with those creds succeeded. The same helper asking for TempoRole got 403 ("trust policy denies web identity assumption").
- minio-go v7.1.0 `credentials.IAM` (as Tempo 2.10.8 sets it up) with `AWS_ROLE_ARN=TempoRole`: a tempo token got creds and wrote to `tempo`. A loki token with the same role was refused with the same 403, and the chain fell back to anonymous creds with no error, as spike 3 found.
- Confirms the fix for risk 2. Limits: fake issuer, 2 jobs, buckets made with `weed shell`; the registry helper was not run separately (spike 3 showed it is byte-identical to loki's).

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-wi-4/spike.sh`, which the command used
- `files/main.go`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-wi-4/main.go`, which the command used
- `files/iam.json`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-wi-4/iam.json`, which the command used
- `files/issuer.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-wi-4/issuer.py`, which the command used
