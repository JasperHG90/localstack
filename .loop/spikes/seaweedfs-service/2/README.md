---
type: spike
title: Spike seaweedfs-service/2
description: can a SeaweedFS admin S3 identity come from a static config file, drive the embedded IAM API, and coexist with API-created users across a restart
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T17:57:21+00:00'
slug: seaweedfs-service
n: 2
outcome_written: true
---

# Spike seaweedfs-service/2

can a SeaweedFS admin S3 identity come from a static config file, drive the embedded IAM API, and coexist with API-created users across a restart

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-service-2/admin_from_file.sh
```

## Outcome

On `chrislusf/seaweedfs:4.48` (arm64, docker), `weed server -dir=/data -s3 -s3.port=8333 -s3.config=/s3.json -s3.iam.readOnly=false` took an admin from a static JSON file (`identities[].credentials[].accessKey/secretKey`, `actions: [Admin, Read, Write, List, Tagging]`). That admin created a bucket and wrote an object, and a bad key got refused.
The embedded IAM API is on the S3 port. With the admin key it accepted CreateUser, CreateAccessKey and PutUserPolicy. The new user could read its bucket and got AccessDenied on CreateBucket.
After `docker restart` with the same file, the admin, the API-made user, its key and its policy all still worked, and ListUsers returned `[app, admin]`. The file does not overwrite filer-stored identities.
This settles risk 2: a Vault-rendered config file is enough, with no `weed shell` bootstrap. Limits: `-s3.iam.readOnly` defaults to true, so IAM writes need `=false`. The filer logs its IAM gRPC as unauthenticated unless `jwt.filer_signing.key` is set. STS logged "no signing key". Admin key rotation through the file and env-var credentials were not tested.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/admin_from_file.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-service-2/admin_from_file.sh`, which the command used
