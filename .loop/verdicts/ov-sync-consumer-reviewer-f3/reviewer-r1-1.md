---
type: verdict
title: 'Verdict: ov-sync-consumer-reviewer-f3 reviewer round 1'
description: 'reviewer verdict for round 1 of ov-sync-consumer-reviewer-f3: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-16T08:18:59+00:00'
slug: ov-sync-consumer-reviewer-f3
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The per-key lock closes the stale-write race the plan describes. I found no
path that can deadlock and no race in the map cleanup. Both new tests check
what their eval rows say. Pass.

## Checked

- Gates: `loopctl gate stamp` from the worktree returned green
  (b2f3ede7...). pre_commit, cli_tests and eval rows r1, r2 and r3 all passed.
- Lock order: Apply takes the key after Resolve and before Limit.Wait, the S3
  read and any tree lock. It holds the key through Write (under RLock) or
  remove (RLock, then Lock). Catch-up's direct remove takes its key outside any
  tree lock. Catch-up calls Apply in sequence while holding no key, and nothing
  takes a key inside `remove`, `removeIfEmpty` or under `tree`. So the waits
  only run key, then tree, then an OV slot. A slot is held for one request
  only. The graph has no cycle.
- Map cleanup: `users` goes up under `k.mu` before the caller blocks on the
  entry's mutex and goes down under `k.mu` after unlock. A waiter that arrives
  while the last holder is leaving either finds the entry (users > 0, so it
  is not deleted) or finds it already deleted and makes a fresh one. Nobody
  can still be waiting on a deleted mutex.
- r1: I copied the module to a scratch dir and removed the
  `defer c.keys.lock(uri)()` line. TestApplySerializesPerKey then fails with
  `OpenViking holds "v1", want the latest content v2`. With the fix it passed
  5 of 5 runs. The fixed 300 ms wait can only cause a false pass on broken
  code when the machine is slow (B has not finished its write within 300 ms).
  It never causes a false failure on correct code, because with the fix B
  blocks no matter how long the wait is.
- r2: TestPerKeyLockNoDeadlock runs folder removals (tree.Lock) at the same
  time as keyed writes and deletes, with catch-up looping. It has a 60 s fatal
  timeout, then checks that OV converges and that the key map is empty. It
  passed 5 of 5 runs.
- Scope: catch-up can still remove a file after a stale listing (the
  delete-versus-recreate case). The plan says catch-up already repairs that
  case, so leaving it out is right. The CatchUp docstring and the .okf
  component sentences still match the code.

## Findings

None.

## Notes

The key is held during Limit.Wait. That costs a worker slot only when two
events for the same file are in flight at once, which is acceptable.
