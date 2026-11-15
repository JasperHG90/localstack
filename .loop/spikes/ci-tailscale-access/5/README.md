---
type: spike
title: Spike ci-tailscale-access/5
description: from a lab-Environment job in localstack (legacy OIDC subject) calling the join composite action by its remote ref, does tailscale/github-action@v4 join with only the federated client id, audience and tag, and does a job without the environment fail to join?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T21:37:26+00:00'
slug: ci-tailscale-access
n: 5
outcome_written: false
---

# Spike ci-tailscale-access/5

from a lab-Environment job in localstack (legacy OIDC subject) calling the join composite action by its remote ref, does tailscale/github-action@v4 join with only the federated client id, audience and tag, and does a job without the environment fail to join?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/ts-spike/check_run.sh 43764572127 join
```

## Outcome

Not written yet: `loopctl plan spike-note ci-tailscale-access 5`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/check_run.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/ts-spike/check_run.sh`, which the command used
- `files/lab-auth-reach-spike.yaml`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/ts-spike/repo/.github/workflows/lab-auth-reach-spike.yaml`, which the command used
- `files/action.yml`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/ts-spike/repo/.github/actions/join/action.yml`, which the command used
