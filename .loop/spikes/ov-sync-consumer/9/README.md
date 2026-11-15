---
type: spike
title: Spike ov-sync-consumer/9
description: under Nomad 2.0.4 and nomad-driver-podman 0.6.4 (podman 3.4.4 as on jammy), does a poststart sidecar with network_mode "task:<main>" share the main task network namespace, reach it on 127.0.0.1 and off-namespace addresses, and keep working after the main task alone restarts?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T20:33:38+00:00'
slug: ov-sync-consumer
n: 9
outcome_written: false
---

# Spike ov-sync-consumer/9

under Nomad 2.0.4 and nomad-driver-podman 0.6.4 (podman 3.4.4 as on jammy), does a poststart sidecar with network_mode "task:<main>" share the main task network namespace, reach it on 127.0.0.1 and off-namespace addresses, and keep working after the main task alone restarts?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc4/spike.sh
```

## Outcome

Not written yet: `loopctl plan spike-note ov-sync-consumer 9`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc4/spike.sh`, which the command used
