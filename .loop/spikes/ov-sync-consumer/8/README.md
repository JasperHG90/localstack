---
type: spike
title: Spike ov-sync-consumer/8
description: does the SeaweedFS 4.48 filer gocdk_pub_sub notifier (the rejected alternative to the webhook) publish filer events into a NATS JetStream stream, and what does it send?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T20:16:29+00:00'
slug: ov-sync-consumer
n: 8
outcome_written: true
---

# Spike ov-sync-consumer/8

does the SeaweedFS 4.48 filer gocdk_pub_sub notifier (the rejected alternative to the webhook) publish filer events into a NATS JetStream stream, and what does it send?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/loopspikes/nats/nats.sh
```

## Outcome

Ran locally with Docker: `nats:2.11-alpine -js`, a stream `SWFS` on `seaweedfs.filer.events`, and `chrislusf/seaweedfs:4.48_full` with `[notification.gocdk_pub_sub] topic_url = "nats://seaweedfs.filer.events"` and `NATS_SERVER_URL`. One bucket, one upload and one delete of `ov-sync/JasperHG90/localstack/docs/a.md` put 10 messages in the stream: six folder and `/buckets/.system` events, then the `a.md` create and delete (stdout.txt).

What it shows about the rejected path: the notifier works, but it has no path filter, so every write on the filer lands in the stream; each body is a gocloud gob envelope around a protobuf `EventNotification`, with the path readable only from the envelope's `key` metadata; and it needs the `_full` image, because the standard 4.48 image is built without the `gocdk` tag. gocloud `natspubsub` v0.46 publishes core NATS, so the filer never learns whether JetStream stored an event. This backs choosing the webhook (spike:ov-sync-consumer/4 and spike:ov-sync-consumer/5 cover the webhook under the job's args). It re-creates a run from an earlier session whose script was lost.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/nats.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/loopspikes/nats/nats.sh`, which the command used
