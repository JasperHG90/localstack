---
type: spike
title: Spike postgres-dynamic-credentials/1
description: are the S2 PoC leftovers (database/ mount, vault-dbengine-admin Postgres role, its KV entry, database-secrets-poc addresses in applications state) still live on the cluster?
tags:
- spike
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-19T06:07:19+00:00'
slug: postgres-dynamic-credentials
n: 1
outcome_written: true
---

# Spike postgres-dynamic-credentials/1

are the S2 PoC leftovers (database/ mount, vault-dbengine-admin Postgres role, its KV entry, database-secrets-poc addresses in applications state) still live on the cluster?

The command exited 126:

```
/tmp/claude-1000/-home-vscode-workspace/5b5de334-808c-4b22-977c-aa8f1886ca6d/scratchpad/spike-r3/leftovers.sh
```

## Outcome

Discarded run: the leftovers script was not executable (exit 126, `Permission denied`) because the `chmod` had been refused along with an earlier command. Nothing was checked. Rerun as spike 2.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/leftovers.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/5b5de334-808c-4b22-977c-aa8f1886ca6d/scratchpad/spike-r3/leftovers.sh`, which the command used
