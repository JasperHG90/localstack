---
type: spike
title: Spike bifrost-decision-router/4
description: on Bifrost 2.3.1, can the complexity classifier run only for the router key, via a priority-0 global passthrough rule `virtual_key_name != "router"` ahead of the complexity_tier rules, or via virtual_key-scoped rules?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T20:51:44+00:00'
slug: bifrost-decision-router
n: 4
outcome_written: true
---

# Spike bifrost-decision-router/4

on Bifrost 2.3.1, can the complexity classifier run only for the router key, via a priority-0 global passthrough rule `virtual_key_name != "router"` ahead of the complexity_tier rules, or via virtual_key-scoped rules?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-bf3/run.sh
```

## Outcome

Exit 0 on Bifrost 2.3.1 (same split-mode, Postgres, auth-on, mock-Ollama harness as spike 2). Two configs each ran the classifier only for the router key: 3 classifier calls for 3 router chats, 0 for 3 `other` chats, with router chats sent to the right tier model and `other` kept on its requested model.
A, no key ID needed: a config.json global rule at priority 0, `virtual_key_name != "router"`, with target `{"weight": 1}` (no provider or model means keep the incoming ones), placed ahead of the three spike-2 tier rules. Why it works: the engine computes `complexity_tier` lazily, just before it evaluates the first rule whose CEL mentions it (plugins/routing/rules/engine.go:238-246), and stops at the first match. CEL `&&` short-circuiting does not prevent the call, which is why spike 2 paid for one on every key.
B: tier rules with `scope: virtual_key` and `scope_id` set to the router key's ID, created through POST /api/governance/routing-rules after the key existed, with no global rules. Other keys never load those rules (buildScopeChain, engine.go:408). Needs the key ID, so Terraform would need a second step (an http/null_resource call after the key is created). config.json validates scope_id against keys already in the store at boot, so it fails on a fresh store.
This answers the operator question from risk 1: the per-chat classifier cost on other keys can be avoided, and A is the cheaper fix. Limits: mock upstream; one non-router key tested; the passthrough rule also matches requests with no virtual key and marks them as routed by rule `not-router-passthrough`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/run.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-bf3/run.sh`, which the command used
- `files/client.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-bf3/client.py`, which the command used
- `files/mock.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-bf3/mock.py`, which the command used
- `files/config.json`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-bf3/config.json`, which the command used
