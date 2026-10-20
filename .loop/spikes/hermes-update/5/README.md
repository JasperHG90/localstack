---
type: spike
title: Spike hermes-update/5
description: after the upgrade, is hermes 0.22.2-1 healthy under its memory cap with the openviking provider active, does a search through the sidecar work, and do the cron jobs exist unpinned with the forced runs ok?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T11:11:00+00:00'
slug: hermes-update
n: 5
outcome_written: true
---

# Spike hermes-update/5

after the upgrade, is hermes 0.22.2-1 healthy under its memory cap with the openviking provider active, does a search through the sidecar work, and do the cron jobs exist unpinned with the forced runs ok?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/hm-verify/verify.sh
```

## Outcome

Void runs: the in-container checks printed nothing (spike 4: `podman exec` without `-i` ignored the piped script) or broke on Python quoting (spike 5), and the memory pattern missed. Superseded by `spike:hermes-update/6`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/verify.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/hm-verify/verify.sh`, which the command used
