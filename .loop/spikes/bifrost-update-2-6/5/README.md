---
type: spike
title: Spike bifrost-update-2-6/5
description: do virtual keys made by AirHelp-OSP/bifrost 0.1.1 on a Postgres store migrated 2.3.1 then 2.6.0 keep ids and values, plan clean with stable provider_configs order, authenticate and update in place after the store migrates to 2.7.0?
tags:
- spike
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-27T10:47:42+00:00'
slug: bifrost-update-2-6
n: 5
outcome_written: true
---

# Spike bifrost-update-2-6/5

do virtual keys made by AirHelp-OSP/bifrost 0.1.1 on a Postgres store migrated 2.3.1 then 2.6.0 keep ids and values, plan clean with stable provider_configs order, authenticate and update in place after the store migrates to 2.7.0?

The command exited 0:

```
/home/vscode/spike-scratch/bifrost-27-1/vk_upgrade.sh 0.1.1 v2.3.1 v2.7.0 v2.6.0
```

## Outcome

Provider `AirHelp-OSP/bifrost` 0.1.1 created the four `services.tf` keys (hermes, memex, openviking, router) on `maximhq/bifrost:v2.3.1` with a Postgres 16 store. The same store then ran under v2.6.0 and then v2.7.0 (arm64 image, migrations ran, e.g. `add_key_service_tier_column`, no error-level log lines on any version, health ok).
On 2.6.0 and on 2.7.0 the API showed the same 4 (name, id, value) tuples (hash `ee0b3dc32979e19c` on all three versions), `provider_configs` stayed alphabetical (embark, gemini, ollama; ollama, typesafe), and `terraform plan -detailed-exitcode` exited 0 on each.
On 2.7.0, hermes, memex and openviking got HTTP 200 embeddings through `embark` to a stub, router got 403 `provider_blocked`, a bogus key got 401. An in-place update (hermes gemini weight 1 to 2) applied, the API showed weight 2, the next plan exited 0, and auth behaved the same.
This rules out drift, lost ids or values, reordered `provider_configs` and broken auth on the 2.3.1 to 2.6.0 to 2.7.0 path, so the provider can stay at `~>0.1.0`. It settles risk 1 for the 2.7.0 target.
Limits: fresh database with only these 4 keys and no traffic history, bogus provider keys, only embeddings called against a stub, router's own routes not called. Ran in the devcontainer, not on the cluster.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/vk_upgrade.sh`: a copy of `/home/vscode/spike-scratch/bifrost-27-1/vk_upgrade.sh`, which the command used
- `files/stub.py`: a copy of `/home/vscode/spike-scratch/bifrost-27-1/stub.py`, which the command used
