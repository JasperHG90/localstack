---
description: Remove Vault login MFA completely, enforcement first and then the TOTP method, without locking everyone out.
stale_after: 2027-01-19
sources:
  - resource: deployments/infrastructure/identity.tf
  - resource: scripts/vault_mfa.sh
---

# How to remove Vault login MFA completely

## Introduction

Remove both the login enforcement and the TOTP method, which drops every
enrolled secret. To stop the challenges but keep everyone enrolled, use
[How to turn off Vault login MFA](turn-off-vault-login-mfa.md) instead.

Order matters, and getting it backwards is a lockout. **Delete the enforcement
first, then the method.** An enforcement naming a method that no longer exists
has no way to be satisfied, so logins fail closed with no route back except the
root token. There is no reason to find out exactly how that presents.

## Prerequisites

- A shell that can run `just apply` in `deployments/infrastructure`.

## Directions

### Step 1: Delete both MFA blocks from Terraform

Delete the `vault_identity_mfa_totp.lab` and
`vault_identity_mfa_login_enforcement.userpass` blocks, and the comments
above them, from `deployments/infrastructure/identity.tf`.

Do not delete them with `vault delete` instead. Both blocks are declared in
Terraform, so the next apply recreates them: a new method with a new id and
no enrolled secrets, and an enforcement that names it. Nobody can complete
that challenge, so every userpass login is locked out.

### Step 2: Apply the infrastructure root

```sh
cd deployments/infrastructure
just apply
```

The plan should destroy exactly those two resources. Terraform destroys the
enforcement before the method it depends on, which is the order that avoids
the lockout. Then run `just mfa_status` from the repository root, which
should print `(none)` under both headings.

## Additional resources

- [Vault login MFA](../reference/vault-login-mfa.md)
