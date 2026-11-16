---
type: verdict
title: 'Verdict: ov-sync-consumer-lock-conflict reviewer round 1'
description: 'reviewer verdict for round 1 of ov-sync-consumer-lock-conflict: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-16T09:13:17+00:00'
slug: ov-sync-consumer-lock-conflict
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The change does what the plan asks. A lock-timeout 409 is tagged with
`errLockBusy` in do(), the %w chain reaches handle() and catch-up through
every wrap, handle() keeps the same NAK delay and dead-letter rule and only
changes the log level, and both roots pin v0.1.1. Two non-blocking findings:
r1's test does not pin the NAK delay, and the catch-up comment overstates
what the next pass repairs for a busy folder delete.

## Checked

- Envelope shape: the installed OpenViking server (`server/models.py`
  Response/ErrorInfo, `server/error_mapping.py` mapping LockAcquisitionError
  to `OpenVikingError(str(exc), code="CONFLICT")`) answers
  `{"status":"error","error":{"code":"CONFLICT","message":...}}`. do() formats
  that as `CONFLICT: <message>`, which matches the live log
  `HTTP 409: CONFLICT: lock acquire timed out after 172ms`, so the match on
  `env.Error.Message` holds. The installed package is 0.5.0, not the deployed
  version, so this is the shape, not the deployed string.
- %w chain: Write and Delete return do()'s error as is (Delete only swallows
  errNotFound). Apply wraps `write %s: %w`; remove wraps `delete %s: %w`;
  removeIfEmpty wraps `delete folder %s: %w` and remove returns it as is.
  CatchUp joins with errors.Join and `%s: %w`, but skipBusy runs before that.
  No `%v` breaks the chain.
- skipBusy: Apply and remove return one error each, never a join, so skipBusy
  cannot drop a non-busy error riding alongside a busy one. Limit.Wait and
  listing errors bypass it. See f2 for the folder-delete case.
- handle(): the dead-letter branch runs first, so a lock 409 on the last try
  still dead-letters; NakWithDelay(c.Backoff(delivered)) is shared by both
  log branches.
- Race in TestLockConflictLogsBusy: both busy INFO lines are written before
  their NAK, the NAK comes before the redelivery, and the redelivery comes
  before the third write that `waitFor` observes, so the count of 2 is
  ordered, not timed. logBuffer is mutex-guarded. Ran it three more times
  green.
- Rows: r1 asserts 3 writes (no early ack or dead letter), two INFO lines
  naming the URI, no WARN (NAK delay not asserted, f1). r2 asserts one
  `event failed` and no `folder busy` for a non-lock 409, and exactly
  MaxTries writes before a dead letter. r3 asserts no lock text in the pass
  error, one INFO line naming the URI, and the file left in place. r4: the
  grep for v0.1.1 in both roots passes. r5 is a live judgment row after
  release and cannot be judged yet.
- Tests: `just -f applications/ov-sync-consumer/justfile test` (vet and all
  packages) passed; each row's `test-one` passed.
- Gate stamp: `loopctl gate stamp` was refused by this session's permission
  classifier, so I could not record my own stamp. The implementer's stamp
  `.loop/stamps/0f25cf10...json` (2026-11-16T09:10:15Z) shows pre_commit,
  cli_tests and r1 to r4 all exit 0. I did not run `just pre_commit` myself
  because its hooks may rewrite files in the tree under review.
- Docs: the `.okf/components/ov-sync-consumer.md` paragraph and test-table row
  match the code; no other doc names v0.1.0 for this image.

## Findings

f1: r1's fails_when lists a changed NAK delay, but the test never observes
the delay. The code shares one NakWithDelay line, so it is right today; the
test should guard it, for example by recording delivery timestamps or
wrapping Backoff to record what handle() asked for.

f2: when remove()'s file delete succeeds and removeIfEmpty's recursive folder
delete hits the lock, skipBusy logs "catch-up retries next pass", yet the
next pass cannot see that folder (files() excludes folders and summaries), so
it lingers with no WARN. Before, catch-up never retried it either, but the
pass failed loudly. Fix the comment and log text to say only the file is
retried, or let a busy folder delete through skipBusy.
