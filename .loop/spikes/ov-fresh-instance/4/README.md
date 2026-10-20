---
type: spike
title: Spike ov-fresh-instance/4
description: on SeaweedFS 4.48, does moving the openviking user's Terraform inline policy from bucket openviking to openviking-v2 (policy renamed, same user and key) apply, keep the key, plan clean, and deny the key on openviking while it keeps full access to openviking-v2?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T14:36:47+00:00'
slug: ov-fresh-instance
n: 4
outcome_written: false
---

# Spike ov-fresh-instance/4

on SeaweedFS 4.48, does moving the openviking user's Terraform inline policy from bucket openviking to openviking-v2 (policy renamed, same user and key) apply, keep the key, plan clean, and deny the key on openviking while it keeps full access to openviking-v2?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovpolicy/spike.sh
```

## Outcome

Not written yet: `loopctl plan spike-note ov-fresh-instance 4`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovpolicy/spike.sh`, which the command used
- `files/main.tf`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovpolicy/main.tf`, which the command used
- `files/probe.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovpolicy/probe.py`, which the command used
- `files/s3.json`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovpolicy/s3.json`, which the command used
- `files/iam.json`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovpolicy/iam.json`, which the command used
