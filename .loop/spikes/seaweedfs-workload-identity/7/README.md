---
type: spike
title: Spike seaweedfs-workload-identity/7
description: after cleanup, is the probe role gone from the job list and the probe bucket gone, with STS still loaded and refusing a bad token?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T06:29:53+00:00'
slug: seaweedfs-workload-identity
n: 7
outcome_written: true
---

# Spike seaweedfs-workload-identity/7

after cleanup, is the probe role gone from the job list and the probe bucket gone, with STS still loaded and refusing a bad token?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/wi-clean/verify.sh
```

## Outcome

Yes. Both probe jobs were purged: `nomad job status wi-probe` and `wi-probe-other` return 404, read in the operator shell. The `wi-probe` bucket was emptied and deleted, and the `wi-probe` entry was taken out of `local.seaweedfs_keyless_jobs`. A targeted apply of `nomad_job.seaweedfs` (1 changed) redeployed the job: deployment 059d55cc is successful, with alloc b19199a4 running. stdout.txt shows the job list has no wi-probe, the admin key lists exactly the six buckets, and STS still refuses a junk token (400), so the IAM config is still loaded.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/verify.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/wi-clean/verify.sh`, which the command used
