---
slug: commit-gate-false-positive-on-strings
cycles: 1
gates_red: 0
friction: [prek-first-pass-rewrite, other:first-impl-false-negative]
blockers: []
worked: [tests-first, other:adversarial-review-caught-regression]
harness_change: quote-aware operator splitting would remove the over-gate that bites probe commands like `echo "a && git commit"` (follow-up)
---

## What worked

Writing the three reproducers first proved the bug and gave the fix a
target: each new negative row failed against the old substring regex.
Keeping the detector in one `_invokes_git_commit` helper shared by both
call sites made the reviewers' single-definition check trivial. The
adversarial and architectural passes independently caught the same real
regression (F1), which is the review layer doing exactly its job.

## What worked less well

The first implementation matched only the segment's first two tokens
(`tokens[0]=="git"`), which silently dropped a real commit behind a
`VAR=value` env-assignment or a `sudo`/`env` wrapper — a false negative
worse than the false positive being fixed. The reviewers flagged it;
switching to an adjacent `git`/`commit` token-pair match restored parity
with the old regex. A `prek` first pass also needed a rewrite (`zip`
without `strict=` / `RUF007`), resolved by `itertools.pairwise`.
