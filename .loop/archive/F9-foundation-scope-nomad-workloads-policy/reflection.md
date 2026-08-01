---
slug: F9-foundation-scope-nomad-workloads-policy
blockers: []
friction: [other:runbook-prose-outside-the-gate, other:assertion-passes-on-wrong-content, other:tree-written-during-review, reviewer-boilerplate]
worked: [other:reviewer-supplied-the-consumer-survey, other:two-passes-converged-independently, other:fail-safe-verdict-placeholder]
harness_change: the gate certifies the diff, not the prose telling a human how to apply it - a runbook that would break the cluster passes just pre_commit green every time
---

## What worked

**The plan review did the expensive part before implementation started.** F9's
subticket 1 was "establish which jobs consume `bootstrap/*` before removing
anything", the one genuinely risky unknown. Its plan reviewer had already
answered it: zero references across all nineteen live jobs, zero in the repo,
and `docs/credential-rotation.md:34-40` stating rotation is host-level by
design. That turned a search into a confirmation and collapsed the ticket from
"maybe build a dedicated role" to "delete three blocks".

**Two independent passes converged on the same defect.** The adversarial and
documentation reviewers both found that the runbook's render instruction would
write a policy matching nothing. Neither was told about the other's finding.
Convergence from different angles is much stronger evidence than one reviewer
insisting, and it is the reason that fix was treated as blocking rather than
argued with.

**The fail-safe verdict placeholder.** After several agents died mid-run on a
session limit, reviewers were told to write `verdict: fail` to their verdict
file first and refine in place. Two later deaths then left a `fail` on disk
rather than nothing, so the commit gate refused rather than seeing an absent
verdict. Worth keeping as standing instruction: a dead review must read as
"not reviewed", never as silence.

**Reviewers re-derived rather than trusted.** One rendered the Jinja template
with the live accessor and diffed it against `vault policy read`, proving the
surviving grants are byte-identical. Another built the post-apply text and ran
all four proposed assertions against four failure modes in a table. That is
the difference between checking a claim and checking the thing.

## What worked less well

**`other:runbook-prose-outside-the-gate`.** The worst defect in this ticket was
never in the diff the gate inspects. `just pre_commit` was green on a runbook
that told the operator to hand-render a double-escaped Jinja template, which
would have written a policy whose paths match nothing and blocked all fifteen
default-role holders, haproxy included, dropping every routed service. The
gate certifies the template. Nothing mechanical reads the prose that tells a
human what to do with it. For any ticket the loop cannot apply, the runbook is
the deliverable and deserves the same suspicion as the code.

**`other:assertion-passes-on-wrong-content`.** Twice. First
`grep -c 'bootstrap'`, case-sensitive, returning 0 against a surviving
`# Bootstrap secrets` comment and thereby passing a policy still advertising a
deleted grant. Then, found in the last cycle and left in, no assertion proves
the *unscoped* metadata block specifically is the one removed: deleting a
job-scoped read instead scores identically green. This is the same class this
ticket's own epic exists to remove, committed inside the fix for it.

**`other:tree-written-during-review`.** Repeated from A1 despite naming it
there. I edited the worktree while a reviewer was reading it, and one agent
reported "the tree moved under me mid-review". `.loop/` sits outside the tree
fingerprint, so the hash does not move and nothing warns. The rule is simple:
freeze from dispatch to join, and it needs to be a habit rather than a
resolution.

**`reviewer-boilerplate`.** Four review cycles, two passes each. Later rounds
spent real budget re-verifying settled ground. Telling each pass exactly what
changed and what was already confirmed helped, but only from cycle three.

**A waiter that matched a stale artifact.** The completion check looked for the
absence of "IN PROGRESS" text and matched a previous cycle's finished verdict,
so the ticket briefly looked ready to merge while the adversarial pass had not
written. The correct predicate is the tree fingerprint, not the file's shape.
The commit gate would have caught it; the report to the operator nearly did not.

## Cycles, gates, blockers

Review cycles: 3, the configured cap. Gates red: 0 - `just pre_commit` passed
on every stamp, including the stamp of the version whose runbook would have
taken the cluster down. Blockers on this ticket: none. Blocks issued: one, to
F1, whose plan documents the pre-F9 policy and instructs "do not narrow it
either".

Two known defects ship, both in the adversarial verdict: F1's relay says the
template drops to 20 lines where it is 21, inside a sentence telling the reader
not to trust line numbers; and the assertion gap above. Both were found in the
final cycle, where the cap leaves no room to fix and re-review. That is the cap
behaving as designed, and it means findings raised last are structurally
unfixable - the same note A1's reflection made. Two tickets running into it is
a pattern, not a coincidence.
