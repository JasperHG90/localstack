---
type: spike
title: Spike seaweedfs-cutover-registry/1
description: with only per-job RegistryRole STS creds via the credential_process helper, does registry 3.1.1 on SeaweedFS 4.48 push a 110 MiB layer (multipart and UploadPartCopy) and a small one (CopyObject), serve both by digest, garbage-collect a deleted image and push again, and which minimal S3 actions does the role need
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T21:03:54+00:00'
slug: seaweedfs-cutover-registry
n: 1
outcome_written: true
---

# Spike seaweedfs-cutover-registry/1

with only per-job RegistryRole STS creds via the credential_process helper, does registry 3.1.1 on SeaweedFS 4.48 push a 110 MiB layer (multipart and UploadPartCopy) and a small one (CopyObject), serve both by digest, garbage-collect a deleted image and push again, and which minimal S3 actions does the role need

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-reg-2/spike.sh
```

## Outcome

Pushes work on SeaweedFS 4.48 (production `weed server` flags, `copy_1 = 2`, `-s3.config` admin plus `-s3.iam.config` with `defaultEffect: Deny`). Registry 3.1.1 ran with no keys, only RegistryRole STS creds from the `registry.hcl` credential_process helper with `&RoleArn=...RegistryRole&RoleSessionName=registry` added. Both phases passed: policy `s3:*` on `registry` and `registry/*`, and the narrowed list.
- Push: a 110 MiB layer committed with UploadPartCopy (stored ETag `-4`, 32 MiB copy parts) and a 1 MiB layer committed with CopyObject (`-1`). Both pulled by digest, `crane validate --remote` passed and every blob's sha256 matched. Deleting `big` by digest and running `registry garbage-collect` with the same creds exited 0. It removed 3 blobs, the big layer's objects were gone and the small one's stayed. After that, pushing big:v2 and small:v2 worked and they validated.
- Minimal policy: `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`, `s3:ListBucket`. Taking any one of those out broke the run: Get, Put or List made the push fail, and Delete made GC leave the blobs behind. Taking out `s3:ListBucketMultipartUploads`, `s3:AbortMultipartUpload` or `s3:ListMultipartUploadParts` broke nothing. SeaweedFS either does not check those names or authorizes the calls under another action, so keeping them in the policy costs nothing and matches AWS.
- Settles risk 2. Limits: fake issuer, one registry, no htpasswd or HAProxy, crane as the client. No interrupted upload was resumed and no `uploadpurging` run was tested.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-reg-2/spike.sh`, which the command used
- `files/iam.tmpl.json`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-reg-2/iam.tmpl.json`, which the command used
- `files/issuer.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-reg-2/issuer.py`, which the command used
- `files/s3.json`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-reg-2/s3.json`, which the command used
