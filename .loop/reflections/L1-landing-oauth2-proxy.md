---
slug: L1-landing-oauth2-proxy
blockers: []
friction: [other:review-agent-race-on-verdict-path]
worked: [other:plan-already-passed-review, other:adversarial-clean-first-cycle]
harness_change: before re-dispatching a review pass for cycle N+1, confirm cycle N's agent has actually terminated (poll for its real completion, not just a "completed" notification) - a background reviewer can keep running well past that notification, and two instances writing the same verdict path race
---

## What worked

The ticket had already been fully re-planned and passed a seventh plan-review
cycle with zero required fixes before pickup - the only blocker was stale
ledger bookkeeping (a blocked entry quoting an earlier failing pass), cleared
in a separate session before this implementation ran. Implementation itself
was straightforward: the plan's 19 requirements, Code surface, and eval
marker were precise enough to build against directly, and the eval marker
was already authored and just needed operator sign-off. The adversarial
review pass came back clean on the first cycle with no findings, including
independently verifying the pinned oauth2-proxy image's arm64 support via a
live quay.io manifest query.

## What worked less well

The documentation review pass found one real, narrow gap (the HAProxy
route-table doc missing the new `dash` row), which is the findings loop
working as intended. What went wrong was orchestration on my side: I
dispatched a "cycle 2" documentation reviewer to re-attack that finding
without confirming the cycle-1 agent had actually stopped. It had not - it
kept running for nearly 28 minutes total, well past an earlier "completed"
notification - and the two agent instances raced writing to the same
verdict path. The stale cycle-1 agent won the last write and reverted the
correct cycle-2 verdict, though to its credit it detected the anomaly,
refused to silently adopt content it couldn't explain, and reported the
race explicitly rather than picking a side. Resolved by dispatching one
more, single-writer review pass and verifying its output directly (file
content and modification time) rather than trusting either agent's
self-reported summary.
