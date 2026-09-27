# How to call OpenViking from the CLI

## Introduction

This gets you an authenticated call to the OpenViking API from a shell.

Both the CLI and an agent authenticate with a Vault identity token, and both
use `openviking-api.lab.orangecluster.nl`, which is an HAProxy route straight
to port 1933. That hostname is not unguarded: OpenViking answers 401 there
without a token, on the REST API and on `/mcp`.

## Prerequisites

- A Vault userpass login whose entity carries `ov_account` and `ov_user`, see
  [OpenViking](../reference/openviking.md#authentication-vault-is-the-identity).
- The `vault` CLI and `curl`.

## Directions

### Step 1: Log in to Vault

```console
$ vault login -method=userpass username=jasper
```

### Step 2: Mint an identity token

```console
$ export OV_URL=https://openviking-api.lab.orangecluster.nl
$ export OV_TOKEN=$(vault read -field=token identity/oidc/token/openviking)
```

The Vault login lasts as long as its token renews; the identity token expires
in 30 days and is re-minted by reading that path again, with no browser.

### Step 3: Call the API with the token

```console
$ curl -H "Authorization: Bearer $OV_TOKEN" "$OV_URL/api/v1/fs/ls?uri=viking://"
```

Send it as `Authorization: Bearer`, or in `X-API-Key`, which upstream also
accepts for anything shaped like a JWT.

`ovx` wraps this so nothing lands in `~/.openviking/ovcli.conf`. That matters
because `ov config add` writes whatever it is given to disk in the clear:
`--api-key-env` resolves the variable at write time rather than holding an
indirection, so it stores the literal value exactly as `--api-key-stdin` does.
Measured by writing a config both ways and grepping the result.

## Additional resources

- [OpenViking](../reference/openviking.md)
- [OpenViking identity](../explanation/openviking-identity.md)
- [How to connect Claude Code to OpenViking](connect-claude-code-to-openviking.md)
