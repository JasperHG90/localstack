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

Why a group grants nothing on its own, and why neither `developer` nor `admin`
is a containment boundary, is
[Why the cluster roles are shaped the way they are](../explanation/cluster-roles.md).

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

Joining and leaving is
[How to join and leave the admin group](../how-to/join-and-leave-the-admin-group.md).

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

Adding a tier is [How to add an app-user tier](../how-to/add-an-app-user-tier.md).

## Which of the four to reach for

When wiring a service that logs people in through Vault, the question is "who
is allowed in", and there are four answers. They are listed in the order to try
them, and the same list appears in `oidc.tf`'s header comment and in
[How to add a service that logs people in through Vault](../how-to/add-a-vault-oidc-client.md).

1. **An existing tier group** — `developer` or `admin` — when one already
   names who should get in. You still create your own assignment.
2. **A new entry in `local.app_user_groups`** when the service needs its own
   tier. This is the branch that keeps consumers on the scaffold.
3. **No group at all**: `assignments = ["allow_all"]`, Vault's built-in, when
   the answer is "anyone who can log in". Four of the six known consumers want
   this.
4. **A service-specific group**, only when none of the three fits.
