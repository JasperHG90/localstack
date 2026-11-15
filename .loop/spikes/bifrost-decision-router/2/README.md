---
type: spike
title: Spike bifrost-decision-router/2
description: on Bifrost 2.3.1, do complexity_analyzer_config (decision classifier ollama/clef:cloud) and global routing_rules on virtual_key_name and complexity_tier load from config.json (split mode, Postgres store), reroute only the named key by tier, and what are the tier values?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T19:56:01+00:00'
slug: bifrost-decision-router
n: 2
outcome_written: true
---

# Spike bifrost-decision-router/2

on Bifrost 2.3.1, do complexity_analyzer_config (decision classifier ollama/clef:cloud) and global routing_rules on virtual_key_name and complexity_tier load from config.json (split mode, Postgres store), reroute only the named key by tier, and what are the tier values?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-bf1/run.sh
```

## Outcome

Exit 0 on Bifrost 2.3.1 (split mode, Postgres store, auth on, mock Ollama upstream). config.json `governance.complexity_analyzer_config` with `"classifier": "decision"`, `"decision": {"provider": "ollama", "model": "clef:cloud"}` loaded, and three global `routing_rules` (`virtual_key_name == "router" && complexity_tier == "SIMPLE"|"MEDIUM"|"COMPLEX"`, priorities 1-3) were stored. All 5 chat calls went where expected: the router key went to gpt-oss:120b-cloud / deepseek-v4.1-flash / mistral-large-4 by tier (routing_info shows requested vs served model), and the `other` key stayed on its requested model for both a SIMPLE and a COMPLEX prompt.
Tier values are uppercase `SIMPLE`, `MEDIUM`, `COMPLEX` (plugins/routing/complexity/config.go:44, sent as the choice keys to `/v1/systemone`). Matching on the key name works, so no key ID is needed. This settles risk 1.
Traps for step 2: the analyzer block needs non-empty `keywords.simple_keywords`/`medium_keywords`/`complex_keywords`, even with the decision classifier. Without them Bifrost logs "invalid complexity analyzer config" and skips the block. Each virtual key's provider_config needs `key_ids: ["*"]`, or it gets "no keys found".
Cost the plan does not state: the classifier ran on every chat request, the `other` key's included (5 decision calls for 5 requests). The `virtual_key_name` check comes first but does not stop the call, so Hermes, Memex and OpenViking chat calls would each also pay for a clef:cloud call.
Limits: the upstream was a mock, so this says nothing about real clef:cloud answers or latency. The provider key used `models: ["*"]` against a mock `/v1/models` that lists the four models.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/run.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-bf1/run.sh`, which the command used
- `files/client.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-bf1/client.py`, which the command used
- `files/mock.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-bf1/mock.py`, which the command used
- `files/config.json`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-bf1/config.json`, which the command used
