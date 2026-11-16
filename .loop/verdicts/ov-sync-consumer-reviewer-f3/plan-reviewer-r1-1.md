---
type: verdict
title: 'Verdict: ov-sync-consumer-reviewer-f3 plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of ov-sync-consumer-reviewer-f3: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-16T08:03:00+00:00'
slug: ov-sync-consumer-reviewer-f3
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

The plan holds. If Apply holds one lock per key across its S3 read and its OpenViking write or delete, the last Apply to run on a key reads the object after its last change. So OpenViking ends with the latest content, whichever worker, redelivery or catch-up ran it. The deadlock constraint can be met: take the per-key lock first, before Limit.Wait, the read and any tree lock, and never take it while holding a tree lock. Then nothing waits in a cycle. I found no unlisted risk that would break the plan.

## Checked

- consumer.go: Apply reads S3 before any lock (line 179 onward). remove takes tree.RLock for the file delete, then tree.Lock for the folder sweep. Every caller that blocks on tree.Lock or RLock holds no other lock today.
- Deadlock: suppose the per-key lock is outermost. A worker holding key K and tree.Lock in remove waits only on RLock holders, and those hold other keys. A worker waiting on key K holds nothing. A pending Lock in Go's RWMutex blocks new RLocks, but the RLock holders finish their single OpenViking request without needing key K. MaxInFlight slots (openviking.go) are held for one request at a time, never across a lock wait, so they add no edge.
- Redelivery: AckWait is 5 minutes and NakWithDelay retries. Either can put the same key on two workers at once. Per-key serialization covers that, and each run reads the current state again.
- Catch-up (catchup.go) calls Apply for missing files, so the per-key lock covers it there. It calls c.remove directly for stale files. That path decides from a listing that may be out of date, so it can delete a file that was just recreated. Per-key locking does not fix that. The next catch-up pass repairs it (bucket has the file, OpenViking does not), which is the delete-versus-recreate case the Intent already puts out of scope.
- Process count: the Nomad job (deployments/applications/services/ov-sync-consumer.hcl) sets no count, so it runs one instance. An in-process lock is enough.
- Eval rows r1 and r2 test the finding and the deadlock constraint, and r3 runs the full suite and the repo gates.

## Findings

None.

## Notes

These are for the builder, not blockers:
- Key the lock by the OpenViking URI, not the S3 key. Catch-up's remove has only the URI. Mapping also allows two prefixes to share a root, which would give two S3 keys the same URI.
- Release per-key entries when the last holder leaves, so the map does not grow without bound.
- The OpenViking HTTP client times out at 150 s and the server waits up to 120 s. If the client gives up on a write that the server still applies, a later serialized write can land before it. A client-side lock cannot order server-side work it has abandoned. This is rare, so leave it to the build.
