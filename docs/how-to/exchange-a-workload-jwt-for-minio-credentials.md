# How to exchange a workload JWT for MinIO credentials

## Introduction

A job can exchange the JWT itself. The request carries its parameters in the
query string and needs no SDK, so `curl` is enough. Use this form to prove
the mechanism by hand from a container that has a shell. It is also, in
essence, what the [`credential_process` route](give-an-aws-sdk-go-service-keyless-minio-access.md) automates. You cannot run
it against ANOTHER job's token, because Nomad refuses to read files under
`secrets/` through `alloc fs`.

## Prerequisites

- A shell in a container of a job that carries the `minio` identity and a
  MinIO policy named after it
  ([How to give a job keyless MinIO access](give-a-job-keyless-minio-access.md)).
- `mc`, for step 2.

## Directions

### Step 1: Post the JWT to MinIO's STS

```
curl -sS -X POST "http://<minio>:9000/?Action=AssumeRoleWithWebIdentity\
&Version=2011-06-15&WebIdentityToken=$(cat /secrets/nomad_minio.jwt)"
```

It returns XML holding an `<AccessKeyId>`, `<SecretAccessKey>`,
`<SessionToken>` and an `<Expiration>` one hour out.

### Step 2: List the bucket with the returned credentials

`mc` takes all three in
one URL:

```
MC_HOST_sts="http://<AccessKeyId>:<SecretAccessKey>:<SessionToken>@<minio>:9000"
mc ls sts/<bucket>
```

## Additional resources

- [Workload identity](../explanation/workload-identity.md#keyless-minio-access)
