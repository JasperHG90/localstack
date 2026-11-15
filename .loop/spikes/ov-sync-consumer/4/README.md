---
type: spike
title: Spike ov-sync-consumer/4
description: does the SeaweedFS 4.48 filer webhook post filtered bearer-authed JSON events for ov-sync PUT and DELETE to a listener in another container when weed runs with the seaweedfs.hcl args, loopback binds included?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T19:57:03+00:00'
slug: ov-sync-consumer
n: 4
outcome_written: true
---

# Spike ov-sync-consumer/4

does the SeaweedFS 4.48 filer webhook post filtered bearer-authed JSON events for ov-sync PUT and DELETE to a listener in another container when weed runs with the seaweedfs.hcl args, loopback binds included?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc2/webhook_job_shape.sh
```

## Outcome

**Risk 2 is real.** SeaweedFS 4.48 started with the exact `seaweedfs.hcl` args (`-ip=127.0.0.1 -ip.bind=127.0.0.1`, S3 on 0.0.0.0, the services.tf IAM config) loads `[notification.webhook]` and applies the filter correctly: it queued events for `/buckets/ov-sync/docs/a.md` and `/buckets/ov-sync/docs` (create, update, delete), and none for the `other` bucket.
No event reached the listener in a second container: 0 delivered. Every POST failed with `dial tcp 127.0.0.1:0->172.18.0.2:20500: connect: invalid argument` and went to dead letter. The webhook client takes 127.0.0.1 as its source address, so it cannot reach anything outside the container's loopback. Firewall rules on radxa cannot fix this.
Limits: one local Docker run on arm64. Docker bridge, not podman.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/webhook_job_shape.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ovc2/webhook_job_shape.sh`, which the command used
