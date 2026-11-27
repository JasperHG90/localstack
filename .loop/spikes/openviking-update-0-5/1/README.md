---
type: spike
title: Spike openviking-update-0-5/1
description: on a 50k-row openviking_v2 context table, does the ov-postgres v0.7.0 first-boot reconcile fit the 60m healthy deadline, and does the ov-ext v0.8.0 md5 backfill leave queries and the event loop responsive on 1 CPU?
tags:
- spike
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-27T12:56:50+00:00'
slug: openviking-update-0-5
n: 1
outcome_written: false
---

# Spike openviking-update-0-5/1

on a 50k-row openviking_v2 context table, does the ov-postgres v0.7.0 first-boot reconcile fit the 60m healthy deadline, and does the ov-ext v0.8.0 md5 backfill leave queries and the event loop responsive on 1 CPU?

The command exited 0:

```
bash -c cp /home/vscode/spike-scratch/ov-boot/seed_old.py /home/vscode/spike-scratch/ov-boot/boot_new.py "$TMPDIR" 2>/dev/null; ROWS=50000 /home/vscode/spike-scratch/ov-boot/run.sh
```

## Outcome

Not written yet: `loopctl plan spike-note openviking-update-0-5 1`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/run.sh`: a copy of `/home/vscode/spike-scratch/ov-boot/run.sh`, which the command used
