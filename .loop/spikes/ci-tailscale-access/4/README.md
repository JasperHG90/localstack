---
type: spike
title: Spike ci-tailscale-access/4
description: does an ephemeral tag:ci node joined with --accept-routes reach vault, openviking-api and s3 .lab on 443 and time out on 192.168.2.30:22, :8200, 192.168.2.50:1933, 192.168.2.29:8333 and firebat tailnet :8200?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T19:55:59+00:00'
slug: ci-tailscale-access
n: 4
outcome_written: true
---

# Spike ci-tailscale-access/4

does an ephemeral tag:ci node joined with --accept-routes reach vault, openviking-api and s3 .lab on 443 and time out on 192.168.2.30:22, :8200, 192.168.2.50:1933, 192.168.2.29:8333 and firebat tailnet :8200?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ts12/check_run.sh 43754977347 reach
```

## Outcome

Same run 43754977347: the join failed with a 403 at the token exchange (see spike 3), so the reach checks were skipped. No reach, timeout or firebat result exists, and nothing about reach is ruled in or out.
Ephemerality was only checked from the source: v4's dist/index.js hardcodes `--client-id=...?preauthorized=true&ephemeral=true`, and its post step ran `tailscale logout`. No live node was seen joining or leaving.
Settles risk 1: no, the spike could not answer it. Rerun the reach-probe workflow (its PASS/FAIL table is in files/reach.yaml) once the federated subject matches the immutable-ID `sub`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/check_run.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ts12/check_run.sh`, which the command used
- `files/join-action.yml`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ts12/join-action.yml`, which the command used
- `files/reach.yaml`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ts12/reach.yaml`, which the command used
