---
slug: N1-netsec-restrict-prometheus-loki-to-cluster
blockers: []
friction: [other:cycle-spent-on-self-inflicted-slop, other:worktree-setup-misses-second-root, other:polish-after-pass-hit-the-cap]
worked: [measured-the-firewall-instead-of-reading-it, reviewer-extended-rather-than-confirmed, dry-run-as-the-safe-probe]
cycles: 4
gates_red: 0
harness_change: "Run the doc slop scan before dispatching a review pass, not after. A semicolon splice cost a full review cycle here, and cycles are the capped resource."
---

## What worked

**Measuring the firewall rather than reading the Terraform.** The ticket looks
like a two-entry edit, and reading the config would have produced exactly that
edit and a broken cluster. Comparing the live iptables chain against ufw's own
rule database found two rules on the monitoring node that exist only in the
chain, one of them Grafana's LAN access. Applying the narrowed rule would have
dropped both, because every ufw write rebuilds the chain from the database.
Nothing in the plan, the diff, or `terraform plan` shows this. Only the host
does.

**`--dry-run` as the probe.** The question was what the next ufw write leaves
behind, and the honest way to answer it on a live cluster is to ask ufw to
print the payload without applying it. That turned a claim about a mechanism
into an artifact I could read, and review independently confirmed it mutates
nothing by hashing the rule file either side of five invocations.

**The reviewer extended the finding instead of confirming it.** I reported the
hazard as delete-only. Review showed `ufw allow` emits the same chain-replacing
payload, which moves the danger from a manual cleanup step to the Terraform
apply itself, and moves the fix from "before deleting" to "in the same apply".
Cycle 2 then caught that both halves of my consequence sentence were backwards:
losing the 9100 rule is harmless because that traffic is same-host and ufw
accepts loopback first, while losing Grafana's rule takes it down by every
route including the tailnet, the opposite of what I had written. Three cycles,
three findings I could not have reached alone.

## What worked less well

**`other:cycle-spent-on-self-inflicted-slop`.** A semicolon splice I wrote
cost a full review cycle: I found it after advancing to review, and fixing it
staled the stamp. Review cycles are the capped resource in this harness, and
spending one on punctuation is pure waste. The scan is cheap and belongs
before the dispatch.

**`other:polish-after-pass-hit-the-cap`.** Cycle 3 returned pass with two
minors. I fixed them, which unbound the verdict from the tree and needed a
fourth cycle the cap forbade, leaving the ticket wedged between a passing
verdict on an old tree and a corrected tree with no verdict. The protocol's
answer, blocking with `cap-exceeded`, discards the worktree, which is a poor
trade for two sentences. The operator raised the cap instead. The lesson is
that "pass with minors" is a decision point: fix them before the pass by
treating a reviewer's minors from the previous cycle as required, or accept
them. Deciding to fix after the pass is what costs.

**`other:worktree-setup-misses-second-root`.** This ticket's gate requires
`terraform plan` in both Terraform roots, and `just worktree_setup` copies only
`deployments/infrastructure/vars/prod.tfvars`, so the applications root cannot
plan in a fresh worktree. I copied the file by hand rather than widen the diff
to a task-runner fix outside the declared code surface. The recipe should copy
both.

**The cap bump rides in this commit.** `max_review_cycles` goes 3 to 4 inside a
firewall change, which is the wrong place for it, and the authorization was for
one pass on one ticket rather than a permanent global raise. Review flagged it
and declined to block on it. It should go back to 3.
