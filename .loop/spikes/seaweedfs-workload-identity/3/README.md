---
type: spike
title: Spike seaweedfs-workload-identity/3
description: do the loki/registry shell credential_process helper and tempo minio-go web identity provider get SeaweedFS STS credentials unchanged (no RoleArn), and what must each send?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T18:03:25+00:00'
slug: seaweedfs-workload-identity
n: 3
outcome_written: true
---

# Spike seaweedfs-workload-identity/3

do the loki/registry shell credential_process helper and tempo minio-go web identity provider get SeaweedFS STS credentials unchanged (no RoleArn), and what must each send?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-wi-2/spike.sh
```

## Outcome

Against SeaweedFS 4.48, neither client works unchanged. SeaweedFS rejects every web-identity request without `RoleSessionName` (400 MissingParameter). Without claim mode it also needs `RoleArn` (403 "RoleArn is required when claim-based policy mode is not configured").
- Shell helper (loki and registry are byte-identical): adding `&RoleSessionName=<job>` to the query string is enough. SeaweedFS accepts the query string on an empty POST, and the success XML has the same `AccessKeyId`/`SecretAccessKey`/`SessionToken`/`Expiration` elements, so the `sed` works unchanged. Add `&RoleArn=` too in role mode.
- minio-go v7.1.0 (tempo 2.10.8): with no `AWS_ROLE_ARN` it fails with "RoleSessionName is required", and the chain falls back to anonymous creds silently. minio-go sends `RoleSessionName` (generated) only when a RoleArn is set. With `AWS_ROLE_ARN` set to the role ARN, or to the sentinel `arn:aws:iam:::role/sts-claim-based` with `policyClaim: nomad_job_id`, it got creds and PutObject to `tempo` succeeded.
- Settles risk 2 as real but cheap: each client needs one parameter or env var. Limits: fake issuer, issuer-only trust policy; per-job binding is risk 1's question.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-wi-2/spike.sh`, which the command used
- `files/main.go`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-wi-2/main.go`, which the command used
