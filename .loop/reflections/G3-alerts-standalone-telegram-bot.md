---
slug: G3-alerts-standalone-telegram-bot
blockers: []
friction: [other:eval-backlink-restales-plan, other:worktree-missing-local-files, other:missing-scope-digest-in-briefing, other:signed-eval-unfixable-by-loop]
worked: [plan-delta-bounded-review, concurrent-review-fanout, premise-falsification]
cycles: 2
gates_red: 1
harness_change: implement-ticket's Isolate step should run the repo's own worktree setup recipe (here `just worktree_setup <path>`) when one exists, before the first stamp.
---

## What worked

**Premise falsification earned its cost on a documentation ticket.** The plan
review found four real gaps in a plan that read as correct: a missing premise
for the one claim everything rested on (that the Vault token was already
swapped), a probe written as a BRE whose `|` was literal so it matched nothing
anywhere, a TODO line the ticket only half-finished, and an unnamed delivery
precondition. None would have been caught by reading the diff.

**The plan-delta rung paid for itself immediately.** Editing section 8 re-staled
the plan-bound verdict. `plan-delta` turned that into a one-section review
instead of a full re-dispatch of the planning pass.

**Two review passes, run concurrently, found the same defect from two ends.**
The documentation pass noticed the quoted Grafana log line was synthesized; the
adversarial pass independently traced Grafana's notifier call path and proved
which level emits what. Neither alone would have produced both the catch and
the correction.

## What worked less well

**`other:eval-backlink-restales-plan`.** create-eval step 7 mandates editing the
plan to add the eval back-link, and create-ticket has already advanced the
ticket to `ready` by then. The edit changes the plan sha256, so the next
`reconcile` demoted the ticket back to `planning` and the plan verdict no longer
bound. The two skills' step orders conflict: the back-link edit has to happen
before the planning review is dispatched, or the advance to `ready` has to come
after it.

**`other:worktree-missing-local-files`.** The first stamp in the worktree failed
`terraform validate`, because `services.tf` reads `file(".../.ssh/id_rsa")` and
`.ssh` is gitignored, so it does not travel with a worktree. The repo already
solves this with `just worktree_setup <path>`, which symlinks `.ssh` and copies
both `prod.tfvars` files, but the implement-ticket protocol never mentions
looking for such a recipe. Cost: one red gate and one wasted 153s gate run.

**`other:missing-scope-digest-in-briefing`.** All four review dispatches
reported that their briefing carried no 64-hex scope digest, so each fell back
to whole-tree binding. Stricter, so nothing was weakened, but the protocol names
the scope digest as a fan-out input without saying where an implementation pass
gets one.

**`other:signed-eval-unfixable-by-loop`.** The adversarial pass proved eval row
2's scorer pathspec `'deployments/*/vars/'` matches zero files, so that
guardrail greens unconditionally. `loopctl eval-amend` is refused twice over:
inside a linked worktree, and without the marker signer's counter-signature. A
scorer defect found during review therefore cannot be fixed in the cycle that
found it, and the ticket ships with a known-hollow row.
