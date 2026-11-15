---
type: spike
title: Spike bifrost-decision-router/3
description: does Bifrost 2.3.1 accept a /v1/decisions request for ollama/clef:cloud with bare-string choices, and with object choices but no virtual key, how far does it get?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T20:16:51+00:00'
slug: bifrost-decision-router
n: 3
outcome_written: true
---

# Spike bifrost-decision-router/3

does Bifrost 2.3.1 accept a /v1/decisions request for ollama/clef:cloud with bare-string choices, and with object choices but no virtual key, how far does it get?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/loopspikes/clef/keyless.sh
```

## Outcome

Against the cluster's Bifrost 2.3.1 at https://bifrost.lab.orangecluster.nl, `POST /v1/decisions` for `ollama/clef:cloud` with one `choice` question (stdout.txt):

- Bare-string choices give 400 "Invalid request payload": each choice must be an object `{"value": ...}` (`core/schemas/decision.go:373` at upstream tag `transports/v2.3.1`).
- Object choices with no key give 401 `virtual_key_required`, after Bifrost resolved provider `ollama`, model `clef:cloud` and request type `decisions`. So the route and the body shape work, and the key goes in the `x-bf-vk` header.

Recorded by hand, not by this run, because it needs a virtual key: the operator ran the object-choice body with the Hermes key on 2026-11-15 and got 403 `model_blocked`, "Model 'clef:cloud' is not allowed for virtual key 'hermes'". A key with `allowed_models = ["*"]` admits only catalog models (`framework/modelcatalog/models.go:316`); `decide.sh keyed` with `BIFROST_VK` set reruns it. This is why the plan gives the router a key that names `clef:cloud` outright. It re-creates calls from an earlier session whose script was lost.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/keyless.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/loopspikes/clef/keyless.sh`, which the command used
- `files/decide.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/loopspikes/clef/decide.sh`, which the command used
