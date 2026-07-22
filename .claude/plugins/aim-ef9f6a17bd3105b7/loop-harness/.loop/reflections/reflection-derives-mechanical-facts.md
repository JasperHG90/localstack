---
slug: reflection-derives-mechanical-facts
blockers: []
friction: [other:background-impl-stales-stamp, prek-first-pass-rewrite]
worked: [generator-evaluator-split]
harness_change: implement-ticket should warn against backgrounding the implementer or any concurrent edits — they stale the stamp mid-review and spin the stop-check; if delegating implementation, TaskStop the sub-agent and re-stamp on a stable tree before dispatching review
---

## What worked

Delegating the implementation to a sub-agent (the generator) and keeping the
stamp and the two independent review passes (the evaluators) in the driver was
a clean split. The reviewers earned their keep: both caught real
docstring/manifesto drift the gates cannot see (a stale `Raises` line and a
missing `.loop/history/` disk-state entry), and both independently re-ran the
gates and recomputed the fingerprint. This ticket's own reflection uses the
new judgment-only schema it introduced.

## What worked less well

Running the implementer in the background collided with the loop's synchronous
model: it kept editing after my "settled" heuristic fired (during its own long
gate run), which staled the stamp between `loopctl stamp` and the advance and
made the stop-check spin. The fix was to `TaskStop` the sub-agent, converge
formatting, and re-stamp on a stable tree, which cost one extra review cycle.
`prek` also reformatted a test file late, contributing to the churn.
