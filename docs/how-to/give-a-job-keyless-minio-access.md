# How to give a job keyless MinIO access

## Introduction

Let a Nomad job read its bucket with no static S3 key, by trading its
Workload Identity JWT for short-lived MinIO credentials.

**To give a new job keyless access**, two things must line up. A job whose
client library does the exchange needs two more. Tempo is that case, and is
the worked example here.

Tempo is the first service to run keyless, and it never calls `curl`. Its
client library does the exchange, which takes four things rather
than two. The pattern generalizes to any minio-go-based service.

A service built on aws-sdk-go v1 takes a different route:
[How to give an aws-sdk-go v1 service keyless MinIO access](give-an-aws-sdk-go-service-keyless-minio-access.md).

## Prerequisites

- A checkout of this repo, and the job's Nomad job id.
- The job's bucket, in `deployments/applications/storage.tf`.

## Directions

### Step 1: Give the job a named identity for the minio audience

The job carries a named identity for the `minio` audience, per the
convention in [Workload identity](../explanation/workload-identity.md#one-audience-per-verifying-service-never-per-job):

```
identity {
  name        = "minio"
  aud         = ["minio"]
  file        = true
  filepath    = "secrets/nomad_minio.jwt"
  ttl         = "1h"
  change_mode = "noop"
}
```

### Step 2: Create a MinIO policy named after the job

A `minio_iam_policy` exists whose `name` is exactly the job id, scoped to
that job's bucket.

**What a missing policy looks like depends on how you reach MinIO, and
the two symptoms are opposites.** Exchanging by hand with `curl`, the
request fails before any credential is minted, with `None of the given
policies (...) are defined`.

**Through a client library the symptom depends on which route the service
takes.** On the minio-go route (tempo),
minio-go's credential chain DISCARDS the provider error and falls back to
anonymous, so the service logs a plain `Access Denied` and its requests go
out unsigned: a quiet, misleading failure. On the `credential_process`
route (loki, registry), aws-sdk-go installs a chain that ERRORS rather
than an anonymous signer, so the failure is loud and names itself:
`ProcessProviderExecutionError` when the helper exits non-zero, or
`NoCredentialProviders` when the SDK never found the helper at all.

Either way, a service that suddenly cannot read its own bucket is more
often a missing policy than a revoked permission.

Tempo's is a `minio_iam_policy` named `tempo`, in
`deployments/applications/storage.tf`.

### Step 3: Point the client library at MinIO's STS

Two environment variables on the task
(for tempo, `deployments/applications/services/tempo.hcl`):

```
AWS_WEB_IDENTITY_TOKEN_FILE = "/secrets/nomad_minio.jwt"
TEST_IAM_ENDPOINT           = "http://192.168.2.29:9000"
```

The endpoint variable is tempo's knob for minio-go's STS endpoint. **Its
scheme is load-bearing**, and deliberately unlike the schemeless
`endpoint:` the same file gives the S3 client. Omit `http://` and
minio-go makes no STS call at all: no error, no log line, just silent
anonymous access.

`AWS_ROLE_ARN` must stay UNSET. Setting it sends a `RoleArn`, which
selects role-policy mode and pins every workload on the target to one
shared policy. Unset means claim mode, which is what makes a per-job
policy work.

### Step 4: Remove every static credential

**Every static credential removed, not just the one in the config file.**
minio-go tries providers in order: static config, `EnvAWS`, `EnvMinio`,
files, and only then web identity. Six variable names have to be absent
on this route. `EnvMinio` checks `MINIO_ROOT_USER` and
`MINIO_ROOT_PASSWORD` FIRST, then `MINIO_ACCESS_KEY` and
`MINIO_SECRET_KEY`; `EnvAWS` reads `AWS_ACCESS_KEY_ID` and
`AWS_SECRET_ACCESS_KEY`. Leave any of the six set and the service keeps
using its old key while every check looks green: the job runs, the bucket
reads, nothing errors. Delete the config keys AND whatever renders those
variables.

On the `credential_process` route the set is NINE, and the ninth is the
one you are most likely to copy from tempo. See [How to give an aws-sdk-go v1 service keyless MinIO access](give-an-aws-sdk-go-service-keyless-minio-access.md).

### Step 5: Check that no static credential is left

The check that catches step 4 is `nomad job inspect <job>`: a
`template { env = true }` stanza is itself part of the submitted jobspec, so
grepping the jobspec for those names covers both the `env` block and
anything rendered from Vault. Expect no matches. A credential that is NOT an
env var escapes this check entirely: registry's used to be two YAML keys in
its rendered config, so grep the jobspec for those too.

## Additional resources

- [Workload identity](../explanation/workload-identity.md#keyless-minio-access):
  what MinIO trusts and how it decides access.
- [How to exchange a workload JWT for MinIO credentials](exchange-a-workload-jwt-for-minio-credentials.md)
