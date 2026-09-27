# How to turn off Vault login MFA

## Introduction

**Delete the enforcement, not the method.** The enforcement is the only thing
that makes Vault ask. Removing it stops every challenge at once, and it takes
effect on the next login, because enforcement is read per login rather than
baked into a token.

The method and the per-person secrets survive that, which is the point: turning
MFA back on later is one apply, and nobody rescans a QR code.

## Prerequisites

- A checkout of this repo, and the `localstack` CLI for
  `eval "$(localstack env)"`.
- Or, if you cannot log in, the root token (see step 1).

## Directions

### Step 1: Delete the enforcement

Through Terraform, which leaves no drift:

```sh
# Delete the vault_identity_mfa_login_enforcement.userpass block, then:
cd deployments/infrastructure
eval "$(localstack env)"
terraform apply -var-file=./vars/prod.tfvars \
  -target=vault_identity_mfa_login_enforcement.userpass
```

Targeted, like every apply in the
[rollout](roll-out-vault-login-mfa.md). This is the recipe somebody
runs under pressure, and an untargeted apply here also restarts MinIO.

In a hurry, at the cost of drift the next apply silently reverts:

```sh
vault delete identity/mfa/login-enforcement/userpass-totp
```

**If you cannot log in to do it.** A lost phone with no live session is the case this has to survive. The root
token bypasses Login MFA, because it is token auth rather than a userpass
login, so the break-glass path already documented still works: SSH to firebat
and read `/opt/vault/init.json`, or run `localstack breakglass` for the
runbook. Then run the `vault delete` above with that token.

[`localstack breakglass`](../reference/cli-breakglass.md) is the long form. Nothing about MFA changes it.

### Step 2: Confirm no enforcement is left

Confirm either way with `just mfa_status`, which should report `(none)` under
login enforcements.

## Additional resources

- [How to remove Vault login MFA completely](remove-vault-login-mfa.md)
- [Vault login MFA](../reference/vault-login-mfa.md)
