---
slug: U7-upgrade-bifrost-2x
blockers: []
friction: [prek-first-pass-rewrite, other:apply-blocked-by-permission, other:cross-ticket-anchor-drift]
worked: [mutation-tested-review, measured-baseline-before-edit]
cycles: 0
gates_red: 0
harness_change: plan-rebind refuses at `ready` but the message does not say the stage is the reason until you read it twice; naming the current stage in the refusal would save a round trip.
---

## What worked

**The before-run was the whole design, and it paid off twice.** The plan made
`scripts/bifrost_smoke.py` run against the OLD gateway as well as the new one,
on the reasoning that a post-only assertion cannot separate "the upgrade broke
it" from "it was never true". Running it at 1.6.7 turned five hopeful
assertions into a measured baseline before a single line changed.

**Probing both directions caught a trap nothing else would have.** The plan
review measured rerank auth with the document shape crossed against key state
and found that at 1.6.7 payload parsing precedes the virtual-key check: an
unkeyed bare-string probe returns 400, never reaching auth. This ticket is
about switching to bare strings, so an implementer writing the auth probe from
the requirement alone would very likely have sent bare strings, failed the
blocking before-run, and either stalled or — worse — softened the assertion for
looking too strict. The fix was one clause pinning the object form.

**The adversarial pass mutation-tested rather than read.** It substituted bare
strings into assertion 1 and top-level `routing_info` into assertion 5 and
confirmed both mutants fail live, which is what proves a pin is load-bearing
rather than decorative. It also injected a sentinel as the virtual key and
rendered all thirteen failure messages to prove no credential can escape.

**`routing_info` over the dimension count.** The embeddings assertion originally
checked only that the vector had 768 elements. A 200 carrying 768 floats could
be answered anywhere; `extra_fields.routing_info` naming `embark-cluster` is
what proves the call reached the private-IP upstream, which is the SSRF premise
this ticket most depends on.

## What worked less well

**`prek-first-pass-rewrite`.** The convenience lint pass reported "1 file would
be reformatted" without writing, because the hook is pinned to
`ruff format --check`. Two extra round trips to notice the check-mode flag and
run the formatter directly.

**`other:apply-blocked-by-permission`.** `terraform apply` was refused by the
permission classifier, so the deployment runbook (§10 steps 4-9) is outstanding
and every runtime eval row is unscored. The code, the gates and both review
passes are complete; the upgrade itself is not. The adversarial verdict says so
explicitly rather than implying the ticket delivered its outcome. Worth noting
the sequencing mistake underneath it: the apply was attempted before the review
passes, when §10 says the runbook runs after them. Backing up was right.

**`other:cross-ticket-anchor-drift`.** This plan cites `path:line` anchors into
OV1's plan, which was being edited in parallel. Between two review cycles those
anchors drifted 25 lines, and one reviewer's own correction was stale by the
time the next agent checked it. Anchors into another live ticket have a short
shelf life; anchoring to a stable heading rather than a line would have held.

**Two pre-existing comment drifts were found and deliberately not fixed here.**
`services.tf:530` says "two Ollama Cloud keys" where four are configured, and
`:556` omits `embark/reranker`. Both predate this ticket and sit outside its
declared four-file surface. Fixing them mid-review would have staled the tree
the adversarial pass was reading, which is exactly the failure that invalidated
L5's verdict. They are logged for a separate contained change rather than
skipped.
