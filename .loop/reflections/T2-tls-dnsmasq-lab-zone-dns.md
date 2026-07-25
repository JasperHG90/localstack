---
slug: T2-tls-dnsmasq-lab-zone-dns
blockers: []
friction: [other:approved-option-on-false-premise, other:ambiguous-eval-needs-positive-control, other:invalid-control-passed-as-proof]
worked: [other:run-the-real-image-against-real-queries, other:measure-what-the-dependency-answers, other:withdraw-rather-than-repair-rationale]
harness_change: An operator decision recorded on a plan carries no evidence of what it was decided ON, so a disproved premise leaves the approval standing and looks like consent to the outcome. Plan front-matter could carry the rationale a resolved fork was approved against.
---

Review cycles: 1 of 3. Gates red: 0. Blockers: none. Nothing applied; the ten
live eval rows are pending an operator run, one of them operator-scored and
dependent on a router change no ticket can automate.

## What worked

**Running the real image against real queries.** Every claim that mattered
was measured rather than reasoned about: the wildcard answers, an unused name
answers, the bare domain answers, the apex returns the real public address,
MX survives, recursion works. That last set is the regression guard for the
operator's live website and mail, and reasoning about `address=` semantics
would not have been evidence.

**Measuring what the dependency actually answers, not what it is documented
to answer.** The reviewer resolved Consul directly and found bridge addresses
where the plan assumed routable ones. The plan, the docs, and my config
comment all agreed with each other and all were wrong together, because they
shared one unchecked assumption. Only a query settled it.

**Withdrawing the option instead of repairing its rationale.** The operator
approved the `.consul` forward because it would "fix a live documentation
lie". It does not. The tempting move was to keep the line and rewrite the
comment, since the line is harmless in isolation. But the approval was given
for a reason, and once the reason is disproved the approval does not transfer
to the outcome. Removing it and marking the recommendation withdrawn returns
the decision to the person who made it.

## What worked less well

**An eval row that could not fail.** Row 5 asked for a TXT query on a lab
name, expecting "upstream answer or NXDOMAIN, never NODATA". dnsmasq returns
NOERROR with zero answers there whether or not forwarding works, because the
name exists locally as an A record. The row would have scored a correct
system as broken, or a broken one as correct, depending on how the reader
squinted. The fix was a positive control: point `address=` at a domain that
HAS a small upstream TXT record and confirm the record still comes back. A
check that cannot distinguish the two outcomes is not a check.

**I ran an invalid control and nearly believed it.** The first attempt to
prove non-A forwarding compared dnsmasq against upstream for `google.com`
TXT, and both returned zero answers, which looked like agreement. Both were
truncated: the raw query carried no EDNS, so `tc=1` and the answers were
dropped. Two matching wrong numbers read exactly like a passing test. Only
checking the truncation bit exposed it. When a control agrees suspiciously
well, verify the control before trusting the result.

**A plan recommendation carried an approval but not its grounds.** The
operator's yes to Q4 was recorded as a decision; the premise it rested on
lived in prose above it and was never re-checked when the ticket ran. Nothing
in the harness links a resolved fork to the evidence it was resolved against,
so a disproved premise leaves an approval standing that now appears to
endorse something the operator never evaluated.
