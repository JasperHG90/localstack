---
slug: R6-rollout-memex-human-oidc
blockers: []
friction: [other:upstream-moved-mid-ticket, other:checks-that-fail-healthy-systems, other:generalised-a-conditional-lever]
worked: [other:probe-past-the-stated-limit, other:converging-review-passes, other:operator-answer-reshaped-design]
cycles: 3
gates_red: 0
harness_change: the stamp fingerprint excludes .loop/, so eval and archive edits are reviewed at working-tree content and are not covered by the tree binding a verdict asserts
---

## What worked

**Probing past a limit instead of reporting it.** The operator asked for a
month-long session. My first answer was "impossible": Vault issues no refresh
token and the shared `lab` key caps TTL at 24h. Both facts were true and the
conclusion was wrong. Vault caps `id_token_ttl` by the verification_ttl of
THE KEY THE CLIENT REFERENCES, and `key` is a per-client field, so a
dedicated key lifts the ceiling with zero effect on other consumers. The
lesson is narrow and reusable: when a limit is quoted from a shared resource,
check whether the resource is actually shared, or merely shared by default.

**Two review passes converging.** As in R5, the adversarial and
documentation passes independently reached the same required fix in two
separate cycles. Two agents landing on one defect without seeing each other
is much stronger evidence than either alone, and it made every fix decision
trivial.

**An operator answer that improved the design.** Asking which group backs the
admin tier surfaced that `vault_identity_group.admin` is break-glass, with
membership outside Terraform. Mapping daily memex admin onto it would have
meant living in break-glass permanently. The two-tier `app_user_groups`
answer avoided that AND removed a check that would have written
`member_entity_ids` to a group no plan can diff.

## What worked less well

**Upstream moved mid-ticket** (`other:upstream-moved-mid-ticket`). memex
v1.2.0 shipped while this session was running, closing the very issue that
had made the human half impossible and inverting a log polarity R5's runbook
asserts. Every premise verified at the v1.1.0 tag needed re-checking. Nothing
detects this: a plan's premises are bound to a plan hash, not to the upstream
version they were measured against. Pinning the tag in each premise, as this
plan does, is what made the re-check cheap.

**Three checks would have failed a healthy system**
(`other:checks-that-fail-healthy-systems`). V2 expected `1 dot-separated
segments` where a Vault batch token yields 2; V5's eval row expected
"Succeeds" where a fabricated uuid correctly returns 404; V1's discriminator
lost the reader-only precondition that makes "a non-403 is wrong" true. Each
would have reported a fault on a correct deploy. This is the same class the
ticket exists to fix in R5's D2, which is uncomfortable and worth saying: it
is easy to write an assertion whose polarity is backwards while believing you
are being rigorous. Rendering the artifact and running the assertion beats
reasoning about it.

**I generalised a conditional lever** (`other:generalised-a-conditional-lever`).
The revocation advice — remove the client from the provider list — is
complete only when that client is the SOLE referencer of its key. I wrote it
as universal guidance for future consumers. A consumer on the shared `lab`
key would have reached for it mid-incident and found it did nothing. Carrying
a mechanism from the case that motivated it to general advice drops the
precondition unless you go looking for it.
