---
slug: A1-audit-plan-premise-sweep
blockers: []
friction: [other:tree-written-during-review, other:doc-lags-operator-instruction, other:repo-derived-published-as-live, reviewer-boilerplate]
worked: [other:agent-per-artifact-fanout, other:briefed-latent-defect-head-on, other:rejected-false-finding-with-evidence]
harness_change: excluded-from-fingerprint should not mean invisible-to-review - the commit gate accepted verdicts while .loop/ churned underneath them
---

## What worked

**One reviewer agent per artifact, dispatched concurrently.** Thirteen plans,
thirteen `loop-plan-reviewer` agents, each briefed with its own fingerprint and
verdict path. Every one verified its fingerprint before binding it. Wall clock
was one review, not thirteen. The alternative A1 originally planned, a single
hand-rolled pattern sweep, would have found a fraction of this: the reviewers
read MinIO's source at the deployed tag, checked GitHub issue state, and probed
Nomad's `/v1/jobs/parse` live. No sweep does that.

**Briefing the known-latent defect head-on paid.** M1's briefing named the
suspected broken edge and said confirm or refute, do not skip. It came back
confirmed AND worse than recorded: `jwks_url` is not merely unused, it is a
removed parameter. A generic "review this plan" would likely have missed it.

**The reviewers caught my errors four times, and every one was the defect class
this ticket exists to remove.** Live-job ground truth derived from a repo grep
and published under a live-readback heading. Anchor drift credited to the wrong
commit. A count keyed on a heading string instead of the substance, wrong
twice. A fork asserting a stale claim `main` had already fixed. None of these
would have been caught by gates: `just pre_commit` passed green throughout.

**Rejecting a false reviewer finding, with evidence, was right.** The
documentation pass demanded deletion of a true claim. Complying would have put
a falsehood into the document built to remove falsehoods. Recording a dated
rebuttal beat both silent compliance and silent override; the pass withdrew the
finding on its next cycle and the adversarial pass independently upheld it.

## What worked less well

**`other:tree-written-during-review`.** I edited thirteen plans and the ledger
while a review pass was running. `.loop/` is stripped from the tree
fingerprint, so the hash never moved and the gate could not see it. The
reviewer caught the drift by file mtime, not by any harness signal. The rule is
simple and I broke it: freeze the tree from dispatch to join.

**`other:doc-lags-operator-instruction`.** An operator instruction arrived
mid-ticket (add pointer sections, block all thirteen). I executed it and left
the deliverable describing the world before it, including a sentence reading
"A1 must not perform the blocks itself" while the ledger showed A1 had. That is
exactly the C1 failure requirement 5 was written to prevent, reproduced inside
the audit created to catch it. When an instruction changes what the deliverable
says about itself, the deliverable is part of that instruction's blast radius.

**`other:repo-derived-published-as-live`.** The most instructive one. A section
headed "read from the live cluster" carried a list produced by
`grep -rl 'vault {' deployments/`. It silently omitted `talat-shim` and
`talat-consumer`, which run on the cluster and hold the shared policy but have
no job file in this repository. The grep was not wrong about the repo. It was
answering a different question than the heading claimed.

**`reviewer-boilerplate`.** Four cycles, two passes each. Later cycles spent
real budget re-verifying settled ground. Telling each pass what was already
verified and asking it not to re-litigate helped, but only from cycle three on.

## Cycles, gates, blockers

Review cycles: 3, the configured cap. Gates red: 0 - `just pre_commit` passed
on every stamp, which is the point worth keeping. Every defect this ticket
found, and every defect its reviewers found in my own work, was invisible to
the gates. Blockers on this ticket: none. Blocks issued to other tickets:
thirteen.

Two known non-blocking defects shipped, both recorded in the adversarial
verdict: R3's citation count (9 stated, 7 counted) and the provenance section
saying three operator decisions where there were four. Not fixed because
`review_cycles` was at cap, so any edit would stale the stamp, and the re-gate
needed to re-stamp is refused at cap, blocking the ticket instead of landing
it. That is the cap working as designed, but it means findings raised in the
final cycle are structurally unfixable. Worth knowing before leaning on cycle
three.
