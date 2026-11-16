---
type: verdict
title: 'Verdict: ov-sync-consumer-lock-conflict reviewer round 2'
description: 'reviewer verdict for round 2 of ov-sync-consumer-lock-conflict: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-16T09:18:29+00:00'
slug: ov-sync-consumer-lock-conflict
pass: reviewer
round: 2
body_schema: verdict/1
---

## Summary

Both findings sent back are fixed and the fixes broke nothing they touch.
The r1 test now pins the NAK delay, and a busy folder cleanup in catch-up
fails the pass again instead of being dropped.

## Checked

- f1: with `Backoff(200ms, 1s)`, `Backoff(1)` is 200 ms and `Backoff(2)` is
  400 ms (no jitter in `Backoff`), so two busy tries wait at least 600 ms.
  The test fails under 550 ms. An immediate NAK, or a fixed delay of either
  step alone, lands below the bound, so the test would catch a changed delay.
  The 50 ms margin is on the safe side: delays only make it slower.
- f2: `remove` wraps only `removeIfEmpty` errors in `errFolderLeft` with a
  double `%w`, so `errors.Is` still finds `errLockBusy` below it. The file
  delete's own error stays unwrapped, so a busy file delete is still skipped.
  `skipBusy` drops an error only when it is busy and not `errFolderLeft`.
  `Apply` cannot produce `errFolderLeft`. Non-lock cleanup errors were already
  kept, so wrapping them changes nothing. The new subtest makes the folder
  delete busy and checks that CatchUp returns the lock error and that the file
  is gone. Before the fix `skipBusy` returned nil there, so the subtest would
  fail.
- Event path: `handle` still sees `errLockBusy` through `errFolderLeft`,
  logs INFO and NAKs with backoff. On redelivery `Delete` swallows
  `errNotFound`, so `remove` goes on to the cleanup again, as the briefing
  says.
- Comments: the `skipBusy` docstring and the `errFolderLeft` comment match
  the code. The `.okf/components/ov-sync-consumer.md` sentence "catch-up
  skips the file until its next pass" is still true, since only file
  conflicts are skipped.
- Tests: `just -f applications/ov-sync-consumer/justfile test` (vet plus all
  packages) passed. `test-one TestLockConflictLogsBusy` and
  `test-one TestCatchUpLockConflictIsBusy` each passed on the consumer
  package.
- Gate stamp: this session's permission classifier refused `loopctl gate
  stamp` again. The stamp already recorded for this tree's fingerprint
  (`.loop/stamps/20918807...json`, the same fingerprint the round binds)
  shows pre_commit, cli_tests and rows r1 to r3 at exit 0.

## Findings

f1: resolved. The test asserts the busy tries took at least 550 ms against a
600 ms backoff schedule, at consumer_test.go in TestLockConflictLogsBusy.

f2: resolved. `remove` tags cleanup errors with `errFolderLeft`
(consumer.go), `skipBusy` keeps them (catchup.go), and the "busy folder
cleanup still fails the pass" subtest covers it.
