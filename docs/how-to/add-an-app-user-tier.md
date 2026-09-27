# How to add an app-user tier

## Introduction

Give a service its own access level, such as `app-minio-readers`, as a Vault
group its OIDC client can admit. Use this when no existing tier names who
should get in, which is branch 2 in
[Which of the four to reach for](../reference/cluster-roles.md#which-of-the-four-to-reach-for).

## Prerequisites

- A checkout of this repo.
- A tier name that follows [the naming convention](../reference/cluster-roles.md#naming-app-service-level),
  `app-<service>-<level>`.
- Your service's `vault_identity_oidc_assignment`
  ([How to add a service that logs people in through Vault](add-a-vault-oidc-client.md)).

## Directions

### Step 1: Add the tier

Add an entry to `local.app_user_groups` in `identity.tf`:

```hcl
locals {
  app_user_groups = {
    "app-minio-readers" = "Read-only access to MinIO buckets"
  }
}
```

### Step 2: Bind only your own tier in your assignment

Then name it from your own `vault_identity_oidc_assignment`, binding **only
your own key**:

```hcl
group_ids = [local.app_user_group_ids["app-minio-readers"]]
```

`local.app_user_group_ids` is keyed by group name for exactly this reason. Do
not bind every value: with one tier that happens to be correct, and with two it
silently admits the other consumer's members to your client, with nothing
changing in your own file to show it.

### Step 3: Add people to the tier

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

## Additional resources

- [Cluster roles](../reference/cluster-roles.md)
- [How to add a service that logs people in through Vault](add-a-vault-oidc-client.md)
