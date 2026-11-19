---
type: spike
title: Spike postgres-dynamic-credentials/2
description: are the S2 PoC leftovers (database/ mount, vault-dbengine-admin Postgres role, its KV entry, database-secrets-poc addresses in applications state) still live on the cluster?
tags:
- spike
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-19T06:07:18+00:00'
slug: postgres-dynamic-credentials
n: 2
outcome_written: true
---

# Spike postgres-dynamic-credentials/2

are the S2 PoC leftovers (database/ mount, vault-dbengine-admin Postgres role, its KV entry, database-secrets-poc addresses in applications state) still live on the cluster?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/5b5de334-808c-4b22-977c-aa8f1886ca6d/scratchpad/spike-r3/leftovers.sh
```

## Outcome

Exit 1 because one leftover remains: KV metadata at `secret/default/postgres/vault-dbengine-admin` still exists, version 1 live (not deleted or destroyed), version 2 soft-deleted 2026-08-09. It holds the old S2 admin password for a role that no longer exists.
Everything else is gone: the only `database`-type mount is `redis/` (no `database/`), Postgres has no `vault-dbengine-admin` role and no `v-*` minted roles, and `terraform state list` on applications (134 addresses, read-only) has no s2_poc, `vault_mount.database`, `postgres_poc` or database-engine address.
The leftover does not block an apply: a `vault_kv_secret_v2` at that path writes version 3 over it, and the role name and the `postgres` mount are free. It is a stale CREATEROLE-era secret, so O2 should destroy its metadata (`vault kv metadata delete -mount=secret default/postgres/vault-dbengine-admin`) or knowingly write over it.
Settles the collision half of risk 3: no collision that stops the build. The cleanup is an operator action and this spike did not do it.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/leftovers.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/5b5de334-808c-4b22-977c-aa8f1886ca6d/scratchpad/spike-r3/leftovers.sh`, which the command used
