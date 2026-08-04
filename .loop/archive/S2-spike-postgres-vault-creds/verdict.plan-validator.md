---
verdict: pass
plan: 0f213bad57be9b2baa6719d1302ed6a5a7c70ade9544878c06d15f72ef896650
---

# Plan review — S2-spike-postgres-vault-creds (pass `plan-validator`, cycle 3, re-stamped)

Fingerprint verified with `sha256sum`:
`0f213bad57be9b2baa6719d1302ed6a5a7c70ade9544878c06d15f72ef896650` (matches the
briefing). `loopctl verify-plan S2-spike-postgres-vault-creds` returns **valid**
(exit 0).

## Premise verdict: SOUND

Gate verdict: **pass**. No required fixes remain.

## What changed since the fingerprint I last stamped

I confirmed the three edits are the ones I asked for, and that nothing else
moved. The plan grew from 771 to 778 lines, and the delta accounts for every one
of those 7 lines: +6 in §7 item 2, +2 in subticket 2, -1 in the S1 section.
Section offsets confirm it — `## 11. Open questions` moved 718 to 725 (+7), the
final line 771 to 778 (+7), and §8's Cleanup paragraph, the eval-marker note, §9
and the whole Premises block are identical apart from the shift.

### 1. Subticket 2's state check — **FIXED**

`plan:564-567` now reads "`terraform state pull | grep -c <the-password>` is 0,
and no `result` or `data_json` attribute in state holds it. The state lives in
the Consul backend, so `state pull` is the only way to read it — there is no
local `terraform.tfstate` to grep."

That is exactly right, and it now agrees with
`deployments/applications/backend.tf` (`terraform { backend "consul" {} }`) and
with §6 `:241-242`. The one verification of the claim the whole OQ3 exception
rests on can now actually run.

### 2. The S1 sentence — **FIXED**

`plan:701-705` is one grammatical sentence, and it is a paraphrase outside quote
marks, not a quotation. It matches
`.loop/plans/S1-spike-boundary-evaluation.md:322-324` on every element: "Hard
blocker: S2 first", "test the real 'keep' path (Vault credential engines)
end-to-end", "Spike order: S2 → S1". The duplicated "resolves the spike order" /
"fixes the spike order" clause is gone.

### 3. The single-link replacement case — **LANDED, and stated accurately**

`plan:308-314` now carries the observation: recreating any one of the three
write-only links alone hands it a freshly generated password while the other two
keep the old one; the connection fails loudly (`verify_connection` defaults true
and §7 `:332` forbids disabling it) while the KV2 copy would go stale in
silence; so bump all three versions on any single-link replacement.

Both halves check out. The vault 5.3.0 schema marks `verify_connection` an
optional bool ("Specifies if the connection is verified during initial
configuration"), and Vault's own default for it is true, so a desynced
connection password is rejected at apply. `vault_kv_secret_v2` has no equivalent
guard, so the silent-stale reading is right. The prescribed mitigation (bump all
three) does not depend on either, which is the robust way to write it.

## Premise findings

Unchanged from the body of this cycle's review, and all still hold. The
load-bearing one, restated because it is what authorizes the OQ3 exception:

**P11 — the write-only chain keeps the credential out of Consul-backed state —
HOLDS.** I did not take the plan's word for it. I built the chain exactly as §7
item 2 and subticket 2 specify — `ephemeral "random_password"` into
`postgresql_role.password_wo`, `vault_kv_secret_v2.data_json_wo`, and the
connection's `postgresql { password_wo, password_wo_version }`, all three
versions from one `local` — in a scratch root served from this repo's own mirror
at `deployments/applications/.terraform/providers`, pinned to vault 5.3.0,
cyrilgdn 1.26.0 and random 3.9.0. `terraform validate` returns "Success! The
configuration is valid." The schema dump confirms `random_password` as an
ephemeral resource and `write_only: true` on `postgresql_role.password_wo` and
`vault_kv_secret_v2.data_json_wo`, with `password_wo` / `password_wo_version` on
the connection's `postgresql` block. Terraform here is v1.14.3 (write-only needs
>= 1.11, ephemeral >= 1.10) and `grep -rn required_version deployments/` returns
nothing, so no version floor blocks it. `random` is absent from
`providers.tf:2-31` but pinned at `.terraform.lock.hcl:125` (3.9.0) and already
resolved implicitly by `database.tf:56`, so §6's "do not add a new provider"
still holds.

Everything else stands as recorded earlier this cycle: the anchors resolve
(`providers.tf:36` is `provider "vault" {}`;
`R3-rollout-postgres-vault-db-creds.md:411-414` is failure mode 4 and contains
the quoted sentence at `:411-413`), the eval marker names
`deployments/applications/database-secrets-poc.tf`
(`.loop/evals/S2-spike-postgres-vault-creds.md:25`), §8's cleanup runs last and
says why, §6 requirement 2 names which half of failure mode 4 the spike settles
and which half R3 keeps, and no section implies a stateful `random_password`
anymore — every surviving mention is descriptive of today's static world or an
explicit prohibition.

## Most dangerous assumption

**P11**, and it is now verified by construction rather than by inference. If the
implementer departs from the specified chain — reaching for a plain
`random_password` because the ephemeral one is unfamiliar — the OQ3 exception to
the F5/F6 config-split invariant collapses and a `CREATEROLE` Postgres admin
lands in the Consul backend. The plan names that collapse condition itself at
`:751-755`, subticket 2 forbids the shortcut, and the `terraform state pull`
check now catches it. That is as guarded as a plan can make it.

## Required fixes

None.

## Non-blocking

- `plan:314` wraps mid-thought ("bump all three versions. Write them from" / "a
  single `local`"), a ragged edge left by the insert. Cosmetic; the lines are
  well inside 80 chars.
- P6 and P10 still cite this verdict file rather than primary evidence. The
  stale line ranges are gone, so nothing resolves to unrelated text, and both
  claims are independently checkable. Not worth another cycle.
