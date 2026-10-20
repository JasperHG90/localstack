---
description: Trade a Nomad job's workload JWT for short-lived SeaweedFS credentials by hand, to prove a keyless job's role works.
stale_after: 2027-04-20
sources:
  - resource: deployments/infrastructure/services.tf
  - resource: deployments/infrastructure/services/seaweedfs.hcl
---

# How to exchange a workload JWT for SeaweedFS credentials

## Introduction

Run the STS exchange by hand from inside a keyless job's container, to prove
its role works before you look at the service's own client. It is the request
the `credential_process` helper in
[How to give an aws-sdk-go v1 service keyless SeaweedFS access](give-an-aws-sdk-go-service-keyless-seaweedfs-access.md)
sends. You can only use the job's own token: Nomad refuses to read files
under `secrets/` through `alloc fs`.

## Prerequisites

- A job with the `seaweedfs` identity and an entry in
  `local.seaweedfs_keyless_jobs`, per
  [How to give a job keyless SeaweedFS access](give-a-job-keyless-seaweedfs-access.md).
- A shell in one of its containers, from
  `nomad alloc exec -task <task> <alloc id> sh`, with `wget` or `curl`.
- `mc` in the devcontainer, for step 2.

## Directions

### Step 1: Post the JWT to SeaweedFS's STS

SeaweedFS listens on orangepi4a, `192.168.2.29:8333`:

```sh
wget -q -O - --post-data='' "http://192.168.2.29:8333/?Action=AssumeRoleWithWebIdentity\
&Version=2011-06-15&RoleArn=arn:aws:iam::role/<job>&RoleSessionName=<job>\
&WebIdentityToken=$(cat /secrets/nomad_seaweedfs.jwt)"
```

With `curl`, use `curl -sS -X POST` and the same URL. The reply is XML holding
an `<AccessKeyId>`, `<SecretAccessKey>`, `<SessionToken>` and an
`<Expiration>` one hour out. Swap in another job's `RoleArn` and SeaweedFS
returns no credentials, because the role's trust policy names a different
`nomad_job_id`.

### Step 2: List the bucket with the returned credentials

In the devcontainer, `mc` takes all three values in one URL:

```sh
MC_HOST_sts="http://<AccessKeyId>:<SecretAccessKey>:<SessionToken>@192.168.2.29:8333" \
  mc ls sts/<bucket>
```

It should list the bucket. Any other bucket returns `Access Denied`.

## Additional resources

- [Workload identity](../explanation/workload-identity.md#keyless-seaweedfs-access)
