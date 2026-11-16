---
type: verdict
title: 'Verdict: ov-sync-consumer-lock-conflict plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of ov-sync-consumer-lock-conflict: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-16T08:45:20+00:00'
slug: ov-sync-consumer-lock-conflict
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

The approach is sound in mechanism: retry inside do(), with no slot held while
it sleeps, an exact body match, and other statuses left alone. But the plan
lists no risks, and the one that matters is open. Nobody has checked that a
retry budget of about a second outlasts OpenViking's lock. The live logs and
spike ov-sync-consumer/3 suggest the lock can be held for tens of seconds, by
OpenViking's background summary job as well as by concurrent writes. In that
case the plan ships and row r5 fails. Settle the lock's scope and how long it
is held (spike or log timing) before building, then size the budget, or change
the approach, from that.

## Checked

- openviking.go: send() takes a MaxInFlight slot per request and frees it on
  return. A retry loop in do() around send() holds no slot while it sleeps, so
  r3 follows naturally. do() folds the body into `CODE: message` and parses
  the envelope first, so matching `env.Error.Message` against "lock acquire
  timed out" is possible.
- consumer.go: Apply holds the key lock, then tree.RLock, around Write.
  remove() holds tree.RLock for the file delete, then tree.Lock for
  removeIfEmpty's recursive deletes. catchup.go takes the key lock for its
  deletes. Retrying under these locks adds no deadlock: the 409's holder is on
  the server and never waits on a consumer lock, and nobody takes a second key.
- main.go: Pool = MaxInFlight = 4, 2 events/s, backoff 2 s doubling to 30 s,
  20 tries. Five deliveries therefore means contention that lasted about 30 s.
- Spike ov-sync-consumer/3 stdout: `semantic_dag - ERROR - Failed to dispatch
  directory ...: lock acquire timed out`. OpenViking's summary work competes
  for the same folder locks.
- The installed openviking 0.5.0 package is not the deployed v0.4.17.1-9 and
  lacks the error string, so I could not settle lock scope from source.

## Findings

p1: the retry budget's premise. How long the lock is held, and by what, is
unknown. The evidence (30 s of contention for one file, summary jobs taking
folder locks) suggests a budget of about a second does not cover it, and the
cure might be per-folder serialization or lower concurrency, not a retry. A
spike or the log timing answers it.

## Notes

Matching the 409 body text is safe as a failure mode. If OpenViking rewords the
message, the consumer falls back to today's behavior (fail the event and let
JetStream redeliver), never to a wrong success. A retried write or delete is
idempotent: a write replaces content, and a delete of a missing path is a 404,
which Delete treats as done. Retrying under the key lock and tree.RLock cannot
deadlock, but it holds those locks longer. Go's RWMutex blocks new readers once
a writer waits, so a removeIfEmpty waiting on tree.Lock stalls every worker
while a write retries. And a recursive folder delete that retries under
tree.Lock, against a summary job on that folder, stalls them all for its whole
budget. A budget of hundreds of milliseconds makes this harmless. If p1 leads to
a budget of tens of seconds, the plan should account for that stall.
