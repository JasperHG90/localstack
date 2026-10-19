---
description: Log in to memex from a laptop as yourself through the Vault lab OIDC provider, so the memex CLI carries your own 30-day token.
stale_after: 2027-01-19
sources:
  - resource: deployments/infrastructure/oidc.tf
---

# How to log in to memex from a laptop

## Introduction

Log in to memex as yourself, through the Vault `lab` provider, so the memex
CLI on your laptop carries your own 30-day token.

## Prerequisites

- The memex CLI on the laptop whose browser you use.
- A Vault login in `app-memex-readers` or `app-memex-admins`.
- An authenticator enrolled for Vault login MFA, since the Vault page asks
  for a TOTP passcode after the password
  ([How to roll out Vault login MFA](roll-out-vault-login-mfa.md)).
- The memex OIDC `client_id`, from
  `vault read -field=client_id identity/oidc/client/memex`.

## Directions

### Step 1: Write the client config on the laptop

`memex auth login` must run where the browser is, not in a devcontainer: it
binds an ephemeral loopback port a host browser cannot reach inside a
container. Config at `~/.config/memex/config.yaml`:

```yaml
oidc:
  issuer: "https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab"
  client_id: "<the memex client_id>"
  credential: "id_token"
  scopes: ["openid", "groups"]
```

`scopes` MUST include `groups`. Vault ignores an unsupported scope rather
than erroring, so a client that omits it logs in successfully and receives a
valid token carrying no `groups` claim, which then matches no grant rule.

### Step 2: Log in

```
memex auth login
memex auth status
```

## Additional resources

- [Vault OIDC tokens](../explanation/vault-oidc-tokens.md): why the config
  sends the id_token.
- [How to verify memex OIDC](verify-memex-oidc.md): step 10 has the full
  check of a human login.
