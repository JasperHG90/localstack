---
type: spike
title: Spike hermes-update/1
description: does the bifrost model-provider drop-in plugin from hermes.hcl still load as provider bifrost in hermes-agent v0.22.2 on arm64 and Python 3.14, and route a model call to a stub Bifrost
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T08:32:25+00:00'
slug: hermes-update
n: 1
outcome_written: true
---

# Spike hermes-update/1

does the bifrost model-provider drop-in plugin from hermes.hcl still load as provider bifrost in hermes-agent v0.22.2 on arm64 and Python 3.14, and route a model call to a stub Bifrost

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-hermes-2/spike.sh
```

## Outcome

The bifrost plugin, copied byte for byte from the two `model-providers/bifrost` templates in `hermes.hcl`, loads in `nousresearch/hermes-agent:v0.22.2` (arm64, Python 3.14.7) as the hermes user. `from providers import register_provider` and `providers.base.ProviderProfile` both import. `get_provider_profile("bifrost")` returns it with source `user`, and the alias `bifrost-gateway` resolves too. It shows up in `list_providers()` and `hermes_cli.auth.PROVIDER_REGISTRY`, and `resolve_runtime_provider("bifrost")` gives base_url `http://127.0.0.1:8080/v1` in chat_completions mode with `BIFROST_API_KEY` picked up.

A one-shot `hermes -z` run with `model.provider: bifrost` sent `POST /v1/chat/completions` (model `ollama/deepseek-v4.1-flash`, `Bearer` key) to a stub Bifrost on 127.0.0.1:8080 and printed the stub reply. That rules out a provider rewrite for 0.22, so this settles risk 2.

Limits: run in local docker against the upstream base, not the rebuilt `ghcr.io/jasperhg90/hermes:0.22.2-1`. Hermes ran under a fresh HERMES_HOME inside the container with a four-line config, not under the s6 gateway entrypoint or the full jobspec config.yaml. Fallback and auxiliary model routing were not exercised.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-hermes-2/spike.sh`, which the command used
