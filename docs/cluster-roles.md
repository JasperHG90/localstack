# Cluster roles

Four roles. The application-user role is a per-application scaffold; memex is
its first consumer.

| Role | Defined in | What it is for |
|---|---|---|
| **Application user** | `deployments/infrastructure/identity.tf`, `local.app_user_groups` | Access to one application, at one level. |
| **Developer** | `deployments/infrastructure/identity.tf` | Everything a person does here: both Terraform roots, brokered Nomad and Consul tokens, users and groups, secrets under `default/`. |
| **Admin** | `deployments/infrastructure/identity.tf`, `vault_policy.admin` | Wildcard mode, for when `developer` refuses legitimate work. |
| **Service account** | per-service, via `jwt-nomad` workload identity | Machines. Not a human role and not managed here. |

There is no separate Deployer. Deploying is something a developer does, so the
two were collapsed on purpose.

## A group grants nothing on its own

This is the part that surprises people. Creating a `vault_identity_group` and
putting someone in it does nothing at all. A group becomes meaningful only when
something names it:

- a **Vault policy** attached to the group, which is how `developer` and
  `admin` work, or
- an **OIDC assignment** naming the group, which is how a service decides who
  may log in through Vault.

The app-user tiers carry `policies = []` deliberately. They are labels for
services to read, not Vault capabilities.

## Neither `developer` nor `admin` is a containment boundary

Say this plainly because the names imply otherwise.

`developer` can write `identity/*` and `sys/policies/acl/*`. A holder can
therefore write themselves a new policy and attach it, reaching anything short
of root in about three commands. `admin` is the same reach without the
detour.

What the roles buy is **per-person credentials that can be revoked**, and no
unseal or rekey when someone leaves. What they do not buy is isolation, and
they do not buy audit attribution either, because no audit device is enabled.

If you want a real boundary, that is a different design and a different ticket.

## `admin` membership is not managed by Terraform

`vault_identity_group.admin` sets `external_member_entity_ids = true`, so
Terraform owns the group but not who is in it. Joining and leaving is a
`vault write`, and no later `terraform apply` reverts it. Verified rather than
assumed: a member added by hand survives an apply that really writes the group,
rather than one that merely skipped the diff.

That is the right shape for a break-glass role, which people join for an hour
and leave. It has a cost:

> **Leaving yourself in `admin` after an incident is invisible to every
> `terraform plan`.** Nothing will ever tell you. Checking is a habit, not a
> gate.

To see who is in it:

```sh
vault read -field=member_entity_ids identity/group/name/admin
```

To join or leave, write the group itself. **`identity/group-member-entity-ids`
does not exist on this Vault**: it returns `unsupported path`, which is easy to
mistake for a permissions problem.

**The list is REPLACED, not appended to.** The join and leave commands below
rewrite the whole membership, so read the current list first and name everyone
who should stay. Passing `member_entity_ids=""` empties the group outright,
which is only what you want if you are its last member.

```sh
# who is in it now, comma-separated and ready to paste
vault read -field=member_entity_ids -format=json identity/group/name/admin \
  | python3 -c 'import sys,json; print(",".join(json.load(sys.stdin)))'

# your own entity id. Empty means your token has no entity: the root token
# has none, so log in as yourself first.
vault read -field=entity_id auth/token/lookup-self

# join: everyone currently in it, plus you.
# If the group is empty, pass your id alone, with no leading comma.
vault write identity/group/name/admin \
  member_entity_ids="<current-members>,<your-entity-id>"

# leave: everyone currently in it, minus you.
# `member_entity_ids=""` empties the group entirely: only correct when you
# are the last member.
vault write identity/group/name/admin \
  member_entity_ids="<current-members-without-you>"
```

Fields you omit are preserved, so there is no need to restate `policies` or
`type`. Measured on 2026-08-02: writing only `member_entity_ids` left
`policies ['admin']` and `type internal` untouched. What is *not* preserved is
the membership list itself, which is why joining means listing the existing
members as well as yourself.

The app-user tiers are the opposite on purpose. They do **not** set the flag,
so `member_entity_ids` on the resource is authoritative and a hand-added member
shows up as a diff on the next plan and is reverted. A tier list should be
reviewable in the repo. `admin` is the deliberate exception.

## Naming: `app-<service>-<level>`

Documented, not enforced. Nothing validates it.

Whether a level is per-app or per-resource is the consumer ticket's call.
Services express levels differently, and only the consumer knows its own
constraint: MinIO thinks in bucket policies, Grafana in org roles. Forcing
one shape here would be guessing on their behalf.

## Adding a tier

Add an entry to `local.app_user_groups` in `identity.tf`:

```hcl
locals {
  app_user_groups = {
    "app-minio-readers" = "Read-only access to MinIO buckets"
  }
}
```

Then name it from your own `vault_identity_oidc_assignment`, binding **only
your own key**:

```hcl
group_ids = [local.app_user_group_ids["app-minio-readers"]]
```

`local.app_user_group_ids` is keyed by group name for exactly this reason. Do
not bind every value: with one tier that happens to be correct, and with two it
silently admits the other consumer's members to your client, with nothing
changing in your own file to show it.

Adding a **person** to a tier is an edit to `local.app_user_group_members`,
the map beside `local.app_user_groups`:

```hcl
locals {
  app_user_group_members = {
    "app-minio-readers" = [vault_identity_entity.operator.id]
  }
}
```

It is wired to `member_entity_ids` on `vault_identity_group.app_user` with a
`lookup(..., each.key, [])`, so a tier with no key here lands empty, which is
a valid resting state. Membership is therefore a pull request. That is
intended.

`member_entity_ids` is authoritative, not additive: whatever the map says
replaces the group's membership, so a member added by hand shows as a diff on
the next plan and is reverted.

## Which of the four to reach for

When wiring a service that logs people in through Vault, the question is "who
is allowed in", and there are four answers. They are listed in the order to try
them, and the same list appears in `oidc.tf`'s header comment and in the
"Adding a service" section of `docs/vault-human-auth.md`.

1. **An existing tier group** — `developer` or `admin` — when one already
   names who should get in. You still create your own assignment.
2. **A new entry in `local.app_user_groups`** when the service needs its own
   tier. This is the branch that keeps consumers on the scaffold.
3. **No group at all**: `assignments = ["allow_all"]`, Vault's built-in, when
   the answer is "anyone who can log in". Four of the six known consumers want
   this.
4. **A service-specific group**, only when none of the three fits.
