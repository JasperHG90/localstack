---
type: spike
title: Spike seaweedfs-service/4
description: after the targeted apply, does SeaweedFS run healthy, serve S3 with the admin key across six buckets, expose only 8333 and 9327 to the LAN, and get scraped by Prometheus, with MinIO untouched?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T05:36:28+00:00'
slug: seaweedfs-service
n: 4
outcome_written: true
---

# Spike seaweedfs-service/4

after the targeted apply, does SeaweedFS run healthy, serve S3 with the admin key across six buckets, expose only 8333 and 9327 to the LAN, and get scraped by Prometheus, with MinIO untouched?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/sw-verify/verify.sh
```

## Outcome

Yes, after one placement fix. The targeted apply (2026-10-20 05:26 UTC: the volume, the job, the firewall rule, the admin key and the Prometheus scrape; 5 added, 1 changed, 0 destroyed) registered the job, but it did not place. First the volume was not yet ready when the job was evaluated. After a forced re-evaluation, `Dimension "memory" exhausted` on orangepi4a. Dry-run `nomad job plan` runs of the live job at 448, 384, 320, 256 and 128 MB all failed, so the node had under 128 MB unreserved. It holds the worker reservation (512 MB), MinIO (2560 MB), ov-dash (512 MB) and alloy (128 MB).

Not taken: lowering MinIO's reservation (MinIO's RSS was 653 MB) would restart MinIO, and its pinned image can no longer be downloaded. Whether orangepi4a still caches that image could not be checked, because SSH to orangepi@192.168.2.29 failed host key verification (REMOTE HOST IDENTIFICATION HAS CHANGED). That is left for the operator, not bypassed. Moving ov-dash: radxa has 512 to 1024 MB free, so ov-dash there would starve the nightly backup jobs, and jetson's host already runs past its reservations (nodes/jetson-orin-nano).

Taken: `nomad job stop ov-dash` (no purge). ov-dash holds no state, so this is fully reversible. SeaweedFS placed at once (alloc a8cb9254). ov-dash stays stopped until `minio-removal` frees MinIO's 2560 MB and starts it again. An applications-root apply before then re-registers it, and it then queues without placing.

Checks (stdout.txt): the deployment is successful with 1 healthy, which needs the Consul `/healthz` check to pass. The operator's Consul token cannot read the `seaweedfs` service yet, because the `deploy` policy grant comes in `seaweedfs-buckets`. With the admin key, mb/cp/ls/rb succeeded, six buckets each took a 1 KiB write and read it back, and all were removed. From the devcontainer on the LAN, only 8333 and 9327 answer, while master, volume, filer, their gRPC ports and the S3 gRPC port 18333 are closed. Prometheus, queried through Grafana's datasource proxy because 192.168.2.47:9090 is not reachable from the devcontainer, has `up{job="seaweedfs"} = 1` and `up{job="minio"} = 1`. MinIO's alloc 4cf10997 (version 13) is unchanged since 15 days ago.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/verify.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/sw-verify/verify.sh`, which the command used
- `files/s3check.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/sw-verify/s3check.py`, which the command used
