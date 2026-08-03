---
slug: U5-upgrade-hermes-bifrost-versions
blockers: []
friction: [other:worktree-missing-artifacts, other:stale-plan-verdict-fingerprint, other:reviewer-could-not-run-plan]
worked: [other:probe-driven-premises, other:surgical-three-line-diff]
harness_change:
---

## What worked

Probe-driven premises (P6): the plan-validator re-probed the live
registries during review and reproduced `v2026.7.30` -> `0.19.1`
verbatim, so the pin choice rested on evidence, not a scrape.

Surgical three-line diff: the Code surface declared exactly three
lines across two files, and the diff matched it precisely. No scope
creep, no stale strings left behind.

## What worked less well

worktree-missing-artifacts: `git worktree add` branched from a HEAD
that never tracked the U5 plan/eval/verdict files (they were untracked
`??` in the primary), so the worktree started with none of them. The
plan-validator advance refused until I copied the three artifacts in
by hand. The skill assumes the worktree inherits tracked `.loop/`
artifacts; untracked ones are invisible to it.

stale-plan-verdict-fingerprint: the existing plan-validator verdict
was bound to an older plan hash (the plan was edited after the first
review to fold in probe results), so `advance ready` refused. Re-ran
the loop-plan-reviewer pass to rebind. Recoverable, but cost a full
review round.

reviewer-could-not-run-plan: the adversarial reviewer could not run
`terraform plan` (Consul state backend 403s without the operator
token), so eval row 4 was assessed by static reasoning, not a live
plan. I ran the plan myself with the env token and confirmed only
hermes, bifrost, and the bifrost_ready sentinel changed, but the
reviewer had to take that on trust. The token is operator-only, so
this is an inherent limit of the review pass, not a fixable defect.