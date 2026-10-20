---
type: spike
title: Spike bifrost-update/4
description: do virtual keys made by AirHelp-OSP/bifrost 0.1.1 on Bifrost 2.0.0 still plan clean, authenticate inference and update in place after the same Postgres store is upgraded to 2.3.1?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T08:32:58+00:00'
slug: bifrost-update
n: 4
outcome_written: true
---

# Spike bifrost-update/4

do virtual keys made by AirHelp-OSP/bifrost 0.1.1 on Bifrost 2.0.0 still plan clean, authenticate inference and update in place after the same Postgres store is upgraded to 2.3.1?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-bifrost-3/vk_upgrade.sh 0.1.1 v2.0.0 v2.3.1
```

## Outcome

Provider `AirHelp-OSP/bifrost` 0.1.1 created the hermes, memex and openviking virtual keys on `maximhq/bifrost:v2.0.0` (arm64, Postgres 16 config store, `auth_config` on, `bifrost.hcl` providers). Bifrost was then replaced by v2.3.1 on the same database, which migrated it: the keys gained `config_hash`, `agent_grants` and `allow_all_providers` and kept their ids and `sk-bf-` values.
Against v2.3.1, `terraform plan -detailed-exitcode` on the 2.0.0 state exited 0 ("No changes"). All 3 keys still authenticated an embeddings call through the `embark` provider to a stub upstream (HTTP 200 each), and a bogus key got 401.
An in-place update (hermes gemini weight 1 to 2) applied, the API showed weight 2, the next plan exited 0 and the keys still returned 200.
This rules out drift, lost keys and broken auth on the 2.0.0 to 2.3.1 upgrade path for this resource shape, so the provider can stay at `~>0.1.0`. Together with spike:bifrost-update/1 it settles risk 1.
Limits: fresh database with only these 3 keys and no traffic history. The upgrade went straight from 2.0.0 to 2.3.1. Only embeddings were tested, against a stub.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/vk_upgrade.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-bifrost-3/vk_upgrade.sh`, which the command used
