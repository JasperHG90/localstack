# How to add a service that logs people in through Vault

## Introduction

Register a new service as a client of Vault's `lab` OIDC provider, so people
sign in to it with their Vault login.

**Two to four resources, then one line in a shared list.** How many depends
entirely on your answer to step 3. All of them go in
`deployments/infrastructure/oidc.tf`, except a group or a new tier, which goes
in `identity.tf`.

## Prerequisites

- A checkout of this repo, and a Vault login with the `developer` policy
  ([How to log in to Vault](log-in-to-vault.md)).
- Your service's real redirect URIs.
- The roles the steps refer to: [Cluster roles](../reference/cluster-roles.md).

## Directions

### Step 1: Pick a template

Copy the smoke-test block in `oidc.tf` as
the template, and see [Cluster roles](../reference/cluster-roles.md) for the
roles it refers to.

**Nomad is the first real consumer of this provider**, so the `G2: Nomad`
section of `oidc.tf` is
worth reading as the worked example. It shows **three** of the four resources
plus the `local.oidc_provider_client_ids` line — it creates no
`vault_identity_group`, because it reuses F11's existing `developer` group
rather than inventing its own. It also shows one thing the smoke client does
not: a service whose own API needs a privileged token can broker it from Vault
rather than holding a static one. Nomad's ACL auth method and binding rule are
management-only writes, so that file adds a `vault_nomad_secret_role` with
`type = "management"` and points a second, aliased `nomad` provider at it.

### Step 2: Create the client

`vault_identity_oidc_client`, your service's client, with its real
`redirect_uris`.

### Step 3: Decide who is allowed in

**Who is allowed in.** Four answers, in the order to try them:

1. **An existing tier group** — `developer` or `admin`, both in
   `identity.tf` — when one already names who should get in.
   Create no group; you still create your own assignment in step 4.
   The `G2: Nomad` section of `oidc.tf` does this.
2. **A new entry in `local.app_user_groups`** (`identity.tf`) when the
   service needs its own tier. memex is its first consumer, so this is the
   branch that keeps app consumers on the shared scaffold rather than
   routing around it. Bind **only your own key**:
   `group_ids = [local.app_user_group_ids["<your-tier>"]]`. Binding every
   value admits the other tiers' members to your client.
   [How to add an app-user tier](add-an-app-user-tier.md) has the edit.
3. **No group and no assignment**: set `assignments = ["allow_all"]` on the
   client and skip step 4 entirely. That is Vault's built-in assignment
   (`entity_ids [*]`, `group_ids [*]`), and it is the answer when "who is
   allowed in" is "anyone who can log in". Four of the six known consumers
   declare flat access and want this.
4. **A service-specific `vault_identity_group`**, only when none of the
   three fits.

### Step 4: Bind the choice with an assignment

`vault_identity_oidc_assignment`, binding whatever step 3 chose to the
client. **Skipped under branch 3**, where you name the built-in instead.

### Step 5: Register the client against the signing key

`vault_identity_oidc_key_allowed_client_id`, which registers your client
against the signing key. This is a standalone resource on purpose, so you
do not edit the key.

### Step 6: Add the client to the provider's list

Then append your client to `local.oidc_provider_client_ids` in `oidc.tf`. That
one line is unavoidable: Vault gates the provider on its `allowed_client_ids`
and offers no standalone resource for it, unlike the key. Omit it and Vault
refuses the authorization request.

### Step 7: Request every scope the service needs

Finally, make your client **request** every scope it needs, not just read it.
Send `scope=openid` plus the scopes you want: `groups` for group names,
`email` for an email address, `openviking` for the `ov_account` and `ov_user`
pair OpenViking reads. oauth2-proxy calls this `--scope`. Only `openid`
is required, so a client that sets `--oidc-groups-claim` and leaves its
default scope alone gets a signed token with no `groups` claim, however
correct the scope template is. Nothing errors. Verified live on 2026-07-31:
with the scope requested, the decoded payload carries
`"groups": ["oidc-smoke"]`.

Which claims each scope carries, and which services read them, is in
[Human login to Vault](../reference/vault-human-auth.md#the-claims-and-which-one-your-service-reads).

### Step 8: Store the client secret

Write your client secret to KV2 under your service's own prefix. Do not put it
in a `.tf` file. Note that the `detect-private-key` pre-commit hook will NOT
catch a Vault client secret: it matches a fixed list of PEM headers, and
`hvo_secret_...` is not one of them.

**That applies to a consumer whose service reads the secret at run time,
through a `template` stanza or a config file.** If your consumer is a Terraform
resource, pass the secret by reference instead and skip KV2 entirely: Nomad's
auth method does this in `oidc.tf`, wiring
`vault_identity_oidc_client.nomad.client_secret` straight into
`config.oidc_client_secret`. Both fields are already `sensitive` in the
providers, so nothing lands in plan output, and there is no second copy of a
live secret to rotate.

## Additional resources

- [Human login to Vault](../reference/vault-human-auth.md): the issuer and
  the claims.
- [Cluster roles](../reference/cluster-roles.md): the four answers to "who is
  allowed in".
- [Vault OIDC tokens](../explanation/vault-oidc-tokens.md): the rules a
  service that verifies tokens itself, or wants long sessions, must follow.
- [How to sign in to Nomad with Vault](sign-in-to-nomad-with-vault.md)
