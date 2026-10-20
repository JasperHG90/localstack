---
type: spike
title: Spike seaweedfs-buckets/4
description: after matching reader grants to MinIO (GetBucketLocation, GetObject), do readers still read but not list or write, writers keep full access, and the backup user still reads and lists the durable buckets?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T06:07:33+00:00'
slug: seaweedfs-buckets
n: 4
outcome_written: true
---

# Spike seaweedfs-buckets/4

after matching reader grants to MinIO (GetBucketLocation, GetObject), do readers still read but not list or write, writers keep full access, and the backup user still reads and lists the durable buckets?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/bk-verify/verify.sh
```

## Outcome

Yes. Review finding f1 said readers had s3:ListBucket, which MinIO readers lack (modules/bucket: GetBucketLocation, GetObject). After matching them to MinIO, the apply changed only the two reader policies (0 added, 2 changed, 0 destroyed), and a second plan reported no changes. Readers now read their own bucket and are refused list and write. Writers keep full access. The backup user, whose policy is the read set plus s3:ListBucket, still reads and lists all four durable buckets and is refused writes. Every user is still refused on another bucket.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/verify.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/bk-verify/verify.sh`, which the command used
- `files/check.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/bk-verify/check.py`, which the command used
