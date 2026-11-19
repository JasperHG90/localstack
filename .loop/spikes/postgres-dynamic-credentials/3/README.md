---
type: spike
title: Spike postgres-dynamic-credentials/3
description: on cyrilgdn/postgresql 1.26.0 and hashicorp/vault 5.3.0, does the write-only chain (ephemeral random_password, postgresql_role password_wo, database connection password_wo, kv data_json_wo with disable_read) apply in one apply with zero copies of the password in state?
tags:
- spike
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-19T06:08:12+00:00'
slug: postgres-dynamic-credentials
n: 3
outcome_written: false
---

# Spike postgres-dynamic-credentials/3

on cyrilgdn/postgresql 1.26.0 and hashicorp/vault 5.3.0, does the write-only chain (ephemeral random_password, postgresql_role password_wo, database connection password_wo, kv data_json_wo with disable_read) apply in one apply with zero copies of the password in state?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/5b5de334-808c-4b22-977c-aa8f1886ca6d/scratchpad/spike-r3/chain.sh
```

## Outcome

Not written yet: `loopctl plan spike-note postgres-dynamic-credentials 3`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/chain.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/5b5de334-808c-4b22-977c-aa8f1886ca6d/scratchpad/spike-r3/chain.sh`, which the command used
