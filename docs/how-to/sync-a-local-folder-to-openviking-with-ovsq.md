---
description: "Mint 15-minute S3 credentials from your Vault session and sync a local folder into viking://user/jasper/resources/local/ with ovsq."
stale_after: 2027-02-27
sources:
  - resource: cli/src/localstack_cli/commands/token.py
  - resource: cli/src/localstack_cli/auth/sts.py
  - resource: deployments/infrastructure/services.tf
  - resource: deployments/infrastructure/oidc.tf
  - resource: deployments/infrastructure/identity.tf
  - resource: deployments/applications/services.tf
---

# How to sync a local folder to OpenViking with ovsq

## Introduction

Sync a folder that no CI workflow can reach, such as notes or a repository
without the openviking-sync workflow, into
`viking://user/jasper/resources/local/<subdir>/`. `ovsq` uploads the files to
the `ov-sync` bucket under `JasperHG90/local/`, and `ov-sync-consumer` writes
them to OpenViking. The S3 credentials come from your Vault session and last
15 minutes. No S3 key is stored anywhere.

## Prerequisites

- `ovsq` on your PATH. See the
  [ovsq README](https://github.com/JasperHG90/openviking_extensions/tree/main/packages/ov-sync-queue).
- A `localstack login` session as the operator
  ([CLI login](../reference/cli-login.md)).

## Directions

### Step 1: Configure the folder

```console
$ ovsq init ~/notes
```

Edit `~/notes/ov-sync-queue.toml`:

```toml
[target]
prefix = "JasperHG90/local"
subdir = "notes"     # lands in viking://user/jasper/resources/local/notes/
source = "notes"     # names this folder's manifest
```

Give every folder its own `subdir` and `source`. Two folders that share
either overwrite or delete each other's files.

### Step 2: Load the credentials

```console
$ eval "$(localstack token s3 local-ov-sync)"
local-ov-sync credentials expire at 2026-11-27T18:15:00Z
```

The line on stderr says when they expire. `env | grep AWS_` shows
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and `AWS_SESSION_TOKEN`. A
refusal from Vault means the session is not the operator's: run
`localstack login` again.

### Step 3: Sync

```console
$ ovsq status ~/notes
$ ovsq run ~/notes
```

`ovsq run` ends with `0 failed`. A second `ovsq status` shows nothing to
upload. Add `--delete` to remove files you deleted locally.

The files appear under `viking://user/jasper/resources/local/notes/` after a
short wait, because the consumer rate-limits its writes.

### Step 4: Resume after the credentials expire

A large first sync can outlast the 15 minutes and fail with
`ExpiredToken`. Run step 2 again, then `ovsq run` again. `ovsq` keeps its
manifest after every 100 files, so it picks up where it stopped.

## Additional resources

- [Workload identity](../explanation/workload-identity.md): why SeaweedFS
  trusts a Vault identity token.
- [How to sync repository folders to the ov-sync bucket](sync-repository-folders-to-the-ov-sync-bucket.md):
  the CI route.
- [ADR 0034](../../.okf/decisions/0034-local-ovsq-syncs-use-a-keyless-operator-sts-role-not-a-static-key.md):
  why there is no static key.
