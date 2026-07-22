---
slug: commit-gate-targets-the-committed-repo
cycles: 0
gates_red: 0
friction: [other:baseline-drift-mid-review, other:own-command-self-gated]
blockers: []
worked: [tests-first, other:sibling-helper-reuse, other:verdict-rebind-clean]
harness_change: docs/ is not in fingerprint_ignore, so an unrelated doc/memex commit mid-review staled this ticket's verdicts and forced a full re-review
---

## What worked

Building on the sibling's `_invokes_git_commit` helper (already landed)
made the `-C` widening a small extension rather than a rewrite. Reproducing
tests first — real temp git repos, no mocks — pinned both holes (`cd`
wrong-repo and the `-C` bypass) before the fix, and both reviewers passed
first time. When the baseline shifted, re-binding the verdicts to the new
tree was clean because the diff was unchanged.

## What worked less well

Two unrelated commits (a docs tutorial and a memex build update) landed
while the ticket sat in review, which staled the tree-bound verdicts and
forced a re-stamp and full re-review even though nothing in the ticket
changed. `fingerprint_ignore` exists but does not cover `docs/`, so
documentation churn invalidates in-flight code verdicts. Separately, the
commit gate's own known over-gate (operators inside a quoted string) blocked
a read-only `git log` recon command whose grep pattern contained the literal
phrase — the exact ergonomic cost the sibling ticket documented.
