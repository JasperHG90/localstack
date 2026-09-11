---
slug: backup-swap-memex-for-openviking
blockers: []
friction: [other:worktree-setup-not-discovered, other:review-cycle-ratchet]
worked: [other:probe-before-planning, other:negative-controls-verified]
harness_change:
---

## What worked

Probing the live cluster before writing the plan changed the ticket's shape.
The operator asked for two things; the probe showed one of them
(`pg_dumpall` already covering the `openviking` database) was already true,
so the ticket shipped one edit instead of two and said why. Premises P2, P3
and P4 carry command output rather than assertions, and both reviewers
re-derived them independently rather than trusting the paste.

Verifying the negative controls before handing the diff to review. Both new
tests were shown to redden: a typo'd bucket name, and a half-done swap that
moves the rclone source but leaves the GCS prefix. The adversarial reviewer
re-ran its own mutation harness and reached the same result, so the claim
cost one exchange instead of a cycle.

## What worked less well

`terraform validate` failed in the fresh worktree because
`deployments/infrastructure/services.tf:473` reads `.ssh/id_rsa`, which is
gitignored and therefore absent from any new worktree. The repo already
solves this with `just worktree_setup <path>`, and I diagnosed it as a repo
defect before finding the recipe. Reading the root `justfile` for setup
recipes belongs before the first red gate in a new worktree, not after.

Three review cycles for one jobspec line. Cycles 2 and 3 existed because I
applied doc fixes that both reviewers had explicitly declined to require,
under `pre-existing-issues.md`. Both later endorsed the calls, and the
adversarial pass drew the useful line: what makes a widened diff acceptable
is that it stays bounded and verified, not that a rule permits it. The cost
is real though — each fix re-staled the stamp and forced a full re-dispatch.
Batching every discretionary fix into one edit before the first dispatch
would have bought the same result in one cycle.
