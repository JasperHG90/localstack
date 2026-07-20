---
slug: loop-config-review-passes
cycles: 0
gates_red: 1
blockers: []
friction: [prek-first-pass-rewrite]
worked: [other:tests-first-pinned-guard]
harness_change: a `loopctl fingerprint` command would save reading stamp.json to hand the reviewer the tree
---

## What worked

Writing the tests first pinned the load-bearing behavior before any code
existed: the un-guessable opt-out (empty/all-disabled `review_passes` must
raise under `require_review:true`) and backward compat (absent key synthesizes
the adversarial pass) were both nailed by explicit failing tests, so the
implementation had a clear target and the reviewer had concrete assertions to
check. The generic-baseline deviation resolved cleanly by citing the repo's
existing "harness is generic" principle rather than inventing a new rule.

## What worked less well

The first stamp went red on mypy alone (bare `dict` missing type args in the
new helper and the test writer) after pytest and both ruff hooks passed —
`prek-first-pass-rewrite`. Cheap to fix, but it cost a full gate re-run
(~25s of pytest) to re-clear. Running `uvx prek run --files <changed>` before
`loopctl stamp` would have caught it without the pytest tax.
