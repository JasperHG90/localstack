---
description: Give a minio-go-based Nomad job keyless SeaweedFS access through a role bound to that job, with tempo as the example.
stale_after: 2027-04-20
sources:
  - resource: deployments/infrastructure/services.tf
  - resource: deployments/applications/services.tf
  - resource: deployments/applications/services/tempo.hcl
  - resource: deployments/applications/storage.tf
---

# How to give a job keyless SeaweedFS access

## Introduction

Let a Nomad job use its bucket with no static S3 key. The job trades its
Workload Identity JWT at SeaweedFS's STS for credentials that last an hour,
through a role that only that job can assume. Use this page when the job's S3
client is minio-go, which does the exchange itself. Tempo is the worked
example.

A service built on aws-sdk-go v1 needs a helper script instead:
[How to give an aws-sdk-go v1 service keyless SeaweedFS access](give-an-aws-sdk-go-service-keyless-seaweedfs-access.md).

## Prerequisites

- A checkout of this repo and the `localstack` CLI, for
  `eval "$(localstack env)"`.
- The job's Nomad job id. The job runs in the `default` namespace.
- The job's bucket in `local.buckets` in
  `deployments/applications/storage.tf`, applied.

## Directions

### Step 1: Add a role for the job

In `deployments/infrastructure/services.tf`, add the job to
`local.seaweedfs_keyless_jobs`. The key is the job id and the value is its one
bucket:

```hcl
seaweedfs_keyless_jobs = {
  tempo    = "tempo"
  loki     = "loki"
  registry = "registry"
  <job>    = "<bucket>"
}
```

The entry renders a policy that reaches only that bucket, and a role
`arn:aws:iam::role/<job>` whose trust policy requires the token's
`nomad_job_id` to equal `<job>` and its `sub` to match
`global:default:<job>:*`. No other job can assume it.

### Step 2: Apply the infrastructure root

```sh
cd deployments/infrastructure
eval "$(localstack env)"
terraform apply -var-file=./vars/prod.tfvars -target=nomad_job.seaweedfs
```

The plan changes `nomad_job.seaweedfs` in place. SeaweedFS reads its IAM
config only at start, so the apply restarts it, and every S3 client waits
while it does. `nomad job status seaweedfs` should show a new allocation
running.

### Step 3: Give the job a named identity for the seaweedfs audience

In the task, beside tempo's in `deployments/applications/services/tempo.hcl`:

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

SeaweedFS accepts only the `seaweedfs` audience. Leave the task's `user`
unset or set it to `root`: Nomad makes the JWT unreadable to a non-root user.

### Step 4: Point minio-go at SeaweedFS's STS

Pass `s3_host` into the jobspec from the job's `nomad_job` in
`deployments/applications/services.tf`, as `nomad_job.tempo` does:

```hcl
{ s3_host = data.consul_service.seaweedfs.service[0].node_address }
```

Then set three variables on the task:

```hcl
env {
  AWS_WEB_IDENTITY_TOKEN_FILE = "/secrets/nomad_seaweedfs.jwt"
  AWS_ROLE_ARN                = "arn:aws:iam::role/<job>"
  TEST_IAM_ENDPOINT           = "http://${s3_host}:8333"
}
```

Both of the following fail with no error. minio-go falls back to anonymous
S3, and SeaweedFS denies it:

- **`AWS_ROLE_ARN` is required.** minio-go sends a `RoleArn` and a
  `RoleSessionName` only when it is set, and SeaweedFS refuses an exchange
  without them.
- **`TEST_IAM_ENDPOINT` needs its `http://`.** Without the scheme minio-go
  makes no STS call at all. The S3 `endpoint` in the job's own storage config
  stays schemeless (`${s3_host}:8333`).

### Step 5: Remove every static credential

minio-go tries static config, then `AWS_ACCESS_KEY_ID` and
`AWS_SECRET_ACCESS_KEY`, then `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`,
`MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY`, then files, and web identity last.
Leave any of these set and the job keeps using that key while every check
looks green. Delete the keys from the job's config file and whatever renders
those six variables, including any template that reads the job's static key
at `default/<job>/seaweedfs`.

### Step 6: Apply the job

```sh
cd deployments/applications
eval "$(localstack env)"
terraform apply -var-file=./vars/prod.tfvars -target=nomad_job.<job>
```

The job should reach a healthy allocation. A plain `Access Denied` in its logs
means the exchange failed and minio-go fell back to anonymous S3: check steps
1, 2 and 4.

### Step 7: Check that no static credential is left

```sh
nomad job inspect <job> | grep -E 'AWS_(ACCESS_KEY_ID|SECRET_ACCESS_KEY)|MINIO_(ROOT_USER|ROOT_PASSWORD|ACCESS_KEY|SECRET_KEY)'
```

Expect no output. The submitted jobspec includes every `env` block and every
`template { env = true }`, so this covers both. A key in a rendered config
file is not an environment variable, so grep the jobspec for those config
keys too.

## Additional resources

- [Workload identity](../explanation/workload-identity.md#keyless-seaweedfs-access):
  what SeaweedFS trusts and how it binds a role to a job.
- [How to exchange a workload JWT for SeaweedFS credentials](exchange-a-workload-jwt-for-seaweedfs-credentials.md)
