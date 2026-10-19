---
type: spike
title: Spike seaweedfs-cutover-openviking/2
description: do OpenViking directory markers (empty dirs) survive the backup rclone sync from MinIO and the rclone copy restore into SeaweedFS 4.48, and which rclone flags keep them
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T21:09:43+00:00'
slug: seaweedfs-cutover-openviking
n: 2
outcome_written: true
---

# Spike seaweedfs-cutover-openviking/2

do OpenViking directory markers (empty dirs) survive the backup rclone sync from MinIO and the rclone copy restore into SeaweedFS 4.48, and which rclone flags keep them

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ov-2/spike.sh
```

## Outcome

OpenViking (AGFS s3fs, v0.4.17.1-9) wrote a tree to MinIO that left 6 zero-byte `/` keys, one per `mkdir`. The backup job's exact command (`rclone sync`, no flags) kept 0 of them: the local copy held 0 empty dirs, SeaweedFS got 0 markers, and `rclone check` still exited 0. OpenViking then lost all 4 empty dirs (stat NotFound, missing from ls and tree, 15 of 24 views matched), and VikingFS.mv lost them too. Non-empty dirs without a marker still worked.
With `--create-empty-src-dirs` on the backup sync and `--create-empty-src-dirs --s3-directory-markers` on the restore copy, SeaweedFS held 11 markers (one per dir, parents included). All 24 views matched and every VikingFS.mv step passed. Bucket to bucket with markers on both legs also passed 24 of 24.
So the risk is real for today's backup job, and these flags fix it. For the real GCS leg the backup needs `--create-empty-src-dirs --gcs-directory-markers`. That comes from rclone's docs: fake-gcs-server dropped `/` keys from its listings, so the GCS backend was not run, and an S3 bucket with `--s3-directory-markers` stood in for it.
Limits: a 4-file sample tree on local containers (pgsty/minio latest, not the pinned release). Prod's marker count is unknown because the env S3 key was rejected (SignatureDoesNotMatch).

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ov-2/spike.sh`, which the command used
- `files/ov_tree.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ov-2/ov_tree.py`, which the command used
- `files/keys.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ov-2/keys.py`, which the command used
