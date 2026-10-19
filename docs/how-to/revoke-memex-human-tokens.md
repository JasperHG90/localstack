---
description: Cut off every outstanding memex human token at once by dropping the memex client from the Vault OIDC provider.
stale_after: 2027-01-19
sources:
  - resource: deployments/infrastructure/oidc.tf
---

# How to revoke memex human tokens

## Introduction

A 30-day memex id_token is a stateless bearer. Vault cannot revoke one once
issued, so know which lever works before you need it. This page cuts off
every outstanding memex human token at once, without touching any other
OIDC client. memex's Nomad job is commented out at the moment, but its
Vault OIDC client and key are still live, so tokens it issued earlier still
verify until you do this.

## Prerequisites

- A checkout of this repo and a `localstack login` session with the
  `developer` policy, see [`localstack login`](../reference/cli-login.md).
  `just apply` loads the session's tokens itself.

## Directions

### Step 1: Remove the memex client from the provider list and apply

**The complete lever: remove the memex client from
`local.oidc_provider_client_ids` in
`deployments/infrastructure/oidc.tf` and apply.** Delete the line
`vault_identity_oidc_client.memex.client_id,`, then run `just apply` from
`deployments/infrastructure/`. That drops the `memex-human` key from the
`lab` provider's JWKS, so every outstanding memex human token fails
verification at once. It is one reversible line, and it touches no other
consumer.

**Rotating the key is NOT a lever, despite how it reads.** A rotation
promotes a new signing key, and the outgoing public key stays published in
the JWKS for `verification_ttl` (30 days), so every token it signed keeps
verifying. A rotation ends no token. Lowering the key's `verification_ttl`
does not help either: it does not re-stamp existing ring members, and Vault
refuses it outright while the client's `id_token_ttl` exceeds it.

### Step 2: Wait out memex's JWKS cache

A running memex sees the change within its JWKS cache interval (about an
hour), not instantly.

### Step 3: Restore the client once the tokens you meant to end have expired

While the client is out, nobody can log in to memex either: Vault refuses
the authorization request for a client the provider does not list. Adding
the line back and running `just apply` again publishes the key again, and
every token it signed verifies again until its own expiry. So keep the
client out until the tokens you meant to end are past their 30 days, or
accept that restoring it brings them back.

## Additional resources

- [Vault OIDC tokens](../explanation/vault-oidc-tokens.md#revoking-a-long-lived-id_token-and-what-rotation-does-not-do):
  why this lever works only for a client on its own key.
