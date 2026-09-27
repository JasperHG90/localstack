# How to get the operator password

## Introduction

`localstack login` prompts for the `operator` password. You need it once, and
the CLI cannot fetch it for you.

## Prerequisites

- A Vault token that already works, such as the root token the devcontainer
  injects.
- A password manager to keep the password in.

## Directions

### Step 1: Read the password out of band

The `operator` password lives in Vault at `secret/default/vault/operator`,
and reading it needs a Vault token, which is what login produces. So the CLI
cannot fetch the password it needs to log in. Get it out of band, once, with
a token that already works:

```sh
vault kv get -field=password secret/default/vault/operator
```

### Step 2: Store it in your password manager

Keep it in your password manager. `localstack login` prompts for it and never
stores it.

## Additional resources

- [`localstack login` reference](../reference/cli-login.md)
