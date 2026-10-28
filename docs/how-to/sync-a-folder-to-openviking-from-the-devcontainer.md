---
description: "Give the devcontainer your host OpenViking login, read-only, so ovsync can sync a folder without logging in again."
stale_after: 2027-01-28
sources:
  - resource: .devcontainer/devcontainer.json
  - resource: .devcontainer/Dockerfile
---

# How to sync a folder to OpenViking from the devcontainer

## Introduction

The devcontainer ships `ovsync` and mounts your host's `~/.openviking`
read-only, so `ovsync` and `ov` use the login you already have on the host.
Set that folder up on the host once, before you build the container. The
container cannot create it or refresh the token in it, so you renew the token
on the host too.

## Prerequisites

- `ov` and `ovx` installed on the host, with an ovx profile `localstack`. See
  the [ovx README](https://github.com/JasperHG90/openviking_extensions/tree/ovx-v0.4.0/packages/ovx).
- `VAULT_ADDR` set on the host, for `ovx -L`. See
  [How to log in to Vault](log-in-to-vault.md).

## Directions

### Step 1: Bind your login on the host

On the host, not in the container:

```console
$ ovx -L --bind localstack
```

`ovx` mints a Vault identity token and writes it to
`~/.openviking/ovcli.conf`. The file holds the token in the clear, and `ovx`
says so.

### Step 2: Set the display language on the host

```console
$ ov language en
```

This writes `~/.openviking/ovcli.settings.conf`. Without it, `ov` refuses
every command with "needs a display language", and the container cannot write
the file for you.

### Step 3: Rebuild the devcontainer

In VS Code, run **Dev Containers: Rebuild Container**. Creating the container
fails if `~/.openviking` does not exist on the host, so finish step 1 first.

### Step 4: Sync a folder

In the container:

```console
$ ovsync init <folder>
$ ovsync run <folder> --create-root
```

`ovsync init` writes a starter `ov-sync.toml` into the folder. Set its root
URI before the first run. `ovsync run` should exit 0 with no 401 or
connection error.

### Step 5: Renew the token on the host

When `ovsync` starts failing with 401, run step 1 again on the host. The
container sees the new token at once.

Inside the container, log in only with `ovx -L --no-bind`. Plain `ovx -L`
there tries to rewrite the read-only `~/.openviking` and exits with an error.

## Additional resources

- [How to call OpenViking from the CLI](call-openviking-from-the-cli.md)
- [OpenViking](../reference/openviking.md)
- [OpenViking identity](../explanation/openviking-identity.md)
