---
type: spike
title: Spike ci-tailscale-access/6
description: does an ephemeral tag:ci runner joined through the federated identity reach vault, openviking-api and s3 on 443 and time out on 192.168.2.30:22, :8200, 192.168.2.50:1933, 192.168.2.29:8333 and firebat tailnet :8200?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T21:38:01+00:00'
slug: ci-tailscale-access
n: 6
outcome_written: true
---

# Spike ci-tailscale-access/6

does an ephemeral tag:ci runner joined through the federated identity reach vault, openviking-api and s3 on 443 and time out on 192.168.2.30:22, :8200, 192.168.2.50:1933, 192.168.2.29:8333 and firebat tailnet :8200?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/ts-spike/check_run.sh 43764572127 reach
```

## Outcome

Same run as spike:ci-tailscale-access/5 (Actions run 43764572127, localstack branch `spike/lab-auth-reach`). The `with-env` job, joined as `tag:ci` with v4's default `--accept-routes`, reached `https://vault.lab.orangecluster.nl/v1/sys/health` (200), `https://openviking-api.lab.orangecluster.nl/health` (200) and `https://s3.lab.orangecluster.nl` (403, an unauthenticated S3 answer, so reachable). It timed out on 192.168.2.30:22, 192.168.2.30:8200, 192.168.2.50:1933, 192.168.2.29:8333 and firebat's tailnet address 100.117.172.3:8200 (stdout.txt). So the saved policy holds live: a `tag:ci` node gets the edge on 443 through the subnet route and nothing else. Ephemerality was not read from the netmap (the probe printed "unknown"); v4 requests `ephemeral=true&preauthorized=true` and its post step ran `tailscale logout`, so the node is removed at job end.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/check_run.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/ts-spike/check_run.sh`, which the command used
