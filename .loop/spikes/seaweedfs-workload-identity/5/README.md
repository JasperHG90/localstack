---
type: spike
title: Spike seaweedfs-workload-identity/5
description: with -s3.config admin, -s3.iam.readOnly=false and an -s3.iam.config holding OIDC, STS and defaultEffect Deny on one weed server, do the static admin, Terraform-made users and per-job STS roles all still work, across a restart, with a clean second plan
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T20:56:54+00:00'
slug: seaweedfs-workload-identity
n: 5
outcome_written: false
---

# Spike seaweedfs-workload-identity/5

with -s3.config admin, -s3.iam.readOnly=false and an -s3.iam.config holding OIDC, STS and defaultEffect Deny on one weed server, do the static admin, Terraform-made users and per-job STS roles all still work, across a restart, with a clean second plan

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-wi-5/spike.sh
```

## Outcome

Not written yet: `loopctl plan spike-note seaweedfs-workload-identity 5`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-wi-5/spike.sh`, which the command used
- `files/probe.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-wi-5/probe.py`, which the command used
- `files/iam.json`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-wi-5/iam.json`, which the command used
- `files/s3.json`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-wi-5/s3.json`, which the command used
- `files/main.tf`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-wi-5/main.tf`, which the command used
- `files/issuer.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-wi-5/issuer.py`, which the command used
