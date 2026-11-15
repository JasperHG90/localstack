---
type: spike
title: Spike ov-sync-consumer/11
description: under Nomad 2.0.4 and nomad-driver-podman 0.6.4 (podman 3.4.4), if a prestart sidecar owns the network namespace and publishes the static ports and the main task joins it with network_mode "task:<sidecar>", is the main task reachable from outside, on loopback and outbound, and can it restart alone?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T20:40:58+00:00'
slug: ov-sync-consumer
n: 11
outcome_written: true
---

# Spike ov-sync-consumer/11

under Nomad 2.0.4 and nomad-driver-podman 0.6.4 (podman 3.4.4), if a prestart sidecar owns the network namespace and publishes the static ports and the main task joins it with network_mode "task:<sidecar>", is the main task reachable from outside, on loopback and outbound, and can it restart alone?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc5/spike.sh
```

## Outcome

Ran locally (Nomad 2.0.4 dev agent, nomad-driver-podman 0.6.4, podman 3.4.4 on jammy, busybox standing in for both tasks), not on the cluster. Prestart sidecar r owned the netns and published group static port 18333 to 8333, and main task a joined with `network_mode = "task:r"`. The driver resolved this to `container:<r's id>` when it created a, and both tasks had the same netns inode. The port binding sat on r only (`8333/tcp,udp -> 172.17.0.2:18333`, a had none).
Before restart: a separate docker container reached a through 172.17.0.2:18333, r reached a on 127.0.0.1:8333, and a reached 172.17.0.2:4646 outside the namespace.
`nomad alloc restart <alloc> a` restarted a alone. The alloc stayed `running`, r was untouched (0 restarts), and all three checks passed again, served by a new a container. But the restart was not clean: a's first new start exited 1 within a second, the driver logged "cannot stop container, status code: 500" for the old container, and a came back after a ~16s restart delay with Restarts=2. The cause was not captured (stderr was empty), so under the service default (2 attempts in 30m) one restart of SeaweedFS can use up an attempt.
`nomad alloc restart <alloc> r` failed the whole alloc, as in spike 9 ("failed to remove dead container ... 500", a killed as "Sibling Task Failed").
Source, v0.6.4: `portMappings()` (driver.go:911, 1627) runs whatever the network mode is, so ports go on the owner's container. podman 3.4.4 also accepted `-p` together with `--network container:r` at create time. Whether such a binding does anything was not tested.
Settles risk 4 for "SeaweedFS restarts alone" when the receiver owns the namespace. What remains: restarting the receiver reschedules the alloc, and an in-place SeaweedFS restart costs one extra failed start.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc5/spike.sh`, which the command used
