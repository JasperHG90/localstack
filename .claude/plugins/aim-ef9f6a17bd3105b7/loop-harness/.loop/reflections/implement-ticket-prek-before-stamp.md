---
slug: implement-ticket-prek-before-stamp
cycles: 1
gates_red: 0
blockers: []
friction: [other:nonblocking-nit-full-recycle]
worked: [eval-as-spec-concrete-dod, reviewers-agreed]
harness_change: Let both-PASS non-blocking observations be accepted-and-deferred without forcing a full re-stamp plus re-review cycle.
---

## What worked

The eval marker made the Definition of Done concrete: the seven rows
told the implementer and both reviewers exactly what to check, so there
was no ambiguity about "done." Both review passes agreed independently
and each re-ran the gates itself (180 passed, prek green), which is the
point of the two-reviewer design for the human-scored rows. Dogfooding
the new step-3 instruction was a clean no-op here (the changed file is a
`.md`, so the Python-typed hooks skipped it), so the fast pass added no
friction while proving the wording is followable.

## What worked less well

One full review cycle was spent on a single non-blocking wording nit
("commit any rewrites" to "let any rewrites land in the tree"). Both
passes had already returned PASS; the architect only surfaced the nit.
Acting on it forced a re-stamp (~40s pytest) and a fresh concurrent
re-run of both passes under the all-or-nothing rule, for a one-word doc
change. The all-or-nothing re-review is correct for code, but for a
doc-only change where both passes already passed and the finding is
explicitly non-blocking, the cost is disproportionate. Tagged
other:nonblocking-nit-full-recycle; the harness_change above is the
candidate relief.
