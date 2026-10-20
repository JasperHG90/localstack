---
type: spike
title: Spike seaweedfs-cutover/1
description: does a registry bucket restored from MinIO through rclone into SeaweedFS still serve old images by tag and digest?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T08:09:09+00:00'
slug: seaweedfs-cutover
n: 1
outcome_written: true
---

# Spike seaweedfs-cutover/1

does a registry bucket restored from MinIO through rclone into SeaweedFS still serve old images by tag and digest?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-cutover-1/registry_restore.sh
```

## Outcome

Yes, with every mismatch explained. A per-key listing compares each durable bucket's GCS copy (gcs:localstack-cluster-backups/minio/<b>/) with SeaweedFS, one way, before `backup-minio` switches its source. A sync from a SeaweedFS bucket that lacked GCS objects would delete them from GCS.

- openviking: GCS 37,286, SeaweedFS 47,725. Nothing is missing on SeaweedFS. 5 keys differ in size, all with a SeaweedFS modtime after the restore ended (07:02:45 UTC), so OpenViking rewrote them after the move. SeaweedFS has more keys because the restore wrote a marker per directory and OpenViking keeps writing.
- registry: GCS 1,124, SeaweedFS 404. The 725 missing are exactly the zero-byte `dir/` markers deleted after the restore (`spike:seaweedfs-cutover-registry/2`). The registry never had them, and no file is missing. Nothing differs. The 5 extra SeaweedFS keys are the post-switch test push.
- models and datalake: empty on both sides.

The next backup run therefore removes only GCS's registry markers and replaces openviking's rewritten objects. No real object is lost.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/registry_restore.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-cutover-1/registry_restore.sh`, which the command used
