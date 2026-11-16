---
type: spike
title: Spike tf-validate-partial-init/2
description: with providers missing from .terraform, does offline terraform validate fail with a provider message, and does init -backend=false heal the root while keeping its Consul backend record?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T14:55:10+00:00'
slug: tf-validate-partial-init
n: 2
outcome_written: true
---

# Spike tf-validate-partial-init/2

with providers missing from .terraform, does offline terraform validate fail with a provider message, and does init -backend=false heal the root while keeping its Consul backend record?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/216b2a69-4889-47a5-b777-58ba4df6cd29/scratchpad/spike-tfv2/probe.sh
```

## Outcome

Not the run to cite: the healthy copy failed `terraform validate` with "no file exists at ./../../.ssh/id_rsa" (`services.tf` line 499 reads a key two directories above the root), which is an artifact of where the copy was placed. spike:tf-validate-partial-init/3 reruns this with a dummy key in place.
The provider-missing and init results matched run 3: validate printed neither expected message, and `init -backend=false` contacted Consul and failed with a 403.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/probe.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/216b2a69-4889-47a5-b777-58ba4df6cd29/scratchpad/spike-tfv2/probe.sh`, which the command used
