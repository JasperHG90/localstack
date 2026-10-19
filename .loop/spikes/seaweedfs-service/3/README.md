---
type: spike
title: Spike seaweedfs-service/3
description: how many SeaweedFS buckets get a first write on one weed server, which flags let six buckets and 300 MB fit, and can master, volume and filer bind loopback while S3 and metrics answer off-host
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T18:15:23+00:00'
slug: seaweedfs-service
n: 3
outcome_written: true
---

# Spike seaweedfs-service/3

how many SeaweedFS buckets get a first write on one weed server, which flags let six buckets and 300 MB fit, and can master, volume and filer bind loopback while S3 and metrics answer off-host

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-service-3/slots.sh
```

## Outcome

On `chrislusf/seaweedfs:4.48` (arm64, docker) with default flags, only 4 of 6 buckets took a first write: the master grows 7 volumes per bucket (`copy_1 = 7`), so registry, models, datalake and openviking used all 27 slots and loki and tempo got `No writable volumes and no free volumes left` (master reported Max 27, Free 0, though `-volume.max` defaults to 8). The fault is the growth count, not disk.
The working set is `weed server -ip=127.0.0.1 -ip.bind=127.0.0.1 -s3.ip.bind=0.0.0.0 -metricsIp=0.0.0.0 -metricsPort=9327 -volume.max=0 -master.volumeSizeLimitMB=1024 -master.volumePreallocate=false -s3.port.iceberg=0 -s3.port.lance=0` plus `/etc/seaweedfs/master.toml` with `[master.volume_growth] copy_1 = 2`. With it, all 6 buckets wrote and read back, 300 MiB went into registry, and the master reported 12 of 27 slots used (2 per bucket), 15 free.
Bind: master 9333/19333, volume 8080/18080 and filer 8888/18888 listened on 127.0.0.1 only, and a second container on the network reached only 8333 (S3), 9327 (metrics, 965 series) and 18333. Port 18333 is the S3 gRPC port. It follows `-s3.ip.bind`, has no bind flag of its own, and `-s3.port.grpc=-1` is fatal, so the firewall has to keep it closed.
This settles risk 3: one `weed server` holds six buckets with that flag set and file. No separate volume servers are needed. Limits: with `-volume.max=0` the slot count is free disk divided by 1 GB, measured on a host with 27 GB free, not on orangepi4a. A 5.34 GB registry needs about 6 more slots. Only 300 MiB was written, not hundreds of GB.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/slots.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-service-3/slots.sh`, which the command used
