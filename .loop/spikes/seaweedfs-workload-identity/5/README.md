---
type: spike
title: Spike seaweedfs-workload-identity/5
description: with -s3.config admin, -s3.iam.readOnly=false and an -s3.iam.config holding OIDC, STS and defaultEffect Deny on one weed server, do the static admin, Terraform-made users and per-job STS roles all still work, across a restart, with a clean second plan
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T20:57:08+00:00'
slug: seaweedfs-workload-identity
n: 5
outcome_written: true
---

# Spike seaweedfs-workload-identity/5

with -s3.config admin, -s3.iam.readOnly=false and an -s3.iam.config holding OIDC, STS and defaultEffect Deny on one weed server, do the static admin, Terraform-made users and per-job STS roles all still work, across a restart, with a clean second plan

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-wi-5/spike.sh
```

## Outcome

One `weed server` (4.48) with `-s3.config` admin, `-s3.iam.readOnly=false`, `-s3.iam.config` (OIDC provider, STS signing key, `policy.defaultEffect: Deny`, a `wi-probe` role bound by `nomad_job_id`/`sub`), the service/3 slot flags and master.toml passed 33 of 33 checks, before and after `docker restart`.
The static admin still created buckets, put/got and read every bucket. hashicorp/aws (~> 6.0) applied a bucket, user, access key and inline policy (4 added), and both the second plan and the post-restart plan were clean (exit 0).
The Terraform key put/got its own bucket and was denied on the admin bucket, the STS bucket and CreateBucket. A wi-probe token got creds for the wi-probe role and wrote its bucket only. A wi-probe-other token asking for that role got HTTP 403.
Rules out `defaultEffect: Deny` or the IAM file changing how static or API-made identities are authorized. Settles risk 4. Limits: local container with a fake issuer, one role and one Terraform user; `roleMapping` was left out (STS ignores it, per spike 2).

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
