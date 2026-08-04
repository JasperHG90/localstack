---
slug: D7-cli-service-join-consul-catalog
blockers: []
friction: [other:contaminated-red-first-experiment, other:review-corrected-my-answer-to-the-operator, other:plan-anchors-broke-on-archiving]
worked: [other:red-first-through-the-command, other:keyword-only-as-a-guardrail]
cycles: 2
gates_red: 1
harness_change: Archiving a done ticket breaks every `path:line` citation another plan makes into it, silently, mid-session.
---

## What worked

Choosing the red-first test by what CAN go red. The obvious regression test
calls `join()` with the new catalog argument, and against the pre-fix code
that only raises `TypeError`, which proves nothing about the defect. The test
that earns the name goes through the command instead: same fixtures, same
path a user takes, and it failed on the assertion (`unresolved` where
`consul-name` belonged) with nothing raised. The eval names that distinction
explicitly so the next person does not pick the useless one.

Making the new parameter keyword-only rather than merely required. The plan
reviewer proved that required alone is not enforceable here: `catalog` and
the existing `service_names` are the same type, so a positional version lets
an unchanged caller bind its names dict to it and type-check clean, shipping
the bug green AND degrading every routed row's health to "no check". The
adversarial reviewer then found the guarantee is even stronger than claimed:
the `*` cannot simply be deleted, because `service_names` carries a default,
so the only route back to positional is a reorder that reddens all ten call
sites. A guardrail that fails loudly in three directions beats a comment.

## What worked less well

My red-first experiment was contaminated and I did not notice. I copied
`cli/` to a scratch directory to reconstruct the pre-fix code, but the copy
carried its `.venv`, so `uv run` stayed bound to the editable install in the
worktree and I was measuring the FIXED code while believing I was measuring
the broken one. The conclusion happened to be right; the method was worthless.
The reviewer caught it, rebuilt the tree without a venv, checked
`localstack_cli.__file__` resolved into the copy before measuring, and got
the real red. Verifying where the import came from is the step that makes a
shadow-copy experiment mean anything.

I gave the operator a wrong answer before this ticket existed. Asked why `s3`
rendered unresolved, I checked job names and Consul service names and
addresses, concluded nothing could resolve it, and said so. The plan reviewer
found that `GET /v1/catalog/services` (the very request this ticket adds)
returns `minio -> ["http", "s3"]`: the tag is declared by the job itself.
`s3` still ships unresolved, because a tag rung needs a rule for tags several
services share, but "deferred with the evidence recorded" and "impossible"
are different claims and I made the wrong one. Three lookups is not an
exhaustive search.

Archiving broke this plan mid-authoring. D3, D4, D6 and R5 were archived
while D7 was being written, and D7 cites D3's plan three times, so
`verify-plan` went from valid to invalid between two consecutive runs with no
edit in between. The content and line numbers were identical under
`.loop/archive/<slug>/plan.md`, so the fix was mechanical, but the failure is
silent and time-dependent: any plan citing a not-yet-archived ticket is one
archive run away from invalid.

Two review-cycle notes for the record. The eval-row count in
`docs/cli-read-commands.md:44` ("Thirteen exist") is already stale at 14 of
24, because the cluster gained a job between review passes; it is untouched
context in this diff and the eval carries the same number, so it is left
alone rather than re-pinned to another value that will rot. And
`ROADMAP.md:201` still cites an archived D2 path, which is the same class of
breakage as above and wants its own sweep rather than a line in a CLI commit.
