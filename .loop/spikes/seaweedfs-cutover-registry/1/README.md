---
type: spike
title: Spike seaweedfs-cutover-registry/1
description: with only per-job RegistryRole STS creds via the credential_process helper, does registry 3.1.1 on SeaweedFS 4.48 push a 110 MiB layer (multipart and UploadPartCopy) and a small one (CopyObject), serve both by digest, garbage-collect a deleted image and push again, and which minimal S3 actions does the role need
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T21:03:34+00:00'
slug: seaweedfs-cutover-registry
n: 1
outcome_written: false
---

# Spike seaweedfs-cutover-registry/1

with only per-job RegistryRole STS creds via the credential_process helper, does registry 3.1.1 on SeaweedFS 4.48 push a 110 MiB layer (multipart and UploadPartCopy) and a small one (CopyObject), serve both by digest, garbage-collect a deleted image and push again, and which minimal S3 actions does the role need

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-reg-2/spike.sh
```

## Outcome

Not written yet: `loopctl plan spike-note seaweedfs-cutover-registry 1`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-reg-2/spike.sh`, which the command used
- `files/iam.tmpl.json`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-reg-2/iam.tmpl.json`, which the command used
- `files/issuer.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-reg-2/issuer.py`, which the command used
- `files/s3.json`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-reg-2/s3.json`, which the command used
