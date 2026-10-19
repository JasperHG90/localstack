---
description: Why OpenViking takes account and user from Vault entity metadata, what that costs, and why an agent shares its person's identity.
stale_after: 2027-01-19
sources:
  - resource: deployments/applications/services/openviking/ov.conf.json
  - resource: deployments/infrastructure/oidc.tf
  - resource: deployments/infrastructure/identity.tf
  - resource: deployments/infrastructure/variables.tf
  - resource: deployments/applications/secrets.tf
  - resource: deployments/applications/services/hermes.hcl
---

# OpenViking identity

OpenViking takes every caller's identity from a Vault-signed JWT. This page
says why the claims are shaped the way they are, what that shape costs, and
why an agent shares its person's identity. The claims, the entities and the
token itself are listed in [OpenViking](../reference/openviking.md).

## Why the claims come from entity metadata

It is deliberately not the entity name and not `sub`. `sub` is the entity UUID,
so an account mapped from it would be one account per UUID while every request
still returned 200. The entity name is wrong for a different reason: the
operator's entity is a cluster-admin identity and its OpenViking account is a
data identity, so those two names differ on purpose.

An entity carrying no `ov_account` is NOT refused, and no configuration makes
it so. Vault renders an absent metadata key as an empty string. Upstream applies
`fallback` only to a null, and its `regex` narrows a value without ever
rejecting one, because a non-match leaves the value untouched. So such a caller
resolves to an account named `""`. Measured against the deployed version.

`identity.account_id.fallback` is still explicitly `null`, because absent means
`"default"` upstream and `default` is a real account here. What actually keeps
the empty case unreachable is the ACL on the identity-token role: only the
operator and the `openviking-user` group can mint one, and Terraform sets both
metadata keys on every entity it puts in either.

## One account, one user each

Everyone shares the `lab` account and is told apart by the user inside it.
`viking://user/jasper` and `viking://user/veerle` cannot read each other,
because OpenViking isolates user scopes absolutely: measured, an ADMIN
gets 403 on another user's scope and no role grants a cross-user read.
`viking://resources` belongs to the account, so it is common to both.

That shape needs the two claims to be separate. The account is the first segment
of every stored path (`/local/<account_id>/...`) and vectors are separated by
the same value ANDed into every query, so a shared account is what puts two
people in one resource tree, and the user is what keeps their own trees apart.
Mapping both from one claim resolves to `lab/user/lab`, which does not exist.

An earlier change briefly gave each person their own account instead. It
isolated them from the shared half as well, and it migrated nothing, so the
content stayed in `lab` while the new accounts sat empty. `lab` is the live
account. The per-person ones are leftovers.

Under `oidc` every caller resolves to role USER. The plugin never consults a
role mapping and never consults `server.root_api_key`, so no admin route has a
reachable credential and nothing can create an account.

Nothing needs to. MEASURED after the switch with
`scripts/ov_identity_probe.py`: a token naming an account that was never
created returns 200 and reads an empty tree. So adding a person is a Vault
entity carrying `ov_account` and `ov_user` and nothing else, and the
provisioner that used to POST to the Admin API is gone rather than replaced.

The cost of that is a typo. A misspelled claim does not fail. It opens a new
empty account or user, and the person sees an empty tree rather than an error.

## The API keys that are left

There are none on the request path. `auth_mode` is `oidc`, so OpenViking
resolves every caller from a Vault-signed JWT and no key is accepted.

Terraform still derives the old per-user keys from a seed
(`deployments/applications/secrets.tf`) and writes them to
`default/openviking-users/*`. Nothing reads them. A client still holding one
gets a 401, logged server-side as `Invalid OIDC token: Invalid token format`.
That message misleads, and is worth knowing: an old key is
`base64url(account).base64url(user).base64url(secret)`, exactly two dots, and
upstream treats any two-dot credential as a JWT before failing to parse it.
Those warnings are stale keys being refused, not a fault.

Deleting the seed and the KV entries would turn that quiet refusal into a loud
failure at Vault. That is the better shape, and it is not done.

## What this costs

Three things, all accepted.

**No admin path.** Role is always USER, so account and user management have no
credential. The Terraform provisioner that used to create accounts is gone,
because its call could not authenticate and its failure would have failed the
whole apply.

**Web Studio is unmounted.** Its settings page could not collect a credential
anyway: upstream replaces the connection form with an unsupported-mode alert
under `oidc`, and there is nothing for it to collect because the token comes
from Vault. See
`.okf/decisions/0009-openviking-has-no-browser-surface.md`.

**Hermes needs a sidecar**, because its credential cannot live in its
environment. See the authentication section of
[OpenViking](../reference/openviking.md#authentication-vault-is-the-identity)
and the section below.

## An agent shares its principal's identity

**An agent shares its principal's identity, and that is not laziness.**
OpenViking isolates user scopes absolutely: an ADMIN gets 403 on another user's
scope, and no role grants a cross-user read. An agent given its own user
therefore cannot see the scope of the person it works for, which for an
assistant is the whole job.

So Hermes's identity-token role carries `lab`/`jasper` and its writes land in
`viking://user/jasper`, indistinguishable from jasper's own. The
`leo-consumer` job carries the same pair, because the transcripts it writes
belong to jasper. Neither holds a key, and revoking one is removing its entry
from `var.vault_openviking_workloads`
(`deployments/infrastructure/variables.tf`) rather than rotating a seed that
rotates everyone.

**Hermes reaches OpenViking through a loopback sidecar, not directly.** A
running process cannot have its environment changed, and every read of an
identity-token path mints a NEW token, so rendering one into Hermes's
environment restarted the task on every consul-template poll. Measured, it
flapped every few minutes. The sidecar reads the token from a file per request
instead, Nomad keeps that file fresh with `change_mode = "noop"`, and Hermes
holds a constant endpoint for the life of the process.

## What is not configured

No agent has its own user. Every entry in `var.vault_openviking_workloads`
writes as `lab`/`jasper`. Giving an agent its own user is changing `user` in
its entry, and that is exactly why none has one: an agent with its own user
cannot see its principal's scope at all. Which agent, if any, should hold one
is an open question. Calling OpenViking by hand is
[How to call OpenViking from the CLI](../how-to/call-openviking-from-the-cli.md).
