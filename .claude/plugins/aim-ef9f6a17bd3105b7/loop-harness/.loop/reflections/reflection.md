---
slug: reflection
cycles: 0
gates_red: 1
blockers: []
friction: [compound-stamp-commit, prek-first-pass-rewrite, other:bundled-inflight-commit]
worked: [tests-first, small-diff, clean-adversarial-pass]
harness_change: give loopctl a maintenance-commit path so unrelated commits during a mid-flight ticket don't need a full HALT
---

## What worked

Tests-first kept the module and its enforcement honest: the three verdict
branches, distill aggregation, and the `done`/`finish` refusals were pinned
before the wiring, so the adversarial reviewer passed clean on the first
cycle (no findings loop). The diff stayed surgical — exactly the 9 files the
ticket's Code surface named, no scope creep.

## What worked less well

- **compound-stamp-commit**: a compound `loopctl halt && git commit` was
  blocked because the pre-commit gate evaluates the whole Bash command before
  the earlier `halt` in the same command runs — the gate saw no HALT yet.
  Splitting `halt` into its own call fixed it. This is the exact
  gate-evaluates-before-the-state-exists pattern the ticket describes.
- **prek-first-pass-rewrite**: ruff-format rewrote files on the first stamp
  and exited non-zero (one red stamp); a re-run went green.
- **other:bundled-inflight-commit**: an operator hygiene commit ran `git add
  -A` mid-ticket and swept the in-flight feature code into an unrelated
  commit, so the loop's one-clean-ticket-commit model was violated.
  Recovering meant replaying the operator commit's exact staged diff minus the
  feature files (via `git reset <sha> -- .` then unstaging the feature) under
  HALT, then finishing the feature through the normal flow. The commit gate
  blocking ALL commits during a mid-flight ticket forced a HALT for the
  unrelated maintenance commit.
