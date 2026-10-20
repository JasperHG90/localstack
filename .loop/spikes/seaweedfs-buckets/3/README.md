---
type: spike
title: Spike seaweedfs-buckets/3
description: after the playbook and the apply, does the admin key list exactly six buckets, does each user reach only its own bucket with its MinIO split, and is the backup key read-only on the four durable buckets?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T05:58:25+00:00'
slug: seaweedfs-buckets
n: 3
outcome_written: true
---

# Spike seaweedfs-buckets/3

after the playbook and the apply, does the admin key list exactly six buckets, does each user reach only its own bucket with its MinIO split, and is the backup key read-only on the four durable buckets?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/bk-verify/verify.sh
```

## Outcome

Yes. On 2026-10-20 `bootstrap/playbooks/enable_consul_secrets.yml` ran with the new `service "seaweedfs" { policy = "read" }` grant (firebat: ok=8 changed=2). Its collections were installed into the session scratchpad, not the home directory. The applications-root plan then showed 38 to add, 0 to change and 0 to destroy, all SeaweedFS resources. The apply added 38, and a second `terraform plan -detailed-exitcode` exited 0 with "No changes".

Checks (stdout.txt). The admin key lists exactly datalake, loki, models, openviking, registry and tempo. Each of the eight bucket users reads and lists its own bucket, and writes it only when it is a writer: ducklake_reader and models_reader are refused writes. Each user is refused a get and a put on another bucket. The `backup` user reads and lists all four durable buckets, is refused a write on each, and is refused on `loki`. Vault holds `default/<job>/seaweedfs` beside `default/<job>/minio` for loki, tempo, registry, openviking and backup-minio. The seed and probe objects were deleted afterwards.

Side finding: the same plan did not show `nomad_job.ov_dash` as drift, though ov-dash is stopped (`spike:seaweedfs-service/4`). An applications-root apply therefore does not start ov-dash again. `minio-removal` must run `nomad job start ov-dash` (or `nomad job run` on its jobspec).

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/verify.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/bk-verify/verify.sh`, which the command used
- `files/check.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/bk-verify/check.py`, which the command used
