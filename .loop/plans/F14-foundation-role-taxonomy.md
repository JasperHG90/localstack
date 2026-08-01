---
epic = "foundation"
depends_on = ["F2-foundation-vault-oidc-provider", "F11-foundation-human-read-role"]
priority = 35
summary = "Create the `admin` group as a wildcard mode you join when `developer` is too narrow, and the scaffold that makes application-user groups a map entry. Ships no app-specific groups. Writes the four-role layout down once."
tags = ["vault", "oidc", "rbac", "taxonomy"]
---

# F14 — The role taxonomy

## Title
Create `admin` and the application-user scaffold, so the role model exists as
machinery and adding an app tier later is a map entry rather than a design
question.

## The layout

| Role | Vault | Ships in |
| --- | --- | --- |
| Application user | no policy | scaffold here, groups with each app |
| Developer | `developer` policy | `F11` |
| Admin | `path "*"` | **here** |
| Service account | per-workload | `F1`, `M1`, `R3` |

## `admin` is a mode, not a tier

**It ships with no members, and that is not a security control.** A
`developer` can add themselves in one write — measured, the next login returns
`identity_policies ['admin','developer']`. That is the intended way in; nobody
else has to grant it.

**So Terraform must not own its membership.** `vault_identity_group` manages
`member_entity_ids` authoritatively: a hand-added member shows as
`~ member_entity_ids`, and the next apply reverts it to `[]` — measured. That
would undo the documented way in, including during this ticket's own proof run.
The `admin` group therefore sets **`external_member_entity_ids = true`**, which
declares the group without owning who is in it. Requirement 2 and eval row 3
verify that a hand-added member survives an apply, rather than assuming the
flag behaves as expected.

The reason for no standing members is simpler: **Vault merges every group's
policies into every token, and re-evaluates membership per request.** Measured:
an existing token gained `sys/audit` the moment its entity joined the group and
lost it the moment it left — no re-login, no revocation. A standing `admin` membership means every
`developer` token is also an `admin` token, and `F11`'s narrow policy stops
meaning anything. You join when `developer` 403s on something legitimate —
enabling an audit device, mounting a new engine, reading the `bootstrap`
mount — and leave after. Daily tokens stay narrow, so a mistake or a leak is
bounded to `developer`.

Breakglass (`D5`) is a different failure: Vault sealed or down, where a Vault
policy is worthless. `D5` is a runbook printer and never touches credentials
(`D5:28-32`); it is not affected by this ticket.

**`admin` is not root, measured on Vault 2.0.3:**

- `vault token create -policy=root` → `400: root tokens may not be created
  without parent token being root`.
- The `default` policy **shadows** `path "*"` on every exact path it names,
  because a specific path beats a glob. `vault list sys/leases/lookup` is
  denied for `admin` and allowed for `root`, and `admin` cannot update its own
  entity (`default` grants `identity/entity/id/{{identity.entity.id}}` read
  only) while it can update anyone else's.

So the policy is `path "*"` **plus explicit blocks re-granting the paths
`default` names**. One bare `path "*"` block does not do the job.

## Non-goals
- **No app-specific groups.** No Grafana, MinIO or Memex names. The map ships
  empty; the eval adds one entry and removes it.
- **No consumer wiring.** `G1`, `G2`, `M2`, `R1`, `R4` each wire their own
  service. This ticket does not claim what any of them does.
- **No new OIDC clients.**
- `developer` (`F11`), the breakglass runbook (`D5`), service accounts (`F1`,
  `M1`, `R3`).

## Requirements
1. **`vault_policy.admin`**: `path "*"` with all capabilities including
   `sudo`, plus an explicit block for each path `default` names, so the glob is
   not shadowed. Read the live `default` policy for that list rather than
   assuming it. **Templated paths must be restated templated**: a plain
   `identity/entity/id/<uuid>` block does not beat `default`'s
   `identity/entity/id/{{identity.entity.id}}`, but the same templated string
   does — both render to the same path and Vault unions the capabilities.
   Terraform passes `{{ }}` through a `vault_policy` heredoc verbatim.
2. **`vault_identity_group.admin`** with **`external_member_entity_ids = true`**
   and no members declared. Terraform owns the group, not its membership, so
   joining and leaving is a `vault write` rather than a Terraform edit and an
   apply does not revert it. **Verify the flag actually behaves that way** —
   add a member by hand, apply, confirm it survives — rather than trusting it.
3. **A scaffold**: a locals map keyed by group name, a `for_each` over
   `vault_identity_group`, `policies = []` on every one.
4. **A marked extension-point local exposing the group ids**, in the shape of
   `local.oidc_provider_client_ids` (`oidc.tf:64`).
