---
slug: eval-as-spec-gate
cycles: 0
gates_red: 0
blockers: []
friction: [other:concurrent-tree-churn]
worked: [tests-first, pattern-mirroring]
harness_change: scope the stamp fingerprint to the ticket's declared code surface (or honor an ignore-list) so unrelated concurrent working-tree writes do not stale the commit gate
---

## What worked

Mirroring existing patterns kept each subticket small and low-risk:
`evals.py` followed `reflection.py` (StrEnum status + frozen verdict +
`ok` property, presence-plus-schema, not tree-bound), and `require_eval`
followed `require_review` (flag, parse, docstring, EXAMPLE_CONFIG). The
pure `validate_transition` took the two new params without disturbing its
three other callers, so the commit gate and block/done paths needed no
change. Tests-first per subticket (S1 validator before everything that
imports it) meant each layer was green before the next was wired.

## What worked less well

The dominant friction was `other:concurrent-tree-churn`: the evidence
stamp certifies the WHOLE working tree (tracked + untracked, minus
`.loop/`), and concurrent activity in the repo (generated logo assets
under `docs/`, a `MANIFESTO.md` and `.manifesto/`, `aim` skill-install
lockfiles) kept landing untracked files during the gate/review window.
Each new file changed the tree fingerprint, staling the stamp and
invalidating the tree-bound reviewer verdict, forcing a re-stamp and a
verdict re-bind. The ticket's own code was byte-identical throughout; the
churn was entirely unrelated files. Setting them aside caused its own
problem (the operator wanted the generated docs left in place), so the
resolution was to re-stamp and re-bind the verdict at the settled tree.
The harness_change above would remove this whole failure mode.
