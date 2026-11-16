---
type: plan
title: 'Plan: ov-sync-consumer-lock-conflict'
description: Retry OpenViking's lock-timeout 409 inside the event, and ship it with the per-key lock as consumer v0.1.1.
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
`/api/v1/content/write` and `DELETE /api/v1/fs`. OpenViking holds a lock on
the tree it writes into and gives up after about 150 ms when another write
holds it. The consumer turns any non-2xx into a failed event, so JetStream
redelivers it after a backoff measured in seconds to minutes: one file took 5
deliveries and the burst took over 20 minutes. Catch-up's folder deletes fail
the same way.

`applications/ov-sync-consumer/internal/consumer/openviking.go` retries a
409 whose body says the lock acquire timed out, inside the same request
slot's caller, a few times with short jittered backoff (hundreds of
milliseconds), before it returns an error. Any other 409, and every other
status, behaves as today. The request slot (`MaxInFlight`) is released
while it waits, so a retry never holds a slot during its sleep.

Then the image goes to `v0.1.1` in both roots' `ov_sync_consumer_image`
lines (`deployments/applications/services.tf` and
`deployments/infrastructure/services.tf`), carrying this and the per-key lock
from `ov-sync-consumer-reviewer-f3`.

Outcome: a test with a fake OpenViking that answers lock-timeout 409 twice
then 200 sees one successful write and no failed event; a non-lock 409 still
fails the event; both roots name `v0.1.1`. After the operator releases and
applies, a burst sync logs no `event failed` line for a 409.

## Could invalidate this plan

- none
