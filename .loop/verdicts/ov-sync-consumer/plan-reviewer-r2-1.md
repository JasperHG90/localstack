---
type: verdict
title: 'Verdict: ov-sync-consumer plan-reviewer round 2'
description: 'plan-reviewer verdict for round 2 of ov-sync-consumer: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-15T20:47:12+00:00'
slug: ov-sync-consumer
pass: plan-reviewer
round: 2
body_schema: verdict/1
---

## Summary

p1 is resolved. The receiver now has to start and stay up without NATS,
reconnect forever, answer non-2xx while it cannot publish, run with memory
headroom, and leave its token template on `change_mode = "noop"`. Tests cover
starting without NATS and a failed publish that does not exit. I checked the
SeaweedFS 4.48 webhook source to see what non-2xx does on the filer side. It
does not stall S3 for other apps. Moving the `seaweedfs` service and its check
to the receiver task fixes the empty-address problem from round 1. I found no
new risk that could break the plan.

## Checked

- SeaweedFS 4.48 `weed/notification/webhook`. `SendMessage` applies the
  `path_prefixes` filter before it queues anything, so only `ov-sync` events
  are buffered. It queues into a watermill gochannel with
  `BlockPublishUntilSubscriberAck` unset, so publishing hands off and returns.
  A receiver that answers non-2xx does not block the filer's write path for
  other buckets. On non-2xx (`http.go:155`) the router's Retry middleware
  tries again (defaults: 3 retries, 3 s backoff doubling up to 30 s), then
  dead-letters the event (`webhook_queue.go:133-148`). So "the webhook
  retries, catch-up repairs drops" matches the code. A NATS outage longer than
  about 20 s drops events, and the plan already leaves those to the catch-up
  pass.
- `deployments/infrastructure/services/seaweedfs.hcl`. The service and check
  use the `s3` port label with the default address mode. On the receiver task,
  which owns the port mapping and has a container IP, this resolves the same
  way it does on the seaweedfs task today. The check still reaches SeaweedFS
  through the shared namespace. Prometheus scrapes 192.168.2.29:9327
  directly, so that does not change.
- Image and network reach. orangepi4a and radxa are both arm64
  (`.okf/nodes/placement.md`), which fits the plan's arm64 build. Every host
  logs in to ghcr.io (`bootstrap/playbooks/configure_podman.yml`, `hosts:
  all`), so orangepi4a can pull the receiver image. The NATS firewall rule
  allows 192.168.0.0/16 on port 4222 (`deployments/infrastructure/services.tf:455`).
- Spike 11 again, for the restart-block claim. One in-place SeaweedFS restart
  cost one failed start, so asking for at least three attempts follows from it.

## Findings

- p1, resolved: the plan now sets how the receiver behaves without NATS and
  how that is tested. The SeaweedFS side of the non-2xx path holds, as shown
  above.

## Notes

- Not a finding. The seaweedfs task's `notification.toml` template will use
  the default `change_mode = "restart"`, while the receiver's token template
  is `noop`. If the bearer token ever rotates, SeaweedFS picks up the new
  token and the receiver keeps the old one, so webhooks get 401 until the
  receiver restarts. Catch-up repairs the gap. The random password only
  changes when someone rotates it on purpose.
- The receiver should answer non-2xx fast instead of waiting on a NATS
  publish, because the webhook times out after 10 s and each worker slot is
  held for that long. That is a build detail.
- The eval rows are still empty. The Outcome paragraph is ready to become
  rows.
