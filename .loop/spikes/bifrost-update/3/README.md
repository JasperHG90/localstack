---
type: spike
title: Spike bifrost-update/3
description: does Bifrost 2.3.1 accept a bare-string rerank and forward it, and embeddings, to the openai-based custom provider embark in a shape embark v0.2.1 accepts, as 2.0.0 does, with routing_info naming embark?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T08:32:08+00:00'
slug: bifrost-update
n: 3
outcome_written: true
---

# Spike bifrost-update/3

does Bifrost 2.3.1 accept a bare-string rerank and forward it, and embeddings, to the openai-based custom provider embark in a shape embark v0.2.1 accepts, as 2.0.0 does, with routing_info naming embark?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-bifrost-2/run.sh
```

## Outcome

On Bifrost 2.3.1 and 2.0.0 (local docker, same config shape as `bifrost.hcl` with sqlite in place of Postgres), a rerank with bare-string `documents` through a virtual key scoped to embark returned 200 on both. Embeddings returned 200 with `extra_fields.routing_info` = provider `embark`, key `embark-cluster` on both. 2.3.1 also adds `requested_provider` and `requested_model` to `routing_info`.
Both versions forward rerank to `/v1/rerank` as `{"model","query","documents":[{"text":...}]}` (objects, not bare strings), and the bodies were identical across the versions. A stub built from the embark v0.2.1 image validated every forwarded body with embark's own `RerankRequest` and `EmbeddingRequest` models and accepted all of them.
This rules out the 2.1.0 rerank change reaching an `openai`-based custom provider. It settles risk 2: 2.3.1 is a valid target for both calls.
Limits: stub upstream, not the real models on the Jetson. Two documents, one embedding input. Config store was sqlite, not Postgres.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/run.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-bifrost-2/run.sh`, which the command used
- `files/stub.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-bifrost-2/stub.py`, which the command used
- `files/client.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-bifrost-2/client.py`, which the command used
- `files/config.json`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-bifrost-2/config.json`, which the command used
