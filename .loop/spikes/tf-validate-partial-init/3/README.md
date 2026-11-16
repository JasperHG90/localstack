---
type: spike
title: Spike tf-validate-partial-init/3
description: with providers missing from .terraform, does offline terraform validate fail with a provider message, and does init -backend=false heal the root while keeping its Consul backend record?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T14:55:11+00:00'
slug: tf-validate-partial-init
n: 3
outcome_written: true
---

# Spike tf-validate-partial-init/3

with providers missing from .terraform, does offline terraform validate fail with a provider message, and does init -backend=false heal the root while keeping its Consul backend record?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/216b2a69-4889-47a5-b777-58ba4df6cd29/scratchpad/spike-tfv2/probe.sh
```

## Outcome

Offline `terraform validate` (Terraform 1.16.5) passed on a healthy copy of `deployments/infrastructure` with no outside connection. With one provider removed or all removed, it failed (exit 1, no network call), but printed neither "Missing required provider" nor "Required plugins are not installed". It printed "there is no package for registry.terraform.io/hashicorp/X V cached in .terraform/providers", and "missing or corrupted provider plugins:" when more than one was gone.
On a developer root whose `.terraform/terraform.tfstate` records the Consul backend, `terraform init -backend=false -input=false` did not heal it: it connected to Consul (192.168.2.30), failed exit 1 with "Error refreshing state: ... 403 ... lacks permission 'key:read'", installed nothing, and validate still failed. It left the backend record byte for byte unchanged and did not touch the lock file.
On a CI-shaped root (no backend record), the same init exited 0 with no Consul connection, and offline validate then passed.
Risk 1 holds, so it is not settled. The script must match the 1.16.5 wording ("no package for", "missing or corrupted provider plugins"). On a root that records a backend, `init -backend=false` reads remote state, so it cannot heal that root offline or without Consul read access. With a valid token it would still read Consul. Limits: one root, one machine, one Consul token that lacks read access.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/probe.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/216b2a69-4889-47a5-b777-58ba4df6cd29/scratchpad/spike-tfv2/probe.sh`, which the command used
