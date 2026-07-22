---
slug: commit-gate-git-hook-backstop
blockers: []
friction: [other:manifesto-drift-on-new-module]
worked: [ready-stage-background-impl, adversarial-review]
harness_change: implement-ticket should remind the driver that a new src module needs a MANIFESTO update (a §2 module-map row, and any invariant it strengthens) before the stamp, since the architectural pass gates on it
---

## What worked

Delegating this large ticket to a background sub-agent while keeping the ledger
stage at `ready` avoided the loop stop-check spin that ticket 2 hit (the
stop-check only fires for a mid-flight ticket, not a `ready` one), and waiting
for the sub-agent's true completion rather than a heuristic settle-timer avoided
the stamp staleness. The sub-agent honestly surfaced the one DECISIONS-vs-scope
tension (G1's SessionStart line) instead of guessing. The adversarial pass
confirmed the un-bypassable enforcement with real `git -C` and subprocess
commits, and the architectural pass caught the missing MANIFESTO update.

## What worked less well

The sub-agent (correctly, given its scope) did not update `MANIFESTO.md`, so the
new `githook.py` module was absent from the §2 module map and I7 still named
only the PreToolUse hook: the architectural pass required the fix, costing one
review cycle. Adding a module without touching the manifesto is a recurring
drift the doc-honesty gate exists to catch; the harness_change above would
front-load it.
