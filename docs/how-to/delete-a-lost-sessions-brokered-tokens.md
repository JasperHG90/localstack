# How to delete a lost session's Nomad and Consul tokens

## Introduction

Close a lost `localstack` session from the Nomad and Consul side, when you
cannot revoke its Vault token. A session mints one Nomad `deploy` token, one
Nomad `manage` token and one Consul `deploy` token, and those services honor
them without consulting Vault.
[How to revoke a lost or stolen session](revoke-a-lost-or-stolen-session.md) is the
other route, and the one to try first.

## Prerequisites

- A Nomad management token, not root.
- `CONSUL_TOKEN` exported in your shell.
- The accessors of the lost session's Nomad and Consul tokens.

## Directions

### Step 1: Cut the mint path

**Cut the mint path, then delete the tokens** — remove the entity from the
group or disable it. Order
matters: the stolen Vault token can re-mint all three until the group
grant is gone.

### Step 2: Delete both Nomad tokens

**Then delete BOTH Nomad tokens**: `nomad acl token
delete <deploy-accessor>` and `nomad acl token delete <manage-accessor>`.
A session mints one of each, and the `manage` token is a full Nomad
management token — missing it leaves the more dangerous of the two live.
This needs a management token, not root.

### Step 3: Delete the Consul token

Then `CONSUL_HTTP_TOKEN="$CONSUL_TOKEN" consul acl token delete
-accessor-id <accessor>`. **The Consul bridge is not optional**: the CLI
reads `CONSUL_HTTP_TOKEN` and ignores `CONSUL_TOKEN`, so without it the
delete fails with an error that reads like a wrong accessor.

### Step 4: Wait out the ACL caches

**The deletes are not instant.** Consul runs `ACLTokenTTL: 30s` with
`ACLDownPolicy: extend-cache` and Nomad `ACL.TokenTTL: 30s`, both defaults. An
agent keeps honoring a deleted token until its cache expires — and Consul
keeps honoring it for as long as the ACL servers are unreachable.

## Additional resources

- [How to revoke a lost or stolen session](revoke-a-lost-or-stolen-session.md)
- [Cluster roles (explanation)](../explanation/cluster-roles.md#why-removing-someone-does-not-end-their-session)
