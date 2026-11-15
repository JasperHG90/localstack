---
type: spike
title: Spike ov-sync-consumer/5
description: with the seaweedfs.hcl -ip.bind=127.0.0.1 kept, does a loopback listener in the same network namespace (a group sidecar) get the filer webhook events, and does dropping -ip.bind let them reach another container?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T19:56:03+00:00'
slug: ov-sync-consumer
n: 5
outcome_written: false
---

# Spike ov-sync-consumer/5

with the seaweedfs.hcl -ip.bind=127.0.0.1 kept, does a loopback listener in the same network namespace (a group sidecar) get the filer webhook events, and does dropping -ip.bind let them reach another container?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc2/webhook_variants.sh
```

## Outcome

Not written yet: `loopctl plan spike-note ov-sync-consumer 5`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/webhook_variants.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc2/webhook_variants.sh`, which the command used
