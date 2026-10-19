---
description: "Replace the operator's generated Vault userpass password with one targeted Terraform apply, and read the new one."
stale_after: 2027-01-19
sources:
  - resource: deployments/infrastructure/identity.tf
  - resource: deployments/infrastructure/secrets.tf
---

# How to rotate the Vault operator password

## Introduction

Replace the operator's generated `userpass` password, for example after it
may have leaked. Terraform generates the password, so rotating it is one
targeted replace and apply.

## Prerequisites

- A checkout of this repo and Terraform.
- A `localstack login` session with the `developer` policy, see
  [How to log in to Vault](log-in-to-vault.md).

## Directions

### Step 1: Replace the password and re-apply

```sh
cd deployments/infrastructure
eval "$(localstack env)"
terraform apply -var-file=./vars/prod.tfvars \
  -replace=random_password.operator
```

`eval "$(localstack env)"` exports `CONSUL_HTTP_TOKEN` and `CONSUL_TOKEN`
along with the Vault and Nomad tokens. Terraform needs the Consul token
because state lives in the Consul backend, and Consul runs
`default_policy = "deny"`. Every recipe in
`deployments/infrastructure/justfile` runs the same `eval` first.

The plan should replace `random_password.operator` and update
`vault_generic_endpoint.operator` (the userpass user) and
`vault_kv_secret_v2.vault_operator_credentials` (the KV2 entry). Existing
tokens keep working until they expire, because a token is not the password.

### Step 2: Read the new password

```sh
vault kv get -field=password secret/default/vault/operator
```

Log in with it as in [How to log in to Vault](log-in-to-vault.md).

## Additional resources

- [How to log in to Vault](log-in-to-vault.md)
- [Human login to Vault](../reference/vault-human-auth.md)
