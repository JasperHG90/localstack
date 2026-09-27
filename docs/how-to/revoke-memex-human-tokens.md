# How to revoke memex human tokens

## Introduction

A 30-day id_token is a stateless bearer. Vault cannot revoke one once issued,
so know which lever actually works before you need it.

## Prerequisites

- A checkout of this repo and a Vault login with the `developer` policy.
- `CONSUL_TOKEN` exported in your shell, for the Consul state backend.

## Directions

### Step 1: Remove the memex client from the provider list and apply

**The complete lever: remove the memex client from
`local.oidc_provider_client_ids` and apply.** That drops the `memex-human`
key from the provider's JWKS, so every outstanding memex human token fails
verification at once. One reversible line, and it touches no other consumer.

**Rotating the key is NOT the complete lever, despite how it reads.**
`rotate` stamps an expiry on the CURRENT signing key only, then promotes the
next one. Keys rotated out earlier keep the expiry they were given at their
own rotation, and nothing revisits them. So repeating the call never
converges: the second call expires a freshly promoted key that signed
nothing. Its real reach is "tokens issued since the last rotation". Lowering
the key's `verification_ttl` does not help either: it does not re-stamp
existing ring members, and Vault refuses it outright while the client's
`id_token_ttl` exceeds it.

### Step 2: Wait out memex's JWKS cache

Either way the change lands within memex's JWKS cache interval (about an
hour), not instantly.

## Additional resources

- [Vault OIDC tokens](../explanation/vault-oidc-tokens.md#revoking-a-long-lived-id_token-and-what-rotation-does-not-do):
  why this lever works only for a client on its own key.
