---
verdict: pass
plan: b7c35b8b529a66c9243e6eabb3deb27a5332a14cd938ea1118192cb2c4d780c8
---

# Plan review: R6-rollout-memex-human-oidc (pass id: plan-validator)

Supersedes my `d6e07701` verdict. Fingerprint recomputed before and after
writing: `sha256sum .loop/plans/R6-rollout-memex-human-oidc.md` =
`b7c35b8b529a66c9243e6eabb3deb27a5332a14cd938ea1118192cb2c4d780c8`.

**Premise verdict: SOUND.**

Deterministic floor: `loopctl verify-plan R6-rollout-memex-human-oidc` returns
`valid`.

This pass carries forward the five mechanisms confirmed against `d6e07701`
(per-client `key` lifting the TTL ceiling, provider JWKS published from the
keys its allowed clients reference, `access_token_ttl = 2592000` driving the
client's cached expiry, memex first-match rule ordering, Q7 being a real
fork). They are not re-derived. What follows attacks the two operator
decisions (A1, A2), the three required fixes (B1, B2, B3), and the
consistency of the two-tier design after the swap.

## Per-assumption findings

### The changed decisions

**A1 — the admin tier is a `local.app_user_groups` entry, and
`vault_identity_group.admin` is no longer part of the design. HOLDS.**
All 16 occurrences of `vault_identity_group.admin` in the plan are
explanatory or negative: `:80`, `:166-177`, `:254-256`, `:295` (R21), `:330`
("NOT named here"), `:408-410` ("NOT TOUCHED AND NOT NAMED"), `:746`
(standing rule, "the only such group ... is untouched"), `:892` (expected
diff: no change), `:1114-1124` (Q2's rationale). The two that name a command
(`:814`, `:1025`) are `vault read identity/group/name/admin`, a read. Grep
for `vault write` across the plan returns four hits and none writes a group:
`:170` and `:1118` describe the break-glass property, `:709` is V5's "**No
`vault write` here**", `:855` is the key-rotate lever. No resource,
assignment or check touches the break-glass group. The rationale is
load-bearing and correct at its anchors: `external_member_entity_ids = true`
is `deployments/infrastructure/roles.tf:131`, the "invisible to every
`terraform plan`" warning is `:125-126`, the wildcard policy sits above at
`:31-116`.

**A2 — a sibling `local.app_user_group_members` map wired to
`member_entity_ids`. HOLDS.** The gap it closes is real:
`vault_identity_group.app_user` (`roles.tf:165-177`) sets `name`, `type`,
`policies` and `metadata` and no member field, while the comment two lines
above (`:158-161`) and `docs/cluster-roles.md:140-141` both promise "a
Terraform edit to `member_entity_ids`". The chosen shape leaves
`local.app_user_groups` as the name-to-description map that
`docs/cluster-roles.md:118-126` documents, so no existing consumer
instruction goes stale. The rejected third option is rejected for the right
reason: `for_each = local.app_user_groups` (`roles.tf:166`) is shared, so
`external_member_entity_ids = true` would apply to every future tier.

### B1 — the rewritten break-glass paragraph

**P24 — `rotate` stamps `ExpireAt` on the CURRENT signing key only. HOLDS,
verified line by line at the cited tag.** `namedKey.rotate`
(`vault/identity_store_oidc.go:1708-1760` at `v2.0.3`) loops the key ring,
stamps `key.ExpireAt = now.Add(verificationTTL)` on the single member whose
`KeyID` matches `k.SigningKey.KeyID`, and `break`s (`:1715-1722`), then
promotes `k.SigningKey = k.NextSigningKey` (`:1740`). A grep for `ExpireAt`
across the whole file finds writes at exactly one place, `:1719`. The
periodic path only *drops* members whose `ExpireAt` has passed
(`:1997-2016`); it never re-stamps. The escape hatch is shut as claimed: the
key create/update path sets `RotationPeriod`, `VerificationTTL`,
`AllowedClientIDs` and `Algorithm` and touches no ring member, and it refuses
the update outright with "unable to update key %q because it is currently
referenced by one or more clients with an id_token_ttl greater than %d
seconds" (`:606-621`). The rotate handler applies no 10x check to the
override, so `verification_ttl=0` is accepted (`:944-958`).

**So §9 lever 2's new wording is correct, not merely different.** The current
signing key signed exactly the tokens issued since it was promoted, which is
the last rotation, so "revokes the tokens issued SINCE THE LAST ROTATION, not
all outstanding tokens" is the right characterization. The non-convergence
claim follows for the same reason: call 2 stamps the key call 1 had just
promoted, which has signed nothing. The arithmetic checks out too,
`2592000 / 604800 = 4.3`, so "roughly four older ring keys" that did sign live
tokens stay verifiable and unreachable.

**Lever 1 really is total. HOLDS.**
`keyIDsReferencedByTargetClientIDs`
(`vault/identity_store_oidc_provider.go:1643-1691`) resolves the provider's
`AllowedClientIDs` to client records, collects `client.Key`, and emits every
KeyID in that key's ring. Drop the memex client from
`local.oidc_provider_client_ids` (`deployments/infrastructure/oidc.tf:79-84`)
and the `memex-human` ring leaves the provider JWKS entirely, while `lab`
stays for the smoke and nomad clients. This is the paragraph §7 tells the
implementer to publish verbatim into `docs/vault-human-auth.md`, and it is
safe to publish.

### B2 — the expected-diff table

**P25 — two new tiers grow the smoke assignment from 1 entry to 3. HOLDS,
and the count matches what `terraform plan` really renders.** The chain
resolves exactly: `local.all_app_user_group_ids = values(local.app_user_group_ids)`
(`roles.tf:200`), `local.app_user_group_ids = { for k, g in
vault_identity_group.app_user : k => g.id }` (`:193`), and
`group_ids = concat([vault_identity_group.smoke.id], local.all_app_user_group_ids)`
(`oidc.tf:129`). A repo-wide grep confirms `oidc.tf:129` is the *only*
consumer of `all_app_user_group_ids` outside other worktrees.
`local.app_user_groups` ships empty (`roles.tf:152-163`), so the live value is
one element today.

I checked the rendering rather than trusting it, because `group_ids` is a
`TypeSet` (`terraform-provider-vault v5.3.0`,
`vault/resource_identity_oidc_assignment.go:39-45`, pinned at
`deployments/infrastructure/.terraform.lock.hcl:87-88`) and two unknown
strings can collapse inside a cty set. They do not. Probe, apply-then-modify
against `terraform_data` with
`toset(concat(["known-smoke-id"], [unknown, unknown]))` on Terraform v1.14.3:

```
~ input = [
      "known-smoke-id",
    + (known after apply),
    + (known after apply),
  ]
```

The implementer sees one existing entry plus two additions, three total, as
an `update in-place`. `group_ids` carries no `ForceNew` in the provider schema
(only `name` does, `:24-30`), so there is no destroy/recreate of the live
smoke assignment either. The table's "no effective access changes today" also
holds: `operator` is already a member of `vault_identity_group.smoke`
(`oidc.tf:114`).

### B3 — V5 no longer writes an unmanaged group

**HOLDS.** V5 (`:706-742`) is now a Terraform edit to
`local.app_user_group_members` plus an apply with the plan read first, and it
states "No `vault write` here, and no restore step" with the right reason.
The read-then-restore-to-exactly-that rule survives as a standing rule
(`:744-751`) with its evidence intact: `docs/cluster-roles.md:70-73` is "**The
list is REPLACED, not appended to.**" and `:84-94` is the join/leave command
pair. Both anchors resolve verbatim.

### Two-tier consistency after the swap

**HOLDS.** §7's `grant_rule` values (`:448`) are `app-memex-admins` →
`admin` at index 0 and `app-memex-readers` → `reader`, matching the two
`local.app_user_groups` keys at `:366-367` and the two
`local.app_user_group_ids[...]` lookups in the assignment at `:319-322`. §8's
V1 asserts the reader claim and the `403` write denial, V5 asserts the dual
claim and the non-`403` write, G5 asserts the tiers, the derived growth and
the untouched break-glass group. §10 puts the members map, both tiers and the
key in R6a and the client in R6b, which honors the one hard ordering
constraint (`key` immutable after create, P17); the client-after-key edge is
also given for free by the Terraform reference. Nothing in the plan gates
memex on `developer` or `admin`: all 10 `developer` mentions are the §5
prohibition, the `nomad_oidc.tf` precedent, or P11's live probe.
`vault_identity_entity.operator` resolves at
`deployments/infrastructure/auth_userpass.tf:38-44` as claimed.

### The three self-reported pre-existing fixes

All three were real defects, and all three are now correct.

- **V6's cross-reference** (`:763`) points at "§9 mode 2", and §9 mode 2
  (`:930-934`) is the `access_token_ttl` left at `3600` failure. Right mode.
- **G2's assertion** (`:772-778`) now reads
  `"value":"app-memex-admins","policy":"admin"` at index 0, which is the
  string that actually appears in the `memex.hcl` array at `:448`. The old
  "admin at index 0" was ambiguous against the memex policy name.
- **Q3's tail** (`:1172-1177`) now says revocable in full only by the first
  lever, and that rotation reaches only tokens issued since the last
  rotation, matching §9 and P24.

### Q8

**A real fork, correctly homed.** It exists only because A1 made the admin
tier Terraform-managed: before the revision the resting state was forced, now
it is a standing-privilege choice. Three named ends, a recommendation (end 1,
where §8 already leaves the membership, so it costs no extra apply), and an
explicit "does NOT block R6a". Not noise.

## Most dangerous assumption

**P24, the reach of `rotate`.** It is the one claim §7 tells the implementer
to copy verbatim into `docs/vault-human-auth.md`, where every future Vault
consumer will read it during an incident. It is now correct at the source
(`vault/identity_store_oidc.go:1715-1722`, `:1740`, `:1997-2016`,
`:606-621`), and the plan names lever 1 as the complete one. Had it stayed
wrong, the failure mode was an operator believing outstanding tokens were
dead while four ring keys still verified them.

## Nits (none blocking)

1. §9's expected-diff table (`:886-894`) tells the implementer to "read the
   whole plan against this expected list" but omits
   `vault_identity_oidc_key.memex_human` being created, which R6a also lands
   (`:1017-1018`). G5 scopes its stop-rule to `roles.tf` and `oidc.tf`
   (`:800-801`), so the two do not actually conflict; adding the key row, or
   scoping the table's sentence the way G5 scopes its own, would close it.
2. G5's "and the two new entries are those tier ids" (`:806-807`) is not
   readable from the R6a plan: the group ids do not exist yet and render as
   `(known after apply)` (probe above). The count is checkable at plan; the
   ids are checkable after apply, which R6a's read-back step already does.
3. §7's sketches for `vault_identity_oidc_client "memex"` (`:333-339`) and
   `vault_identity_oidc_assignment "memex"` (`:315-332`) omit the required
   `name` field. It is pinned elsewhere (the data source reads
   `name = "memex"` at `:425`, and §9 mode 4 quotes
   `no client found at "identity/oidc/client/memex"`), and Terraform fails
   loudly on a missing required field.
4. §9's timing note (`:874-875`) covers memex's 3600 s JWKS cache but not
   Vault's own prune delay on lever 2: the stamped ring member stays in the
   JWKS until `expireOIDCPublicKeys` runs
   (`vault/identity_store_oidc.go:1949`, scheduled from `nextRun` at
   `:2141-2185`, which the rotate handler flushes). About a minute, dwarfed by
   the 3600 s, but the published paragraph is the place to be exact.

## Contract hygiene

Clean. Code surface anchors resolve (spot-checked `roles.tf:118-201`,
`oidc.tf:28-32`, `:72-84`, `:109-148`, `nomad_oidc.tf:30-64`,
`services.tf:1-26`, `:180`, `memex.hcl:138-148`,
`docs/cluster-roles.md:70-141`, `docs/vault-human-auth.md:262-306`, `:322-334`,
`docs/memex-oidc-verification.md:1`, `:21-38`, `:140-160`). Gates are the
discovered ones (`just pre_commit`, the four pre-commit hooks,
`scripts/tf_validate.sh`), non-goals are explicit and now include the
break-glass group, every check has its declared home in
`docs/memex-oidc-verification.md`, and the open forks (Q1, Q4, Q5, Q8) each
carry a recommendation while the settled ones (Q2, Q3, Q6, Q7) are marked
SETTLED with the deciding evidence.

## Verdict

`pass`. The premise is SOUND. Both operator decisions are carried through
consistently, the three required fixes are correct rather than merely
different, the three self-reported pre-existing fixes hold, and Q8 is a real
fork with a recommendation. The four items above are nits, not conditions.
