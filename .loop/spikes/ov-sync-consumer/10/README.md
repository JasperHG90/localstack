---
type: spike
title: Spike ov-sync-consumer/10
description: under Nomad 2.0.4 and nomad-driver-podman 0.6.4 (podman 3.4.4), if a prestart sidecar owns the network namespace and publishes the static ports and the main task joins it with network_mode "task:<sidecar>", is the main task reachable from outside, on loopback and outbound, and can it restart alone?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T20:40:56+00:00'
slug: ov-sync-consumer
n: 10
outcome_written: true
---

# Spike ov-sync-consumer/10

under Nomad 2.0.4 and nomad-driver-podman 0.6.4 (podman 3.4.4), if a prestart sidecar owns the network namespace and publishes the static ports and the main task joins it with network_mode "task:<sidecar>", is the main task reachable from outside, on loopback and outbound, and can it restart alone?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc5/spike.sh
```

## Outcome

Harness bug, superseded by spike:ov-sync-consumer/11: the outside check read the wrong `docker inspect` field and hit `:18333` with no host, and busybox `date` has no `%N`, so the check never compared two values. The parts it did measure matched run 11: the job started, r and a shared a netns, loopback and outbound worked, `alloc restart a` kept the alloc running, and `alloc restart r` failed the alloc.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc5/spike.sh`, which the command used
