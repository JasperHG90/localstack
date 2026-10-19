---
type: spike
title: Spike seaweedfs-buckets/2
description: can hashicorp/aws manage SeaweedFS buckets, IAM users, access keys and inline user policies with a clean second plan?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T17:57:58+00:00'
slug: seaweedfs-buckets
n: 2
outcome_written: true
---

# Spike seaweedfs-buckets/2

can hashicorp/aws manage SeaweedFS buckets, IAM users, access keys and inline user policies with a clean second plan?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-buckets-1/spike.sh
```

## Outcome

Against SeaweedFS 4.48 (`weed server -s3`, admin from `-s3.config`), hashicorp/aws ~> 6.0 with s3 and iam endpoints on the S3 port created 2 `aws_s3_bucket`, 2 `aws_iam_user`, 2 `aws_iam_access_key` and 2 `aws_iam_user_policy` (8 added). The second plan was clean (exit 0) and stayed clean after a container restart, so bare `aws_s3_bucket` refresh does not fail and IAM state persists.
Trap: with default flags every IAM write fails, `403 AccessDenied: IAM write operations are disabled on this server`. The job must pass `-s3.iam.readOnly=false`.
The aminueza/minio provider is no fallback: `minio_s3_bucket` works, but `minio_iam_user` and `minio_iam_policy` fail with `reading IAM user (spike-gamma): The specified key does not exist.`
Settles risk 1. Limits: one node, did not test that the minted keys can sign requests or that the policy is enforced (risk 2).

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-buckets-1/spike.sh`, which the command used
