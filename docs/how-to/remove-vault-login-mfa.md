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

- A Vault token that can write `identity/mfa/*`.

## Directions

### Step 1: Delete the enforcement first

Doing this in Terraform instead, by
deleting both blocks in one apply, is safer: Terraform destroys the enforcement
before the method it depends on. Delete both
`vault_identity_mfa_*` blocks in `identity.tf`, apply once, and skip step 2.

```sh
# enforcement first
vault delete identity/mfa/login-enforcement/userpass-totp
```

### Step 2: Delete the method

`just mfa_status` prints the method id.

```sh
# then the method, which drops every enrolled secret with it
vault delete identity/mfa/method/totp/<method-id>
```

## Additional resources

- [Vault login MFA](../reference/vault-login-mfa.md)
