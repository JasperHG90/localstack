---
type: spike
title: Spike seaweedfs-cutover-registry/2
description: after the backup, restore, marker removal and switch, does every pre-switch image serve unchanged by tag and digest, does a new push land on SeaweedFS, and does MinIO stay fixed?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T07:54:04+00:00'
slug: seaweedfs-cutover-registry
n: 2
outcome_written: false
---

# Spike seaweedfs-cutover-registry/2

after the backup, restore, marker removal and switch, does every pre-switch image serve unchanged by tag and digest, does a new push land on SeaweedFS, and does MinIO stay fixed?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/reg/verify.sh
```

## Outcome

Not written yet: `loopctl plan spike-note seaweedfs-cutover-registry 2`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/verify.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/reg/verify.sh`, which the command used
- `files/snapshot.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/reg/snapshot.py`, which the command used
- `files/push_check.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/reg/push_check.py`, which the command used
- `files/drop_markers.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/reg/drop_markers.py`, which the command used
- `files/before.json`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/reg/before.json`, which the command used
