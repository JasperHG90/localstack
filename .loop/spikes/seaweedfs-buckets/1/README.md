---
type: spike
title: Spike seaweedfs-buckets/1
description: does SeaweedFS (4.48) deny a key scoped to one bucket on another bucket, via s3.config actions or IAM PutUserPolicy?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T17:56:36+00:00'
slug: seaweedfs-buckets
n: 1
outcome_written: true
---

# Spike seaweedfs-buckets/1

does SeaweedFS (4.48) deny a key scoped to one bucket on another bucket, via s3.config actions or IAM PutUserPolicy?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-buckets-2/spike.sh
```

## Outcome

On SeaweedFS 4.48 (single `weed server -s3`, boto3), both mechanisms isolate buckets: 32/32 checks matched, 0 mismatches each for s3.config actions (`Read:bkt-a`, `Write:bkt-a`, `List:bkt-a`) and for IAM API users with `PutUserPolicy` scoped to `arn:aws:s3:::bkt-a` and `bkt-a/*`.
writer-a could put/get/list/delete on bkt-a and got AccessDenied on all four against bkt-b; reader-a could get/list bkt-a and got AccessDenied on put/delete there and on everything in bkt-b; bkt-b's seed object survived.
ListBuckets leaks no names: each user saw only `['bkt-a']`, like MinIO. Gap: an IAM-policy user gets AccessDenied on `GetBucketLocation` unless the policy also grants `s3:GetBucketLocation` (static-action users get it), so add that action for clients that call it.
Limits: the IAM API needs `-s3.iam.readOnly=false` (default true), and the server logged "no signing key found for STS service" at start without breaking IAM user/policy calls. Rules out the "coarse per-identity actions only" failure. Settles risk 2.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-buckets-2/spike.sh`, which the command used
- `files/check.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-buckets-2/check.py`, which the command used
- `files/s3.json`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-buckets-2/s3.json`, which the command used
