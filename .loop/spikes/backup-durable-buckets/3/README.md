---
type: spike
title: Spike backup-durable-buckets/3
description: after the deployed run, is every MinIO object and directory in the durable buckets present in GCS at the same size?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T04:41:34+00:00'
slug: backup-durable-buckets
n: 3
outcome_written: true
---

# Spike backup-durable-buckets/3

after the deployed run, is every MinIO object and directory in the durable buckets present in GCS at the same size?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/gcs-size/verify.sh
```

## Outcome

Yes. After the deployed four-bucket backup run (allocation 8e84a792, exit 0 at 2026-10-20 04:38:21 UTC), a listing-only comparison of MinIO against `gcs:localstack-cluster-backups/minio/<bucket>/` found, for each of openviking, registry, models and datalake: 0 files missing, 0 size differences, 0 MinIO directory keys whose directory is absent in GCS. openviking: 37,137 files / 836,331,631 B on both sides; registry: 399 files / 5,340,847,012 B on both sides; models and datalake empty on both.

Object counts differ by design, not by loss. MinIO's openviking holds 8,583 zero-byte directory keys; GCS keeps a marker only for the 93 empty directories, because the sync ran onto an existing copy and directories with files need none. registry has no directory keys on MinIO but 725 markers on GCS, because it was a first copy and the marker flags wrote one per directory. A restore with `--s3-directory-markers` therefore creates 725 zero-byte `dir/` keys in SeaweedFS's registry bucket that MinIO never had: `seaweedfs-cutover-registry` must check the registry tolerates them, or restore registry without that flag.

Four openviking test files have LF or CR in their names. rclone's GCS encoding stores those characters as U+240A and U+240D; the comparison decodes them, and the s3 backend decodes them back on restore.

This stands in for the eval's "rclone size" outputs: rclone is not installed in the devcontainer, and the listing compares per key, which is stricter than totals.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/verify.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/gcs-size/verify.sh`, which the command used
- `files/compare.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/gcs-size/compare.py`, which the command used
