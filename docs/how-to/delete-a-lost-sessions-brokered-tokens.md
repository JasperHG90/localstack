---
description: Close a lost localstack session by deleting its brokered Nomad and Consul tokens when its Vault token cannot be revoked.
stale_after: 2027-01-19
sources:
  - resource: cli/src/localstack_cli/auth/broker.py
  - resource: deployments/infrastructure/identity.tf
  - resource: deployments/infrastructure/machine_roles.tf
  - resource: bootstrap/roles/consul_client/templates/consul.hcl.j2
---

# How to delete a lost session's Nomad and Consul tokens

## Introduction

Close a lost `localstack` session from the Nomad and Consul side, when you
cannot revoke its Vault token. A session mints one Nomad `deploy` token, one
Nomad `manage` token and one Consul `deploy` token, and those services honor
them without consulting Vault.
[How to revoke a lost or stolen session](revoke-a-lost-or-stolen-session.md) is the
other route, and the one to try first.

## Prerequisites

- A Nomad management token, for example from `vault read nomad/creds/manage`.
  The bootstrap token is not needed.
- `CONSUL_TOKEN` exported in your shell.
- The accessors of the lost session's Nomad and Consul tokens.

## Directions

### Step 1: Cut the mint path

**Cut the mint path, then delete the tokens.** Disable the session holder's
Vault entity, or remove it from the `developer` group, whose policy grants
`nomad/creds/deploy`, `nomad/creds/manage` and `consul/creds/deploy`. Order
matters: the stolen Vault token can re-mint all three until that grant is
gone.

### Step 2: Delete both Nomad tokens

**Then delete BOTH Nomad tokens**: `nomad acl token
delete <deploy-accessor>` and `nomad acl token delete <manage-accessor>`.
A session mints one of each, and the `manage` token is a full Nomad
management token. Missing it leaves the more dangerous of the two live.

### Step 3: Delete the Consul token

Then `CONSUL_HTTP_TOKEN="$CONSUL_TOKEN" consul acl token delete
-accessor-id <accessor>`. **The Consul bridge is not optional**: the CLI
reads `CONSUL_HTTP_TOKEN` and ignores `CONSUL_TOKEN`, so without it the
delete fails with an error that reads like a wrong accessor.

### Step 4: Wait out the ACL caches

**The deletes are not instant.** Consul and Nomad both cache a resolved
token for 30 seconds, their default token TTL, so an agent keeps honoring a
deleted token until its cache expires. Wait a minute before you treat the
session as closed. The Consul client agents set `down_policy = "deny"`, so
while they cannot reach the servers they refuse every token rather than keep
honoring a deleted one.

## Additional resources

- [How to revoke a lost or stolen session](revoke-a-lost-or-stolen-session.md)
- [Cluster roles (explanation)](../explanation/cluster-roles.md#why-removing-someone-does-not-end-their-session)
