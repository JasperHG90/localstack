---
slug: N2-netsec-remove-dnsmasq-for-public-dns
blockers: []
friction: [other:stale-eval-row-after-reorder, other:no-destroy-provisioner]
worked: [precondition-verified-independently, reviewer-measured-the-real-resolver]
cycles: 2
gates_red: 0
harness_change: "When a ticket's priority moves it ahead of one it used to follow, re-read its eval rows: rows asserting the other ticket's post-state go quietly unsatisfiable."
---

## What worked

**Verifying the precondition against something other than the thing being
removed.** The whole ticket rests on public records answering, and querying
`1.1.1.1` and `8.8.8.8` rather than the local resolver is what made the check
mean anything. The plan recorded that the precondition had been false a few
hours before it was written, so re-running it at implementation time rather
than trusting the note was the right instruction to have left behind.

**The reviewer measured the resolver that actually matters.** I checked two
public resolvers. Adversarial review went further and queried the router every
household device uses, then told it apart from dnsmasq by TTL: 300 from the
router against 0 from dnsmasq. That turned the plan's headline risk, a
resolver refusing an RFC1918 answer from public DNS, from a hypothetical into
something ruled out empirically for every device on this network. Using TTL as
the discriminator is not something I would have reached for.

**Two review cycles, zero red gates.** Both findings were in the eval and the
doc rather than the code. The code change is three deletions, which is a hard
thing to get wrong, and the risk sat entirely in whether it was safe to make
them.

## What worked less well

**`other:stale-eval-row-after-reorder`.** One eval row asserted the edge serves
lab hostnames over valid TLS, which is only true after the cutover ticket
lands. It was written when this ticket was expected to run after that one; the
operator then reprioritized it ahead, and the row silently became
unsatisfiable. It read as correct right up to the point of scoring it. Same
defect class the audit ticket exists to sweep, and the same one that produced
a relayed finding on the cutover ticket earlier in this session: a decision
changes the world, and a check written against the old world keeps looking
plausible. Reordering a ticket is exactly the kind of edit that prompts nobody
to re-read its eval.

**`other:no-destroy-provisioner`.** `null_resource.firewall` only runs `ufw
allow` and has no destroy step, so `terraform plan` reporting the resource
destroyed says nothing about the host. Ports 53/udp and 53/tcp stay open until
someone deletes them by hand. The plan flagged it and an eval row catches its
omission, but the shape is a trap for anything touching the firewall map, and
review supplied the sharper version of the warning: delete by rule spec, not
by index, because `ufw delete 22` renumbers 23.
