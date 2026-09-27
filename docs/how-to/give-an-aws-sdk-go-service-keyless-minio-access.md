# How to give an aws-sdk-go v1 service keyless MinIO access

## Introduction

[Tempo's route](give-a-job-keyless-minio-access.md) needs a client library that can be pointed at MinIO's STS.
aws-sdk-go v1 cannot: it has no environment variable for a non-AWS STS
endpoint, so a service built on it would send the exchange to Amazon. loki
and registry are both in that position, and both take a second route
instead: a small helper does the exchange itself, and the SDK runs it.

The SDK invokes `credential_process`, the helper POSTs to MinIO's STS with
the JWT and no `RoleArn`, prints credentials as JSON, and the SDK re-runs it
when they expire. Claim mode resolves the policy from `nomad_job_id` exactly
as on the other route, so the MinIO side is identical.

Four things per job (steps 2 to 5), and the env vars are the ones that break everything,
loudly.

## Prerequisites

- A `minio_iam_policy` named exactly the job id, per step 2 of
  [How to give a job keyless MinIO access](give-a-job-keyless-minio-access.md).

## Directions

### Step 1: Check the image can run the helper

**This route needs the image to cooperate.** The container must ship a shell
and an HTTP client, and the task must be able to read its own JWT. loki
(`docker.io/grafana/loki:3.4.2`, built on `gcr.io/distroless/static:debug`,
whose busybox supplies both) and registry (`docker.io/library/registry:3.1.1`,
Alpine-based) qualify, and both run as root. Check a new consumer before
assuming: a `scratch` image has neither, and would need the exchange moved to
a sidecar instead.

### Step 2: Give the job a named identity for the minio audience

The named identity block, as in step 1 of
[How to give a job keyless MinIO access](give-a-job-keyless-minio-access.md), with `aud = ["minio"]`.

### Step 3: Set the three AWS SDK environment variables

**Three env vars, all required:**

```
AWS_SDK_LOAD_CONFIG = "1"
AWS_CONFIG_FILE     = "/local/aws-config"
AWS_REGION          = "us-east-1"
```

`AWS_SDK_LOAD_CONFIG` is what puts the config file on the SDK's list at
all. `AWS_CONFIG_FILE` is what says WHICH file: omit it and the SDK reads
`$HOME/.aws/config`, which does not exist in these containers, and every
request fails with `NoCredentialProviders`.

### Step 4: Add the helper and the config file that names it

Two templates: the helper at `local/minio-creds.sh` with `perms = "0755"`,
and `local/aws-config` naming it under a `[default]` profile. The template
destination is alloc-relative and `AWS_CONFIG_FILE` is the in-container
path, so they differ by a leading slash and must otherwise agree.

**The helper's contract is the SDK's, not yours.** `"Version":1` is
mandatory, stdout is capped at 8 KiB and the run at 60 seconds, it is invoked
through `sh -c`, and a non-zero exit surfaces as
`ProcessProviderExecutionError`. Print the JSON and nothing else, and fail
loudly rather than emitting a half-document: an empty field would otherwise
reach the SDK as valid JSON with blank credentials.

### Step 5: Keep nine credential names absent

**Nine names absent, not six.** The six in step 4 of
[How to give a job keyless MinIO access](give-a-job-keyless-minio-access.md), plus the legacy
`AWS_ACCESS_KEY` / `AWS_SECRET_KEY`, plus
`AWS_WEB_IDENTITY_TOKEN_FILE`. That last one is the trap: tempo SETS it,
so it is what you copy, and aws-sdk-go checks it BEFORE the shared config.
Set it here and session creation fails outright with
`WebIdentityErr: role ARN is not set`, with the helper otherwise perfect.

## Additional resources

- [Workload identity](../explanation/workload-identity.md#keyless-minio-access)
- [How to exchange a workload JWT for MinIO credentials](exchange-a-workload-jwt-for-minio-credentials.md):
  the exchange the helper automates, by hand.
