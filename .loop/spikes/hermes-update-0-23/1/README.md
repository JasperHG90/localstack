---
type: spike
title: Spike hermes-update-0-23/1
description: does the model-providers/bifrost drop-in plugin from hermes.hcl load as provider bifrost in hermes-agent v0.23.4 and send POST /v1/chat/completions to a stub Bifrost?
tags:
- spike
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-26T13:38:53+00:00'
slug: hermes-update-0-23
n: 1
outcome_written: true
---

# Spike hermes-update-0-23/1

does the model-providers/bifrost drop-in plugin from hermes.hcl load as provider bifrost in hermes-agent v0.23.4 and send POST /v1/chat/completions to a stub Bifrost?

The command exited 0:

```
/home/vscode/spike-scratch/hermes-2/bifrost.sh
```

## Outcome

The bifrost plugin, copied byte for byte from the two `model-providers/bifrost` templates in `hermes.hcl` into `$HERMES_HOME/plugins/model-providers/`, loads in `nousresearch/hermes-agent:v0.23.4` (arm64, Python 3.14.9) as provider `bifrost` with source `user`. The `bifrost-gateway` alias, `list_providers()`, `PROVIDER_REGISTRY` and `resolve_runtime_provider` (base_url `http://127.0.0.1:8080/v1`, chat_completions, key set) all hold.
A one-shot `hermes -z` sent `POST /v1/chat/completions` (model `ollama/deepseek-v4.1-flash`, `Bearer` key, streamed) to the stub Bifrost and printed the stub reply. That rules out a provider rewrite for 0.23 and settles risk 3.
Limits: run against the upstream base with a fresh HERMES_HOME and a four-line config, not the s6 gateway or the full jobspec config (spike 3 covers the gateway path with the rendered config and also routes through `provider=bifrost`). Fallback and auxiliary routing were not exercised. `hermes` prints a harmless "install out of sync (pnpm)" warning on the base.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/bifrost.sh`: a copy of `/home/vscode/spike-scratch/hermes-2/bifrost.sh`, which the command used
