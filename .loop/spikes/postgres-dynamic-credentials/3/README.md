---
type: spike
title: Spike postgres-dynamic-credentials/3
description: on cyrilgdn/postgresql 1.26.0 and hashicorp/vault 5.3.0, does the write-only chain (ephemeral random_password, postgresql_role password_wo, database connection password_wo, kv data_json_wo with disable_read) apply in one apply with zero copies of the password in state?
tags:
- spike
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-19T06:08:25+00:00'
slug: postgres-dynamic-credentials
n: 3
outcome_written: true
---

# Spike postgres-dynamic-credentials/3

on cyrilgdn/postgresql 1.26.0 and hashicorp/vault 5.3.0, does the write-only chain (ephemeral random_password, postgresql_role password_wo, database connection password_wo, kv data_json_wo with disable_read) apply in one apply with zero copies of the password in state?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/5b5de334-808c-4b22-977c-aa8f1886ca6d/scratchpad/spike-r3/chain.sh
```

## Outcome

Exit 0. On vault 5.3.0, postgresql 1.26.0, random 3.9.0 and Terraform 1.16.5, from a `localstack login` session, the chain validated and created all four objects in one untargeted apply: `ephemeral "random_password"`, `postgresql_role` `password_wo`, the database connection's `password_wo` (verify_connection true, so Vault logged in as the role), and `vault_kv_secret_v2` `data_json_wo` with `disable_read`. The role also accepted the password read back from KV.
The local state (10075 bytes) holds 0 copies of the password. Every password or data attribute is null or empty (`password_wo`, `password`, `data`, `data_json`, `data_json_wo`). A second plan reported `No changes`. Destroy removed the mount, the KV metadata and the Postgres role.
This rules out provider drift breaking the chain on today's pins. Settles the chain half of risk 3.
Limits: local state, not the Consul backend. A bare LOGIN role, so the `roles` versus `postgresql_grant_role` defect and ADMIN OPTION were not tested. All objects were named `spike_r3*`, not the real `postgres` mount.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/chain.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/5b5de334-808c-4b22-977c-aa8f1886ca6d/scratchpad/spike-r3/chain.sh`, which the command used
