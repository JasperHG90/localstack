---
type: plan
title: 'Plan: ov-sync-consumer-lock-conflict'
description: Treat OpenViking's lock-timeout 409 as an expected busy folder, quiet it, and ship it with the per-key lock as consumer v0.1.1.
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T08:42:49+00:00'
slug: ov-sync-consumer-lock-conflict
epic: null
depends_on: []
priority: null
---

# ov-sync-consumer-lock-conflict

<!-- This template was registered in planning. To capture an idea as a stub
instead (intent for later, promoted by the operator), write the plan with
`status: draft` in its front matter before running loopctl ticket register.
A hand-written plan's front matter needs type: plan, title, description and
slug; loopctl ticket register fills in generated. Optional: epic, depends_on,
priority, status, strictness and blocking. -->

Relayed from: none

## Intent

The first live sync (2026-11-16, run 43818142026, 189 files) logged dozens of
`HTTP 409: CONFLICT: lock acquire timed out after ~150ms` from
`/api/v1/content/write` and `DELETE /api/v1/fs`, each as a WARN
`event failed, retrying`. Every file got through: the consumer allows
`MAX_TRIES` 20 deliveries with backoff from 2 s doubling to 30 s
(`applications/ov-sync-consumer/main.go`). The lock is not brief. One file
hit it five times over about 3.5 minutes (`set-up-the-nats-cli.md`, 07:01:13
to 07:04:47), and failures came in bursts by folder (three `docs/how-to/`
files within 130 ms at 07:01:13, three `docs/reference/` files at 07:06:54).
Spike `ov-sync-consumer/3` showed OpenViking's own folder-summary job
(`semantic_dag`) failing on the same lock, so a folder lock held by that job
is the likely cause. What holds the lock and for how long is not measured;
the operator chose to quiet the symptom now and measure later.

`applications/ov-sync-consumer/internal/consumer/openviking.go` returns a
distinct error for a 409 whose message says the lock acquire timed out. The
consumer's failure path in `consumer.go` keeps JetStream's redelivery
unchanged for it (same backoff, same `MAX_TRIES`, still dead-lettered on the
last try), but logs it at INFO as `folder busy, retrying later` with the URI
and delivery count instead of WARN `event failed`. Catch-up does the same for
a folder delete that hits it. Any other 409, and every other status, behaves
as today. Delivery is unchanged, so this cannot make it worse.

Then the image goes to `v0.1.1` in both roots' `ov_sync_consumer_image`
lines (`deployments/applications/services.tf` and
`deployments/infrastructure/services.tf`), carrying this and the per-key lock
from `ov-sync-consumer-reviewer-f3`.

Outcome: a fake OpenViking answering a lock-timeout 409 makes the event
redeliver with the usual backoff and log an INFO `folder busy` line and no
WARN; a non-lock 409 still logs WARN `event failed`; the last allowed try of a
lock 409 still dead-letters; both roots name `v0.1.1`. Speeding up bursts is
the stub `ov-sync-consumer-lock-scope`.

## Could invalidate this plan

- none
