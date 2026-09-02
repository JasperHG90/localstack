---
slug: G1-grafana-native-oidc-login
blockers: []
friction: [other:eval-amendment-lost-in-copy-back, other:plan-edit-stales-verdict-at-ready, other:artifact-commit-blocked-by-stale-stamp, other:reviewer-clobbered-operator-token, other:eval-header-has-no-amend-path]
worked: [other:plan-traps-were-real, other:concurrent-review-fanout, other:pending-operator-annotation]
harness_change: Let eval-amend run inside a linked worktree, which would delete the copy-back that lost an amendment here.
---

## What worked

**The plan's five review rounds paid for themselves.** Every trap it recorded
turned out to be real and load-bearing: no OIDC discovery in 11.5.2, Vault
hard-rejecting a scope without `openid`, the Viewer-not-Editor default, and
the unquoted scope template. The adversarial reviewer stood up a throwaway
Vault and independently confirmed all six premises it was asked to falsify.
Implementation was mechanical because the thinking had already been done.

**Dispatching both review passes concurrently against one frozen fingerprint.**
Two passes, one tree, no drift, and the documentation pass caught a defect the
adversarial pass was not looking for: a hallucinated claim that `localstack
breakglass` reads the unseal keys. It does not, and that sentence sat in the
paragraph someone reads during an incident.

**`verdict: pending-operator` let the ticket finish honestly.** No apply was
possible, so six rows are annotated rather than quietly scored, and the three
statically checkable rows were actually run.

## What worked less well

**A counter-signed eval amendment was silently lost, and only an adversarial
reviewer caught it.** `eval-amend` refuses to run inside a linked worktree, so
each amendment meant: amend in the primary, copy to the worktree, restore the
primary. The restore reverted the primary to the *committed* marker, which had
no amendments. The next round's amendments stacked onto that reverted file,
and copying it back overwrote the first fix. The marker then carried
`amendments: 2` and read as consistent, while the row it had fixed was red
against the diff. Nothing deterministic catches this: `verify-eval-substance`
inspects the Scorer cell, and the broken grep lived in the Input cell. The
rule that would have prevented it is one line: **sync worktree to primary
before amending, never after.**

**Editing the plan after its verdict bound to it.** `create-eval` step 7 says
to update the plan's eval back-link. Doing so changed the plan's sha256, which
staled the passing plan-validator verdict, and `loopctl plan-rebind` refuses
outside `planning` while `advance` refuses to go backwards from `ready`. The
only way out was reverting the edit. Two skill steps point in opposite
directions.

**A first eval marker cannot be committed.** `preflight-artifacts` refuses to
branch a worktree until the marker is committed, but the commit gate refuses
every commit while the stamp is stale, and there is no stamp before the ticket
starts. Broke only because the operator committed from outside the session.

**The adversarial reviewer destroyed `~/.vault-token`.** Its isolated `vault
server -dev` clobbered the operator's cached token, which then made one of its
own findings unverifiable. Read-only toward the repo is not the same as
read-only toward the environment.

**A false claim in an eval marker's header has no sanctioned fix.**
`eval-amend` is row-scoped. The header carried the same wrong statement as a
row, so the row went through the audited path and the header was hand-edited.
