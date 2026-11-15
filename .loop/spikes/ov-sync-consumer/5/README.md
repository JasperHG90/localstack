---
type: spike
title: Spike ov-sync-consumer/5
description: with the seaweedfs.hcl -ip.bind=127.0.0.1 kept, does a loopback listener in the same network namespace (a group sidecar) get the filer webhook events, and does dropping -ip.bind let them reach another container?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T19:57:05+00:00'
slug: ov-sync-consumer
n: 5
outcome_written: true
---

# Spike ov-sync-consumer/5

with the seaweedfs.hcl -ip.bind=127.0.0.1 kept, does a loopback listener in the same network namespace (a group sidecar) get the filer webhook events, and does dropping -ip.bind let them reach another container?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc2/webhook_variants.sh
```

## Outcome

This run is a control for spike 4, with two variants.
A: all `seaweedfs.hcl` args kept, listener on loopback in the seaweed container's network namespace (`http://127.0.0.1:20500`). All 4 events arrived, each as JSON with the bearer header: create `docs/a.md`, create `docs` (the folder), update `docs/a.md`, delete `docs/a.md`. Each body has `event_type`, `key` and `message`, and nothing came from bucket `other`.
B: `-ip.bind` dropped, `-ip=127.0.0.1` kept. Still 0 delivered, with the same `127.0.0.1:0->` dial error, and netstat shows the filer ports still on loopback. So `-ip=127.0.0.1` is what pins the webhook's source address (and `-ip.bind` defaults to it), not `-ip.bind` alone.
Takeaway: under this job's args the webhook only works toward a loopback endpoint in the same network namespace. Two ways out: a relay sidecar in the seaweedfs group, or changing `-ip`. A sidecar would also need to share a network namespace with the seaweedfs task, which this run did not test under Nomad podman. Exit 1 because B failed, as expected.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/webhook_variants.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc2/webhook_variants.sh`, which the command used
