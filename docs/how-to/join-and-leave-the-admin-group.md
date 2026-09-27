# How to join and leave the admin group

## Introduction

Join the Vault `admin` group for an incident, when `developer` refuses
legitimate work, and leave it afterward. `admin` membership is outside
Terraform, so nothing reminds you to leave.
[Cluster roles](../reference/cluster-roles.md#admin-membership-is-not-managed-by-terraform)
says why.

## Prerequisites

- A Vault login as yourself, not the root token
  ([How to log in to Vault](log-in-to-vault.md)).

## Directions

### Step 1: Read who is in the group now

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
```

### Step 2: Read your own entity id

```sh
# your own entity id. Empty means your token has no entity: the root token
# has none, so log in as yourself first.
vault read -field=entity_id auth/token/lookup-self
```

### Step 3: Join

```sh
# join: everyone currently in it, plus you.
# If the group is empty, pass your id alone, with no leading comma.
vault write identity/group/name/admin \
  member_entity_ids="<current-members>,<your-entity-id>"
```

Fields you omit are preserved, so there is no need to restate `policies` or
`type`. Measured on 2026-08-02: writing only `member_entity_ids` left
`policies ['admin']` and `type internal` untouched. What is *not* preserved is
the membership list itself, which is why joining means listing the existing
members as well as yourself.

### Step 4: Leave when the incident is over

```sh
# leave: everyone currently in it, minus you.
# `member_entity_ids=""` empties the group entirely: only correct when you
# are the last member.
vault write identity/group/name/admin \
  member_entity_ids="<current-members-without-you>"
```

## Additional resources

- [Cluster roles](../reference/cluster-roles.md)
- [How to revoke a lost or stolen session](revoke-a-lost-or-stolen-session.md)
