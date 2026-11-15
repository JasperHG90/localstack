---
type: spike
title: Spike ov-sync-consumer/9
description: under Nomad 2.0.4 and nomad-driver-podman 0.6.4 (podman 3.4.4 as on jammy), does a poststart sidecar with network_mode "task:<main>" share the main task network namespace, reach it on 127.0.0.1 and off-namespace addresses, and keep working after the main task alone restarts?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T20:33:59+00:00'
slug: ov-sync-consumer
n: 9
outcome_written: true
---

# Spike ov-sync-consumer/9

under Nomad 2.0.4 and nomad-driver-podman 0.6.4 (podman 3.4.4 as on jammy), does a poststart sidecar with network_mode "task:<main>" share the main task network namespace, reach it on 127.0.0.1 and off-namespace addresses, and keep working after the main task alone restarts?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc4/spike.sh
```

## Outcome

Ran locally, not on the cluster: a Nomad 2.0.4 dev agent with nomad-driver-podman 0.6.4 and podman 3.4.4 (Ubuntu jammy, orangepi4a's OS) in a privileged container. Busybox stood in for SeaweedFS.
The sharing works. Sidecar b with `network_mode = "task:a"` got `container:<a's id>`, the same netns inode as a, reached a's listener on 127.0.0.1:9000, and reached an address outside the namespace (the agent at 172.17.0.2:4646). In v0.6.4 the driver turns `task:X` into `X-<alloc id>` at create time (driver.go:826).
Restarting a alone breaks it. `nomad alloc restart <alloc> a` stopped a, the driver's delete got a 500 while b still held a's namespace, and the next StartTask failed "failed to remove dead container" as unrecoverable. The whole alloc went `failed` and Nomad placed a fresh alloc (new a and b, sharing again). b never kept receiving through a's restart. A crash of a takes the same StartTask path, but this run only tested the user restart. The 500's body was not captured: the old container deleted cleanly once b had stopped, which points to the dependent-container rule.
Exit 1: risk 4 holds for "keeps receiving after the seaweedfs task alone restarts", and does not hold for sharing, loopback or outbound. Side note: on podman 6.1.3 the same restart hung instead, because the driver read the 500 from stats of a stopped container as "still running".

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc4/spike.sh`, which the command used
