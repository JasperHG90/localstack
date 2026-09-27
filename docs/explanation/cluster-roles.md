# Why the cluster roles are shaped the way they are

The roles themselves, and where each is defined, are in
[Cluster roles](../reference/cluster-roles.md). This page says what a role
buys and what it does not.

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

### It is not a security boundary, and that is deliberate

A `developer` can write `identity/*` and `sys/policies/acl/*`, so they can
grant themselves anything short of `root` in about three commands. Vault
refuses to attach the `root` policy and refuses nothing else. Developer and
Deployer are one role on this cluster by choice — there is one person, and a
boundary between "develops" and "deploys" would protect nothing while making
every task need two credentials.

So the `bootstrap` mount, `sys/audit` and the unseal surface are **outside what
the policy grants**, not outside what the holder can reach.

What the credential does buy over the root token:

- It is per-person.
- It cannot be used to unseal or rekey.

What it does **not** buy: audit attribution. **No audit device is enabled on
this cluster**, so nothing records who did what, whichever credential is used.
That is worth fixing, and is separate work.

## Why removing someone does not end their session

**Everything else is narrower than it looks.** Removing someone from the
`developer` group demotes their Vault
token to `default` on its next call, because the policy arrives through the
group at request time rather than baked into the token. But that is only the
Vault half. A `localstack` session also holds brokered Nomad and Consul
tokens (two Nomad roles, `deploy` and `manage`), which those services honor
without consulting Vault, and removing an entity from a group does not
revoke a Vault lease. Worse, the `default` policy grants `sys/leases/renew`
(measured), so a demoted holder can keep renewing all three brokered leases
up to their `max_ttl` of one hour.

**Disabling the entity does not close it either.** `vault path-help
identity/entity/id/<id>` is explicit: *"tokens tied to this identity will not
be able to be used (**but will not be revoked**)."* It stops renewal; the
brokered Nomad and Consul tokens still live out their current lease in those
services' own state.

What does close it is
[How to revoke a lost or stolen session](../how-to/revoke-a-lost-or-stolen-session.md)
and [How to delete a lost session's Nomad and Consul tokens](../how-to/delete-a-lost-sessions-brokered-tokens.md).

## Breaking glass

If Vault is sealed, down, or you have locked yourself out, a Vault policy is
worthless. SSH to firebat and read `/opt/vault/init.json` — see `localstack
breakglass` (D5) for the runbook. `developer` is for when Vault is up and your
policy is too narrow; breakglass is for when Vault will not answer.