5. **`vault_identity_oidc_assignment.smoke.group_ids` reads that local**, which
   makes `oidc.tf` the extension point's first consumer and is the only way to
   prove the wiring — there is one client, and its `assignments` is inline at
   `oidc.tf:110`. This ticket therefore **does** edit `oidc.tf`, by that one
   line.
   **It must `concat` the local onto the existing smoke group id, not replace
   it.** The map ships empty, so a replacement writes `group_ids = []` and
   breaks F2's live smoke client.
6. **The map ships empty.** No app-specific entries.
7. **Naming is `app-<service>-<level>`, documented, not enforced.** Whether a
   level is per-app or per-resource is the consumer ticket's call, because each
   app expresses levels differently and only the consumer knows its own
   constraint. **Not because of a MinIO naming collision** — an earlier draft
   said that, and it conflated two unrelated facts: MinIO's bucket policies are
   `<bucket>_read_write` (`modules/bucket/main.tf:12`), but M2 gates on the
   per-client assignment and bypasses the claim entirely
   (`oidc.tf:36-38`, `M2:128-132`), so those names never meet a group name.
8. **For the app-user groups only, adding a person is a Terraform edit.**
   They do NOT set `external_member_entity_ids`, so
   `vault_identity_group.member_entity_ids` is authoritative there and a member
   added by hand shows as `~ member_entity_ids / 1 to change` on the next plan
   and is reverted. That is the right default for a tier list that should be
   reviewable. `admin` is the deliberate exception (Requirement 2), because its
   whole workflow is joining and leaving between applies.
9. **Prove it end to end**: add one throwaway map entry, apply, put a scratch
   entity in it, log in through the provider, **decode the token** and find the
   name in `groups` as a real array, confirm the entity reads nothing, remove
   everything. Decoding is required — a malformed template renders
   `{"groups": "null"}` and still issues a valid token.
10. **`docs/cluster-roles.md`** states the four roles, where each is defined,
    the naming convention, that a group needs an OIDC assignment to grant
    anything, and that neither `developer` nor `admin` is a containment
    boundary. It must also say that **`admin` membership is not managed by
    Terraform**, so leaving yourself in it after an incident is invisible to
    every plan — checking it is a habit, not a gate.
11. **Update `docs/vault-human-auth.md:71-87`.** Its step 2 tells every
    consumer to create its own `vault_identity_group`. With a shared taxonomy
    that is now the second answer in the repo: a consumer references tier
    groups and creates its own only when the tiers do not fit.
12. Plain language (`.claude/rules/plain-language.md`); adversarial sub-agent
    review before done (`.claude/rules/adversarial-reviews.md`).

## Code surface
- `deployments/infrastructure/roles.tf` **(new)**: `vault_policy.admin`,
  `vault_identity_group.admin`, the app-user map, the `for_each` groups, the
  marked local.
- `deployments/infrastructure/oidc.tf` **(edit, one line)**: Requirement 5.
- `docs/cluster-roles.md` **(new)**, `docs/vault-human-auth.md` **(edit)**.

## Tests & validation gates
- **Gate**: `just pre_commit` (`.loop/config.json:2-4`).
- `terraform validate` and `terraform plan` in the infrastructure root.
- `.loop/evals/F14-foundation-role-taxonomy.md`.

## Risk assessment
- **Blast radius: small.** An empty map creates nothing; the `admin` group has
  no members.
- **Reversibility: high**, except Requirement 5's `oidc.tf` line, which is
  live OIDC wiring — a wrong edit there breaks the existing smoke client.
  Verify a smoke login still works after applying it.
- **The failure that matters is a scaffold that does not work**, found by the
  first consumer months later. Requirement 9 is an end-to-end login, not a
  plan.
- **The second is `admin` gaining a standing member**, which silently makes
  `F11` meaningless. **Nothing enforces this and nothing can**, because
  `external_member_entity_ids = true` means no apply will ever clear the field.
  The eval checks the group is empty at the end of its own run; after that it is
  a convention the operator keeps, and `docs/cluster-roles.md` must say so
  rather than implying Terraform guards it.

## Open questions

**Q1. Keep `admin` at all, given breakglass exists?**
*Settled by the operator, 2026-08-01: yes, as wildcard mode.* `developer` is an
enumerated policy and will 403 on legitimate work it does not list; `admin`
covers that without SSH. Two earlier justifications were wrong and are not
reasons: it is **not** attributable, because no audit device is enabled
(`F11`), and root tokens **are** revocable without a rekey, via
`generate-root` with unseal shares.

**Q2. Per-app or per-resource levels?**
*Delegated to the consumer ticket*, which knows its app's constraint.

## Definition of Done
`admin` exists as a policy and a group with no members, and is proven not to be
root. Its membership is deliberately outside Terraform's control, so "no
members" is a state the proof leaves behind by hand, not one an apply
maintains.
The scaffold exists, ships no app-specific groups, and one throwaway entry is
carried end to end: applied, wired to the smoke assignment, logged in, decoded
out of the token, and removed. `docs/cluster-roles.md` lays out the four roles
and `docs/vault-human-auth.md` no longer gives a conflicting answer.
