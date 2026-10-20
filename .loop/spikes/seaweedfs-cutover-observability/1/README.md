---
type: spike
title: Spike seaweedfs-cutover-observability/1
description: after the switch, are loki and tempo healthy and writing to SeaweedFS (counts rising), MinIO flat, Grafana querying both, and the SeaweedFS dashboard and alerts loaded?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T07:12:33+00:00'
slug: seaweedfs-cutover-observability
n: 1
outcome_written: true
---

# Spike seaweedfs-cutover-observability/1

after the switch, are loki and tempo healthy and writing to SeaweedFS (counts rising), MinIO flat, Grafana querying both, and the SeaweedFS dashboard and alerts loaded?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/obs-verify/verify.sh
```

## Outcome

Yes. On 2026-10-20 the applications root updated `nomad_job.loki` (06:52 UTC), checked it, then updated `nomad_job.tempo` (06:54). Both deployments are successful. The infrastructure root updated `nomad_job.grafana`, which also delivered the OpenViking alerts already committed on main but never applied.

SeaweedFS's object counts since the switch: loki 1 (06:53), 3 (06:55), 7 (07:10 and 07:12, flat within the two-minute window because Loki flushes chunks and index in batches); tempo 8 (06:55), 86 (07:10), 98 (07:12). MinIO stayed fixed: loki at 13,581 throughout, and tempo at 6,502 from 06:55 on. Tempo's last flush before the switch took it from 6,494 to 6,502. Through Grafana's datasource proxy, Loki returns 1,866 log lines for the last 10 minutes and Tempo returns 5 traces. Both ranges fall wholly after the switch. The SeaweedFS dashboard (uid localstack-seaweedfs, 12 panels) is provisioned. The SeaweedFSDown, SeaweedFSDiskError and ScrapeJobMissing rules are loaded with health=ok and state inactive.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/verify.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/obs-verify/verify.sh`, which the command used
- `files/counts.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/counts.py`, which the command used
