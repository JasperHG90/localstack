---
type: spike
title: Spike seaweedfs-workload-identity/6
description: 'live on the cluster: did wi-probe write its bucket through its role while wi-probe-other was refused it, and do the admin key, a static-key user and a clean applications plan still work with the IAM config loaded?'
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T06:29:52+00:00'
slug: seaweedfs-workload-identity
n: 6
outcome_written: true
---

# Spike seaweedfs-workload-identity/6

live on the cluster: did wi-probe write its bucket through its role while wi-probe-other was refused it, and do the admin key, a static-key user and a clean applications plan still work with the IAM config loaded?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/wi-verify/verify.sh
```

## Outcome

Yes. On 2026-10-20 the infrastructure root applied the STS signing key (`default/seaweedfs/sts`) and the `seaweedfs` job with `-s3.iam.config`, with a temporary `"wi-probe" = "wi-probe"` entry in `local.seaweedfs_keyless_jobs` (2 added, 1 changed). The admin key made a throwaway bucket `wi-probe`. Two throwaway batch jobs (files/wi-probe.nomad.hcl, files/wi-probe-other.nomad.hcl) each carried a `seaweedfs`-audience identity and called STS for `arn:aws:iam::role/wi-probe`. Their alloc exit codes are the result, because the operator token cannot read alloc logs. wi-probe alloc 27b36488 exited 0: STS 200, then a signed PUT of `from-wi-probe` returned 200. wi-probe-other alloc cdb1b46c exited 0, which means STS answered 403 for that role.

Earlier runs failed for probe-script reasons only. The Nomad client re-parses task config, so `curl -w '%%{http_code}'` became a template directive (allocs c0229d68 and c10632a4), and a broken PUT status parse made alloc d90bf872 exit 3 after STS had returned 200.

This run (stdout.txt): the admin key reads back `from-wi-probe` = "written by wi-probe" as the only object in `wi-probe`. The static `loki` key from `seaweedfs-buckets` still writes and reads its own bucket and gets AccessDenied on `tempo`. The applications-root plan reports no changes, with the IAM config loaded.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/verify.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/wi-verify/verify.sh`, which the command used
- `files/check.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/wi-verify/check.py`, which the command used
- `files/wi-probe.nomad.hcl`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/wi-verify/wi-probe.nomad.hcl`, which the command used
- `files/wi-probe-other.nomad.hcl`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/wi-verify/wi-probe-other.nomad.hcl`, which the command used
