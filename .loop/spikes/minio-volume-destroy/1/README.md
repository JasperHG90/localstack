---
type: spike
title: Spike minio-volume-destroy/1
description: after the apply, are the minio_data volume, its host directory and every MinIO key in Vault gone, and does the infrastructure plan change nothing but the always-run firewall rules?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T09:39:12+00:00'
slug: minio-volume-destroy
n: 1
outcome_written: true
---

# Spike minio-volume-destroy/1

after the apply, are the minio_data volume, its host directory and every MinIO key in Vault gone, and does the infrastructure plan change nothing but the always-run firewall rules?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/vol-verify/verify.sh
```

## Outcome

Yes. On 2026-10-20, with the operator's approval ("Yes do it"), a targeted apply destroyed `nomad_dynamic_host_volume.minio_data` (volume cb07eebf on orangepi4a; 0 added, 0 changed, 1 destroyed, 16s). `vault kv metadata delete` purged every version of the 17 old MinIO key paths (default/minio/<user> and default/<job>/minio). stdout.txt shows Nomad lists no `minio_data`, the host directory /opt/nomad/data/host_volumes/cb07eebf-... is gone on the node, none of those Vault paths remains, and the infrastructure plan lists only the 15 `null_resource.firewall` replacements its `always_run` timestamp forces on every plan.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/verify.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/vol-verify/verify.sh`, which the command used
