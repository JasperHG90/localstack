---
type: spike
title: Spike openviking-update-0-5/2
description: on a 50k-row openviking_v2 context table, does the ov-postgres v0.7.0 first-boot reconcile fit the 60m healthy deadline, and does the ov-ext v0.8.0 md5 backfill leave queries and the event loop responsive on 1 CPU?
tags:
- spike
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-27T13:00:47+00:00'
slug: openviking-update-0-5
n: 2
outcome_written: true
---

# Spike openviking-update-0-5/2

on a 50k-row openviking_v2 context table, does the ov-postgres v0.7.0 first-boot reconcile fit the 60m healthy deadline, and does the ov-ext v0.8.0 md5 backfill leave queries and the event loop responsive on 1 CPU?

The command exited 0:

```
ROWS=50000 /home/vscode/spike-scratch/ov-boot/run.sh
```

## Outcome

On 50,000 rows (384-dim, 119 MB, seeded by ov-postgres v0.6.0 on OpenViking 0.4.17.1; Postgres limited to 1 CPU, the server process pinned to 1 core), the ov-postgres v0.7.0 / OpenViking 0.5.6 first-boot reconcile took 0.62 s. It added md5 and the ACL columns, built the ACL indexes and the guard trigger, and queued the backfill. That is far inside the 60m `healthy_deadline` in openviking.hcl.
ov-ext v0.8.0's maintenance pass then filled md5 on all 50,000 rows in 150.5 s, about 0.60 s per 200-row batch, and cleared the pending mark. While it ran, a vector query beside it in the same process stayed fast (p95 48 ms against 56 ms before, max 220 ms), and event-loop lag peaked at 77 ms, well under the 5 s alive-check timeout. The backfill also runs after `initialize`, so it does not delay the bind.
This settles risk 1: neither step needs a maintenance window or a throttle at this size.
Limits: Prometheus (192.168.2.47:9090) was not reachable from the devcontainer, so 50k rows stands in for the live count, which was not measured. Files were on a local VikingFS, so each read on live SeaweedFS costs more network wait (wait, not CPU). The extra-column move found nothing to move, as on a table written only by 0.4.17.1.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/run.sh`: a copy of `/home/vscode/spike-scratch/ov-boot/run.sh`, which the command used
- `files/seed_old.py`: a copy of `/home/vscode/spike-scratch/ov-boot/seed_old.py`, which the command used
- `files/boot_new.py`: a copy of `/home/vscode/spike-scratch/ov-boot/boot_new.py`, which the command used
