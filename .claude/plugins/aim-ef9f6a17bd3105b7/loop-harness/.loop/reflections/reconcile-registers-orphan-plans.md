---
slug: reconcile-registers-orphan-plans
blockers: []
friction: [other:mypy-enum-narrowing-in-tests]
worked: [inline-implementation, adversarial-review]
harness_change:
---

## What worked

Implementing inline (rather than in a background sub-agent) kept the working
tree stable, so no stamp went stale mid-review the way ticket 2's backgrounded
implementer caused. The two review passes earned their keep again: the
adversarial pass required a missing test for the R7 self-heal ordering (an
orphan whose commit already exists), and the architectural pass caught a real
I17-vs-DECISIONS wording inconsistency (the invariant omitted `blocked` from
the silent set). Both were genuine, not boilerplate.

## What worked less well

mypy flagged a `Non-overlapping identity check` in the self-heal test: an early
`assert entry.stage is Stage.READY` narrowed the enum type, so the later
`assert ... is Stage.DONE` on the same expression read as impossible. It surfaced
only as a RED stamp (which, fittingly, exercised this batch's own gate-failure
history log). The fix was to assert the plans-pass effect via the returned
`registered` list instead of re-reading `.stage`, avoiding the narrowing.
