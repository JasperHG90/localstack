---
slug: T3-tls-edge-cutover-lab-domain
blockers: []
friction: [other:blanket-sed-ships-false-prose, other:plan-instruction-went-stale-under-me, other:requirement-with-no-metric-to-satisfy-it]
worked: [validated-the-real-cert-offline-before-apply, premise-audit-before-implementing, two-review-passes-caught-different-classes]
cycles: 3
gates_red: 0
harness_change: "A reference sweep across many files needs each site reopened and its prose judged. Path substitution is not a rename: the sentence around the anchor usually asserts something about what the anchor contains."
---

## What worked

**Validating the real certificate offline before the operator applies
anything.** The plan's own warning was that a wrong template renders blank
lines, HAProxy cannot parse `crt`, and twelve services go down together on
flag day. Reasoning about `.Data.data` versus `.Data` would not have settled
that. Pulling the actual certificate and key from Vault, concatenating them
exactly as the template will, and running `haproxy -c` in the same image the
job uses did: valid, exit 0. The negative controls mattered as much as the
positive one, and one of them paid off twice: the same real PEM at mode 0600
fails, which turns requirement 2's `perms = "0644"` from received wisdom into
a measured fact about this certificate.

**The premise audit before implementing.** It found the plan instructing me
to preserve a sentence that a ticket landing two hours earlier had made false.
No amount of care reading the diff would have surfaced that, because the
sentence was not in the diff.

**Two review passes catching genuinely different things.** The adversarial
pass found false prose around retargeted anchors and a wrong 30-versus-90-day
figure. The documentation pass found that I had explained the predecessor's
failure incorrectly, and proved it by generating throwaway certificates and
running OpenSSL's hostname verifier rather than by reading my sentence. Either
pass alone would have shipped the other's defect.

## What worked less well

**`other:blanket-sed-ships-false-prose`.** Twice, in one ticket. First on the
hostname sweep, where the rename turned "F3 shipped an unusable wildcard
(`*.localstack` cannot match a hostname)" into a sentence describing a
perfectly valid wildcard. Then on the `pki.tf` anchor retarget, where I
changed paths and left the surrounding prose naming the two resources this
apply destroys, plus one plan quoting text that exists only in an archived
file. I caught three of the first batch myself and thought that was the lot;
review found five. The second time I repeated the mistake after already
having been burned by it, and a third instance survived into the final cycle
because I fixed one site and assumed its twin.

The lesson is narrow and worth keeping: a path substitution is not a rename.
The sentence around an anchor almost always asserts something about what the
anchor contains, and that assertion does not travel with the path. Reopen
every site.

**`other:plan-instruction-went-stale-under-me`.** The plan carried an explicit
"do NOT touch this statement" for a sentence that was true when written and
false by the time I read it. Following the instruction would have shipped a
document that `dig` disproves. Overriding a plan instruction is the right call
here, but it is only available if something checks the world rather than the
plan, which is what the premise audit did. The eval carried the same stale
instruction, so the acceptance artifact would have scored the corrected doc as
wrong.

**`other:requirement-with-no-metric-to-satisfy-it`.** Requirement 11 asked for
an alert on days-to-certificate-expiry. Nothing in the cluster measures that,
so the requirement was unsatisfiable inside its own declared code surface, and
its eval row was a 100% deterministic check that nothing could pass. That is
worth catching at plan time rather than mid-implementation, since the honest
resolutions are all scope decisions for the operator. I also stated the
resulting exposure wrong at first, as 90 days, when the daily run with a
30-day renewal margin makes it 30.

**The review cap and the fingerprint.** Three cycles were spent almost
entirely on prose in `.loop/`, not on the infrastructure change, which never
moved after the first stamp. Discovering that `.loop/` sits outside the tree
fingerprint made the last round of fixes free, and knowing that earlier would
have saved at least one cycle.
