---
type: spike
title: Spike lab-auth-immutable-subject/1
description: 'does the new Tailscale federated credential admit an immutable-subject repo''s environment: lab job when a composite step reads the OIDC sub and passes the chosen client and audience to tailscale/github-action?'
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-18T13:10:37+00:00'
slug: lab-auth-immutable-subject
n: 1
outcome_written: true
---

# Spike lab-auth-immutable-subject/1

does the new Tailscale federated credential admit an immutable-subject repo's environment: lab job when a composite step reads the OIDC sub and passes the chosen client and audience to tailscale/github-action?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/2e7fce49-b865-4028-af55-9a588a2debef/scratchpad/spike-lais/check_run.sh 44310680589
```

## Outcome

Run 44310680589 in `JasperHG90/lab-auth-probe` (commit bacd152) passed both checks. In the `environment: lab` job, a composite bash step read `sub` from its OIDC token (`repo:JasperHG90@8079803/lab-auth-probe@1459171707:environment:lab`), printed `SUB_FORMAT=immutable`, and passed client `T4Y1pq366F11CNTRL-kysCUqvnvH11CNTRL` and its audience to `tailscale/github-action@v4` as step outputs. `tailscale up` worked on attempt 1, and the reach table was `OVERALL=PASS` (vault and openviking 200, s3 403, all five raw ports closed).
The job with no environment (`sub` ending `:ref:refs/heads/main`) picked the same new credential and got a 403 at the token exchange, so the new credential admits only `:environment:lab`.
This rules out both halves of the risk: the new credential admits an immutable-subject repo's lab job, and a composite step can read `sub` and choose the credential. Settles risk 1: yes.
Limits: one repo and one run. The legacy-subject branch (old credential) did not run here, because this repo issues only immutable subjects.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/check_run.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/2e7fce49-b865-4028-af55-9a588a2debef/scratchpad/spike-lais/check_run.sh`, which the command used
- `files/action.yml`: a copy of `/tmp/claude-1000/-home-vscode-workspace/2e7fce49-b865-4028-af55-9a588a2debef/scratchpad/spike-lais/probe/.github/actions/join/action.yml`, which the command used
