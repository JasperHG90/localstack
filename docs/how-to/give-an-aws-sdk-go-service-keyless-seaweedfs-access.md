---
description: Give an aws-sdk-go v1 service keyless SeaweedFS access through a credential_process helper, as loki and the registry do.
stale_after: 2027-04-20
sources:
  - resource: deployments/infrastructure/services.tf
  - resource: deployments/applications/services.tf
  - resource: deployments/applications/services/loki.hcl
  - resource: deployments/applications/services/registry.hcl
---

# How to give an aws-sdk-go v1 service keyless SeaweedFS access

## Introduction

aws-sdk-go v1 cannot be pointed at a non-AWS STS, so a service built on it
cannot do the exchange the way tempo does. Instead a small helper script trades
the job's Workload Identity JWT at SeaweedFS's STS and prints credentials as
JSON, and the SDK runs it through `credential_process` and re-runs it when they
expire. Loki and the OCI registry work this way.

For a service built on minio-go, use
[How to give a job keyless SeaweedFS access](give-a-job-keyless-seaweedfs-access.md).

## Prerequisites

- A checkout of this repo and the `localstack` CLI, for
  `eval "$(localstack env)"`.
- The job's Nomad job id. The job runs in the `default` namespace.
- The job's bucket in `local.buckets` in
  `deployments/applications/storage.tf`, applied.

## Directions

### Step 1: Check the image can run the helper

The container needs a shell and an HTTP client. Loki
(`docker.io/grafana/loki:3.4.2`, whose busybox has `sh` and `wget`) and the
registry (`docker.io/library/registry:3.1.1`, Alpine) both have them, and both
run as root, which lets the task read its own JWT. A `scratch` image has
neither, and would need the exchange moved to a sidecar.

### Step 2: Add a role for the job

Add the job to `local.seaweedfs_keyless_jobs` in
`deployments/infrastructure/services.tf`, keyed by job id with its bucket as
the value, as in step 1 of
[How to give a job keyless SeaweedFS access](give-a-job-keyless-seaweedfs-access.md).
That renders the role `arn:aws:iam::role/<job>`, which only this job can
assume.

### Step 3: Apply the infrastructure root

```sh
cd deployments/infrastructure
eval "$(localstack env)"
terraform apply -var-file=./vars/prod.tfvars -target=nomad_job.seaweedfs
```

SeaweedFS reads its IAM config only at start, so the apply restarts it.
`nomad job status seaweedfs` should show a new allocation running.

### Step 4: Give the job a named identity for the seaweedfs audience

```hcl
identity {
  name        = "seaweedfs"
  aud         = ["seaweedfs"]
  file        = true
  filepath    = "secrets/nomad_seaweedfs.jwt"
  ttl         = "1h"
  change_mode = "noop"
}
```

### Step 5: Set the three AWS SDK environment variables

```hcl
env {
  AWS_SDK_LOAD_CONFIG = "1"
  AWS_CONFIG_FILE     = "/local/aws-config"
  AWS_REGION          = "us-east-1"
}
```

`AWS_SDK_LOAD_CONFIG` makes the SDK read a config file at all, and
`AWS_CONFIG_FILE` says which one. Omit `AWS_CONFIG_FILE` and the SDK reads
`$HOME/.aws/config`, which does not exist in these containers, and every
request fails with `NoCredentialProviders`.

Pass `s3_host` into the jobspec from the job's `nomad_job` in
`deployments/applications/services.tf`, as `nomad_job.loki` does:

```hcl
{ s3_host = data.consul_service.seaweedfs.service[0].node_address }
```

### Step 6: Add the helper and the config file that names it

Copy the two templates from `deployments/applications/services/loki.hcl`:
the helper at `local/s3-creds.sh` with `perms = "0755"`, and `local/aws-config`
holding:

```ini
[default]
credential_process = /local/s3-creds.sh
```

In the helper, change the `RoleArn` and `RoleSessionName` to the job's own:

```sh
body=$(wget -q -O - --post-data='' \
  "http://${s3_host}:8333/?Action=AssumeRoleWithWebIdentity&Version=2011-06-15&RoleArn=arn:aws:iam::role/<job>&RoleSessionName=<job>&WebIdentityToken=$${jwt}")
```

SeaweedFS refuses the exchange without both. The helper must print one JSON
document with `"Version":1` and nothing else, in under 60 seconds and 8 KiB.
A non-zero exit reaches the service as `ProcessProviderExecutionError`, so
loki's helper exits 1 rather than print a credential with an empty field.

### Step 7: Keep nine credential names absent

Remove `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `MINIO_ROOT_USER`,
`MINIO_ROOT_PASSWORD`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, the legacy
`AWS_ACCESS_KEY` and `AWS_SECRET_KEY`, and `AWS_WEB_IDENTITY_TOKEN_FILE`.

The last one is the trap, because tempo sets it and it is the one you copy.
aws-sdk-go reads it before the config file, so with it set the service fails
at start with `WebIdentityErr: role ARN is not set`, however correct the
helper is.

### Step 8: Apply the job and run the helper

```sh
cd deployments/applications
terraform apply -var-file=./vars/prod.tfvars -target=nomad_job.<job>
nomad alloc exec -task <task> <alloc id> /local/s3-creds.sh
```

The helper should print one JSON line holding `AccessKeyId`,
`SecretAccessKey`, `SessionToken` and `Expiration`.

## Additional resources

- [Workload identity](../explanation/workload-identity.md#keyless-seaweedfs-access)
- [How to exchange a workload JWT for SeaweedFS credentials](exchange-a-workload-jwt-for-seaweedfs-credentials.md):
  the exchange the helper automates, by hand.
