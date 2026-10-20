---
type: spike
title: Spike seaweedfs-cutover-openviking/3
description: after the backup, restore and restart on SeaweedFS, does OpenViking serve the same tree and file contents as the step 0 baseline, and does a new write land on SeaweedFS while MinIO stays fixed?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T07:09:32+00:00'
slug: seaweedfs-cutover-openviking
n: 3
outcome_written: true
---

# Spike seaweedfs-cutover-openviking/3

after the backup, restore and restart on SeaweedFS, does OpenViking serve the same tree and file contents as the step 0 baseline, and does a new write land on SeaweedFS while MinIO stays fixed?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/ov-baseline/verify.sh
```

## Outcome

Yes. The sequence on 2026-10-20 (UTC):

- 06:40, step 0: baseline through OpenViking's API (files/snapshot.py), with a recursive listing of 53 entries (32 files, 21 dirs, 11 empty dirs) and sha256 of 25 files spread across the tree (files/listing.txt, hashes.txt, sample.txt).
- 06:43, step 1: `nomad job stop openviking`, dead at 06:43:06.
- Step 2: `nomad job periodic force backup-minio` ran child periodic-1792478586, alloc 69dd293e, exit 0 at 06:44:11. The run carried the marker flags.
- Step 3: `restore-s3` dispatched for models (b6307633, alloc a459ca59, exit 0), datalake (87619a66, alloc 93190213, exit 0) and openviking (a5f995fe, alloc 2b260d70, exit 0 at 07:02:45). An exit of 0 means the copy, `rclone check` and the one-way directory check all passed (restore-s3.hcl exit codes). models and datalake have no GCS prefix, so they exit 0 with nothing to restore. Dispatching needed `dispatch-job` in the Nomad deploy policy, which this ticket adds.
- 07:03-07:05, step 4: the applications root updated `nomad_job.openviking` to the SeaweedFS endpoint and the key at default/openviking/seaweedfs. Deployment 26432ab4 is successful.

stdout.txt shows `/ready` reports ready with `agfs` ok. The listing after the move is identical to the baseline, empty directories included, and all 25 content hashes are identical. A new directory made through the API raised SeaweedFS's openviking object count from 47,680 to 47,682, while MinIO's stayed at 45,765, the count it held since OpenViking stopped. The test directory was then deleted.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/verify.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/ov-baseline/verify.sh`, which the command used
- `files/snapshot.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/ov-baseline/snapshot.py`, which the command used
- `files/write_check.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/ov-baseline/write_check.py`, which the command used
- `files/listing.txt`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/ov-baseline/before/listing.txt`, which the command used
- `files/hashes.txt`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/ov-baseline/before/hashes.txt`, which the command used
- `files/sample.txt`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/ov-baseline/before/sample.txt`, which the command used
- `files/summary.txt`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/ov-baseline/before/summary.txt`, which the command used
