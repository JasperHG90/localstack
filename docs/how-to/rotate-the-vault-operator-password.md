# How to rotate the Vault operator password

## Introduction

Replace the operator's generated `userpass` password, for example after it
may have leaked. Terraform generates the password, so rotating it is one
targeted replace and apply.

## Prerequisites

- A checkout of this repo and Terraform.
- `CONSUL_TOKEN` exported in your shell, for the Consul state backend.
- A Vault token with the `developer` policy.

## Directions

### Step 1: Replace the password and re-apply

Replace the generated password and re-apply:

```
cd deployments/infrastructure
CONSUL_HTTP_TOKEN=${CONSUL_TOKEN} terraform apply \
  -var-file=./vars/prod.tfvars \
  -replace=random_password.operator
```

The `CONSUL_HTTP_TOKEN` prefix is required: state lives in the Consul backend,
Consul runs `default_policy = "deny"`, and the shell exports the token as
`CONSUL_TOKEN`. Every state-touching command in this repo carries it, including
every recipe in `deployments/infrastructure/justfile`.

This rewrites both the userpass user and the KV2 entry. Existing tokens keep
working until they expire, because a token is not the password.

## Additional resources

- [How to log in to Vault](log-in-to-vault.md)
- [Human login to Vault](../reference/vault-human-auth.md)
