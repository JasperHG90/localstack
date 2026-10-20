---
type: spike
title: Spike ov-fresh-instance/4
description: on SeaweedFS 4.48, does moving the openviking user's Terraform inline policy from bucket openviking to openviking-v2 (policy renamed, same user and key) apply, keep the key, plan clean, and deny the key on openviking while it keeps full access to openviking-v2?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T14:37:02+00:00'
slug: ov-fresh-instance
n: 4
outcome_written: true
---

# Spike ov-fresh-instance/4

on SeaweedFS 4.48, does moving the openviking user's Terraform inline policy from bucket openviking to openviking-v2 (policy renamed, same user and key) apply, keep the key, plan clean, and deny the key on openviking while it keeps full access to openviking-v2?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovpolicy/spike.sh
```

## Outcome

On a local SeaweedFS 4.48 with the service's flags (`-s3.iam.readOnly=false`, `-s3.iam.config` with `defaultEffect: Deny`), a copy of the storage.tf shapes applied today's catalog (11 added), then the move: `aws_iam_user_policy.seaweedfs["openviking"]` replaced (`openviking-openviking` to `openviking-openviking-v2`), bucket `openviking-v2` created, backup policy updated in place (2 added, 1 changed, 1 destroyed, exit 0).
The access key id and secret were identical before and after, the user held one policy and one key, and the third plan was clean (exit 0).
The same key was then denied PutObject, GetObject, ListObjectsV2 and DeleteObject on `openviking` (the object stayed, admin still read it) and had put, get, list and delete on `openviking-v2`; the backup key read both buckets. All 15 checks held again after `docker restart`.
Rules out key loss or leftover access on the old bucket from the policy rename. Settles plan-review finding p1.
Limits: one node, a two-bucket catalog (loki, openviking) instead of all six, no OIDC provider in the IAM file, and the restore user was left out.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovpolicy/spike.sh`, which the command used
- `files/main.tf`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovpolicy/main.tf`, which the command used
- `files/probe.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovpolicy/probe.py`, which the command used
- `files/s3.json`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovpolicy/s3.json`, which the command used
- `files/iam.json`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovpolicy/iam.json`, which the command used
