---
slug: F14-foundation-role-taxonomy
blockers: []
friction: [other:untested-limit-claimed, other:probe-clobbered-managed-state, other:generalisation-contradicted-own-measurement, other:runbook-command-never-run]
worked: [other:negative-control-per-claim, other:reviewer-overturned-my-premise, other:measure-instead-of-hedge]
harness_change: "Six review cycles here, and three of them existed only because a required fix touched a fingerprinted file, staling two verdicts that had nothing to do with the fix. The reviews were still true; only the binding was stale. Twice the cheapest correct action was a one-sentence doc edit and the harness charged two full re-reviews for it. A verdict that recorded which paths it examined could be re-bound when its own scope did not move. Same finding as G2's reflection, now with a second ticket's evidence."
---

## What worked

**A negative control per claim, not per ticket.** Every capability assertion
here was measured against a token that should fail. `default` alone cannot
`list sys/leases/lookup`; `admin` can. A non-member is refused by the smoke
client and admitted by an `allow_all` client, same entity, same request. Without
the failing half, each of those is a green result that proves nothing, and this
ticket's whole product is assertions about who can do what.

**A reviewer overturning a premise rather than a detail.** I filed two
requirements as unprovable without a browser. A reviewer checked and found
`identity/oidc/provider/lab/authorize` is an ordinary API endpoint that takes a
Vault token and returns the code in the response body. Both clauses were then
proven headlessly in about ten minutes, including decoding an `id_token` to
confirm a scaffold-created tier arrives in `groups` as a real array. The
finding was not that my answer was wrong; it was that my question had been
retired without being asked.

**Preferring a measurement to a hedge.** The plan allowed "say plainly it is
unverified" as an out for the `allow_all` clause. Taking the out would have
passed review. Running it took one throwaway client and one scratch entity, and
turned the branch four of six consumers will copy from documented-and-assumed
into measured.

## What worked less well

**I claimed a limit I never tested, and the claim was load-bearing.** "Needs a
browser" was written as a constraint and read as one. An admission of ignorance
looks like honesty, which is exactly what makes it dangerous when it is
standing in for a measurement nobody attempted. The same shape appeared twice
more in miniature: `vault token lookup -field=entity_id` does not exist, and I
briefly simplified a runbook command to a form I had not run.

**A probe clobbered Terraform-managed state, twice, and the first repair hid
the second.** Writing one `metadata` key to the operator entity replaced the
whole map, evicting `managed_by` and `kind`. The next apply restored them,
which is where an unexplained "2 changed" came from. My cleanup then emptied
the map again and left live drift that only a reviewer's plan caught.
Terraform healing the first eviction is what made the second easy to miss.

**A generalisation that contradicted a measurement in the same file.** I wrote
"a probe that writes one field silently drops the rest" fifty lines above my
own record that omitted fields *are* preserved. Both were true of different
things: fields merge, map-valued fields are replaced wholesale. Writing the
broad version was faster than working out which one I had actually seen.

**A runbook command that would have hurt someone.** The first `leave` was
`member_entity_ids=""`, directly under a `join` taking a comma-separated list.
It empties the group, so an operator following it mid-incident evicts every
other break-glass holder. Nothing in the ticket asked for these commands; they
were added because the docs told operators to join and leave by hand and did
not say how. Incident text deserves the same standard as code, and I wrote it
in the register of a comment.
