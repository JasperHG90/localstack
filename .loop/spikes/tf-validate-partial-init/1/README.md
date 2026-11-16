---
type: spike
title: Spike tf-validate-partial-init/1
description: does terraform providers schema -json pass offline on a healthy root (no network, no backend) and fail when a provider is missing, all are gone, or one is truncated?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T14:52:38+00:00'
slug: tf-validate-partial-init
n: 1
outcome_written: true
---

# Spike tf-validate-partial-init/1

does terraform providers schema -json pass offline on a healthy root (no network, no backend) and fail when a provider is missing, all are gone, or one is truncated?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/216b2a69-4889-47a5-b777-58ba4df6cd29/scratchpad/spike-tfv/probe.sh
```

## Outcome

On a copy of `deployments/infrastructure` with every provider installed, `terraform providers schema -json` (Terraform 1.16.5) failed offline, exit 1 in 0.6 s. It tried to GET `http://192.168.2.30:8500/v1/kv/terraform/infrastructure`, which is the Consul backend recorded in `.terraform/terraform.tfstate` by an earlier full init. So on a root initialized with its backend, the command reads remote state and cannot run offline or without the backend.
With providers missing (one removed, or all removed), it failed exit 1 in under 0.5 s with "Required plugins are not installed" and made no network call. That half of the probe works.
Risk 1 holds, so it is not settled: the probe touches Consul and fails on healthy roots without it. The probe needs another shape, such as one that does not load the backend.
Limits: one root on one machine. The truncated-binary case did not run (a glob bug in the script), which does not change the verdict. A root initialized with `-backend=false` (as in CI) was not tested.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/probe.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/216b2a69-4889-47a5-b777-58ba4df6cd29/scratchpad/spike-tfv/probe.sh`, which the command used
