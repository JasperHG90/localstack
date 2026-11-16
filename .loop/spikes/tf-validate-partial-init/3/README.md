---
type: spike
title: Spike tf-validate-partial-init/3
description: with providers missing from .terraform, does offline terraform validate fail with a provider message, and does init -backend=false heal the root while keeping its Consul backend record?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T14:54:50+00:00'
slug: tf-validate-partial-init
n: 3
outcome_written: false
---

# Spike tf-validate-partial-init/3

with providers missing from .terraform, does offline terraform validate fail with a provider message, and does init -backend=false heal the root while keeping its Consul backend record?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/216b2a69-4889-47a5-b777-58ba4df6cd29/scratchpad/spike-tfv2/probe.sh
```

## Outcome

Not written yet: `loopctl plan spike-note tf-validate-partial-init 3`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/probe.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/216b2a69-4889-47a5-b777-58ba4df6cd29/scratchpad/spike-tfv2/probe.sh`, which the command used
