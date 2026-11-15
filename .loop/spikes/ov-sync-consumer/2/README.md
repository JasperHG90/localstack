---
type: spike
title: Spike ov-sync-consumer/2
description: does the SeaweedFS 4.48 filer webhook post filtered bearer-authed JSON events for ov-sync PUT and DELETE to a listener in another container when weed runs with the seaweedfs.hcl args, loopback binds included?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T19:57:02+00:00'
slug: ov-sync-consumer
n: 2
outcome_written: true
---

# Spike ov-sync-consumer/2

does the SeaweedFS 4.48 filer webhook post filtered bearer-authed JSON events for ov-sync PUT and DELETE to a listener in another container when weed runs with the seaweedfs.hcl args, loopback binds included?

The command exited 126:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc2/webhook_job_shape.sh
```

## Outcome

Not a result. The script lacked its executable bit, so `/bin/sh` refused it (exit 126) before any container started. spike:ov-sync-consumer/4 is the same script run properly.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/webhook_job_shape.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc2/webhook_job_shape.sh`, which the command used
