---
type: spike
title: Spike ov-sync-consumer/11
description: under Nomad 2.0.4 and nomad-driver-podman 0.6.4 (podman 3.4.4), if a prestart sidecar owns the network namespace and publishes the static ports and the main task joins it with network_mode "task:<sidecar>", is the main task reachable from outside, on loopback and outbound, and can it restart alone?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T20:40:31+00:00'
slug: ov-sync-consumer
n: 11
outcome_written: false
---

# Spike ov-sync-consumer/11

under Nomad 2.0.4 and nomad-driver-podman 0.6.4 (podman 3.4.4), if a prestart sidecar owns the network namespace and publishes the static ports and the main task joins it with network_mode "task:<sidecar>", is the main task reachable from outside, on loopback and outbound, and can it restart alone?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc5/spike.sh
```

## Outcome

Not written yet: `loopctl plan spike-note ov-sync-consumer 11`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc5/spike.sh`, which the command used
