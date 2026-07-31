---
slug: F2-foundation-vault-oidc-provider
blockers: []
friction: [other:silent-failure-passes-apply, other:assertion-passes-on-wrong-content, other:edit-script-reported-false-success, reviewer-boilerplate]
worked: [other:operator-shrank-the-ticket, other:reviewer-verified-against-shipped-binary, other:terraform-validate-as-schema-check]
harness_change: a gate that runs `terraform validate` proves schema, never semantics - every defect this ticket shipped and fixed was schema-valid
---

## What worked

**Shrinking the ticket removed a whole class of defect.** The pre-rewrite F2
owned every consumer's OIDC client and stated the count four different ways
across its body, its addendum, the eval DoD and eval row 3. The operator's
decision to keep only the singleton pieces did not just simplify the build, it
deleted the contradiction: with no consumer clients there is no count to
reconcile, and the Terraform cycle between the key and its clients disappears
with it. Worth remembering that a scope question can dissolve a correctness
question.

**Reviewers verified against the shipped artifact, not against reasoning.** The
adversarial pass pulled Vault's own canonical scope template out of
`/usr/bin/vault`, rendered the fixed literal in `terraform console`, and
checked the live server's OpenAPI for how `template` is accepted. The
documentation pass built a scratch Terraform root and ran `apply -replace=`
with and without `-var-file` to settle whether the flag was needed. Three
independent confirmations of one line beats one confident assertion.

**`terraform validate` in the gate is worth having, within its limits.** It
caught nothing here because nothing was schema-wrong, but it is the reason the
provider-schema questions (does `vault_identity_oidc_key_allowed_client_id`
exist in 5.3.0, does `vault_generic_endpoint` accept this shape) were cheap to
settle rather than discovered at apply.

## What worked less well

**`other:silent-failure-passes-apply`.** The headline defect. The `groups`
scope template used `jsonencode`, which quotes the placeholder; Vault emits
fully-formed JSON per substitution, so the result was invalid JSON. Apply
succeeds, because Vault validates the template against a zero-group entity
that renders `{"groups": "null"}` and parses. Only real token issuance breaks
it, and even then `mergeJSONTemplates` logs a warning and continues with an
empty claim set. A signed token comes back with the claim simply absent. L1,
R1 and R4 all gate on that claim, so this would have surfaced three tickets
later as "oauth2-proxy authorizes nobody" with nothing pointing back here.
Nothing in the gate could have caught it: it is schema-valid, plan-valid and
apply-valid.

**`other:assertion-passes-on-wrong-content`, twice in one ticket.** The eval's
original secret guardrail scored `detect-private-key`, a hook matching a fixed
PEM blocklist that cannot match `hvo_secret_...`. Then the fix for the
`jsonencode` defect could not be exercised, because the close-out never sent
`scope=openid groups` and Vault returns a signed token with no claim when only
`openid` is requested. The test for the silent failure had the same silent
failure. "A token came back" was the evidence in both cases.

**`other:edit-script-reported-false-success`.** My own tooling did it too. An
edit script called `.replace()` without an assert and printed `"LOW fixed"`
unconditionally, so a no-op match reported as done, and I told the operator a
fix had landed when it had not. The reviewer caught it, and I only found it by
checking. Every subsequent edit used `assert old in t`. The lesson is not
subtle: a mutation that cannot fail is not a check.

**`reviewer-boilerplate`, and worse, a self-inflicted stall.** Four review
cycles, two passes each, several killed mid-run by a session limit and by my
own edits landing while a reviewer was reading the tree. One agent reported
"the tree moved under me mid-review". `.loop/` sits outside the fingerprint so
the hash does not move and nothing warns. Freezing the tree from dispatch to
join is a rule I named in A1's reflection and then broke twice more.

## Cycles, gates, blockers

Review cycles: 3, the configured cap. Gates red: 0 — `just pre_commit` passed
on every stamp, including the stamps of the version whose OIDC claim would
never have been emitted and the version whose test could not detect that.
Blockers: none.

Two defects ship, both in the verdicts:
`docs/vault-human-auth.md`'s "Adding a service" section does not tell consumers
their client must REQUEST the `groups` scope, and line 106 says "Taint" where
the command uses `-replace`. Both are one sentence. Neither is fixable, because
`review_cycles` is at the cap and any edit stales the stamp while the re-gate
that would refresh it is refused — so the fix would block the ticket rather
than land it. Third ticket in a row to hit this (A1, F9, F2), which makes it a
harness property worth addressing rather than three coincidences: findings
raised in the final cycle are structurally unfixable.

**Not merged, by operator instruction.** Committed on `loop/F2-...`; main is
untouched. Nothing is applied to the cluster.
