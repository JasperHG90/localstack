---
type: spike
title: Spike seaweedfs-cutover-openviking/3
description: after the backup, restore and restart on SeaweedFS, does OpenViking serve the same tree and file contents as the step 0 baseline, and does a new write land on SeaweedFS while MinIO stays fixed?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T07:09:18+00:00'
slug: seaweedfs-cutover-openviking
n: 3
outcome_written: false
---

# Spike seaweedfs-cutover-openviking/3

after the backup, restore and restart on SeaweedFS, does OpenViking serve the same tree and file contents as the step 0 baseline, and does a new write land on SeaweedFS while MinIO stays fixed?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/ov-baseline/verify.sh
```

## Outcome

Not written yet: `loopctl plan spike-note seaweedfs-cutover-openviking 3`.

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
