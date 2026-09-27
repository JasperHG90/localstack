# How to apply a backup infrastructure change

## Introduction

All GCS infrastructure for the backups (bucket, service account, IAM, key) is
managed by Terraform in `storage.tf`. Use this to apply a change to it.

## Prerequisites

- The `gcloud` CLI, with access to the GCP project named by `gcp_project`.
- A `localstack login` session, because `just apply` runs
  `localstack env`.
- `just` and Terraform, as for any apply in `deployments/infrastructure`.

## Directions

### Step 1: Authenticate with Application Default Credentials

Terraform reads Google credentials from Application Default Credentials, and
`localstack env` does not set them. Authenticate before `terraform apply`:

```bash
gcloud auth application-default login
```

That stores credentials at
`~/.config/gcloud/application_default_credentials.json`, which the Google
Terraform provider picks up automatically. On a headless machine:

```bash
gcloud auth application-default login --no-launch-browser
```

### Step 2: Apply the infrastructure root

Then apply from the infrastructure root. A checkout that has never fetched
the Google provider needs `just init` first:

```bash
cd deployments/infrastructure
just init
just apply
```

## Additional resources

- [GCS backups reference](../reference/gcs-backups.md)
