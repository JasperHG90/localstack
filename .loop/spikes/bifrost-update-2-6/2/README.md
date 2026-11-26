---
type: spike
title: Spike bifrost-update-2-6/2
description: do virtual keys made by AirHelp-OSP/bifrost 0.1.1 on Bifrost 2.3.1 keep ids and values, plan clean with stable provider_configs order, authenticate inference and update in place after the same Postgres store is migrated to 2.6.0?
tags:
- spike
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-26T13:35:02+00:00'
slug: bifrost-update-2-6
n: 2
outcome_written: true
---

# Spike bifrost-update-2-6/2

do virtual keys made by AirHelp-OSP/bifrost 0.1.1 on Bifrost 2.3.1 keep ids and values, plan clean with stable provider_configs order, authenticate inference and update in place after the same Postgres store is migrated to 2.6.0?

The command exited 0:

```
/home/vscode/spike-scratch/bifrost-1/vk_upgrade.sh 0.1.1 v2.3.1 v2.6.0
```

## Outcome

Provider `AirHelp-OSP/bifrost` 0.1.1 created the four keys from `services.tf` (hermes, memex, openviking, router, same `provider_configs`) on `maximhq/bifrost:v2.3.1` (arm64, Postgres 16 store, auth on, `bifrost.hcl` providers incl. typesafe, complexity analyzer and routing rules). v2.6.0 then started on the same database, ran its config-store migrations with no error-level log lines, and served health ok.
After the upgrade the API showed the same 4 keys with identical (name, id, value) tuples, and `provider_configs` still came back in alphabetical order (embark, gemini, ollama; ollama, typesafe). `terraform plan -detailed-exitcode` on the 2.3.1 state exited 0 ("No changes").
Hermes, memex and openviking each got HTTP 200 on an embeddings call through `embark` to a stub. The router key got 403 `provider_blocked` (it authenticated but has no embark), and a bogus key got 401 `access_not_found`. An in-place update (hermes gemini weight 1 to 2) applied, the API showed weight 2, the next plan exited 0, and auth still behaved the same.
This rules out drift, lost ids or values, reordered `provider_configs` and broken auth on the 2.3.1 to 2.6.0 path, so the provider can stay at `~>0.1.0`. It settles risk 1.
Limits: fresh database with only these 4 keys and no traffic history. Only embeddings were called, against a stub. The router key's own routes (typesafe, ollama) were not called.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/vk_upgrade.sh`: a copy of `/home/vscode/spike-scratch/bifrost-1/vk_upgrade.sh`, which the command used
- `files/stub.py`: a copy of `/home/vscode/spike-scratch/bifrost-1/stub.py`, which the command used
