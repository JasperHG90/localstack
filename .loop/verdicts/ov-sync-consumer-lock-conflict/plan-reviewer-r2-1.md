---
type: verdict
title: 'Verdict: ov-sync-consumer-lock-conflict plan-reviewer round 2'
description: 'plan-reviewer verdict for round 2 of ov-sync-consumer-lock-conflict: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-16T09:05:47+00:00'
slug: ov-sync-consumer-lock-conflict
pass: plan-reviewer
round: 2
body_schema: verdict/1
---

## Summary

The revised plan changes only how a lock-timeout 409 is logged. Delivery,
backoff, MAX_TRIES and dead-lettering stay as they are. Nothing it rests on is
missing from the repo, and no unlisted risk could break it.

## Checked

- consumer.go handle(): one branch decides dead-letter (errBadEvent or
  delivered >= MaxTries), then WARN plus NakWithDelay(Backoff(delivered)).
  Adding an errors.Is check for a lock sentinel before the WARN, after the
  dead-letter branch, gives r1 and r2 without touching delivery.
- openviking.go do() builds the error with fmt.Errorf from the envelope's
  Code and Message. Every caller (Write, Delete, remove, removeIfEmpty)
  wraps with %w, so a sentinel returned from do() survives up to handle() and
  through catch-up's errors.Join. Delete's 404-as-done means a redelivered
  event whose file delete already landed goes on to the folder cleanup.
- catchup.go: the folder-delete path goes through remove() under the key
  lock. The pass runs every CATCHUP_INTERVAL (15m), so a swallowed busy delete
  is tried again next pass. Delivery cannot get worse.
- Per-key lock from ov-sync-consumer-reviewer-f3 is on main (commit
  4d0cdfd4). Both roots pin v0.1.0 today. The module justfile's release
  recipe reads the tag from the applications root and refuses a mismatch with
  infrastructure, so bumping both lines is the whole release step. test-one
  fails when the named test did not run.

## Findings

p1 (resolved): the plan no longer relies on an in-process retry outlasting
the lock. JetStream redelivery carries the retry, as it already did in the
first live sync, where every file got through.

## Notes

- Catch-up's missing-file writes (Apply) can also hit the lock and would still
  log WARN "catch-up pass failed". The plan scopes catch-up to folder deletes
  and r5 judges only the event path, so this does not break the plan. The
  builder may cover it in the same change.
- A lock held past about eight minutes still dead-letters. That is today's
  behavior and the plan keeps it on purpose. Catch-up repairs the file.
