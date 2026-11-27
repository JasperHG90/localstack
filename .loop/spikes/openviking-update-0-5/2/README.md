---
type: spike
title: Spike openviking-update-0-5/2
description: on a 50k-row openviking_v2 context table, does the ov-postgres v0.7.0 first-boot reconcile fit the 60m healthy deadline, and does the ov-ext v0.8.0 md5 backfill leave queries and the event loop responsive on 1 CPU?
tags:
- spike
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-27T13:00:24+00:00'
slug: openviking-update-0-5
n: 2
outcome_written: false
---

# Spike openviking-update-0-5/2

on a 50k-row openviking_v2 context table, does the ov-postgres v0.7.0 first-boot reconcile fit the 60m healthy deadline, and does the ov-ext v0.8.0 md5 backfill leave queries and the event loop responsive on 1 CPU?

The command exited 0:

```
ROWS=50000 /home/vscode/spike-scratch/ov-boot/run.sh
```

## Outcome

Not written yet: `loopctl plan spike-note openviking-update-0-5 2`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/run.sh`: a copy of `/home/vscode/spike-scratch/ov-boot/run.sh`, which the command used
- `files/seed_old.py`: a copy of `/home/vscode/spike-scratch/ov-boot/seed_old.py`, which the command used
- `files/boot_new.py`: a copy of `/home/vscode/spike-scratch/ov-boot/boot_new.py`, which the command used
