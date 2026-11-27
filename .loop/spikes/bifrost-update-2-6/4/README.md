---
type: spike
title: Spike bifrost-update-2-6/4
description: does Bifrost 2.7.0 accept a bare-string rerank through a virtual key and forward it, and embeddings, to the openai-based custom provider embark in a shape embark v0.2.4 accepts, as 2.6.0 does, with routing_info naming embark?
tags:
- spike
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-27T10:47:15+00:00'
slug: bifrost-update-2-6
n: 4
outcome_written: true
---

# Spike bifrost-update-2-6/4

does Bifrost 2.7.0 accept a bare-string rerank through a virtual key and forward it, and embeddings, to the openai-based custom provider embark in a shape embark v0.2.4 accepts, as 2.6.0 does, with routing_info naming embark?

The command exited 0:

```
/home/vscode/spike-scratch/bifrost-27-2/run.sh
```

## Outcome

On Bifrost 2.7.0 and 2.6.0 (control), both in local docker with the `embark` provider block from `bifrost.hcl` and sqlite in place of Postgres, a rerank with bare-string `documents` through a virtual key scoped to embark returned 200. Embeddings returned 200 with `extra_fields.routing_info` = provider `embark`, key `embark-cluster`, on both.
Both versions forward rerank to `/v1/rerank` as `{"model","query","documents":[{"text":...}]}`, and the bodies were identical across the two versions. A stub on the deployed embark-jetson v0.2.4 image checked every forwarded body against embark's own `RerankRequest` and `EmbeddingRequest` models and accepted all of them (status 200).
This rules out the 2.6.0 to 2.7.0 changes breaking either call for an `openai`-based custom provider. It settles risk 3: 2.7.0 is a valid target for both calls.
Limits: stub upstream, not the real models on the Jetson. Two documents, one embedding input. Config store was sqlite, not Postgres, and the virtual key was made fresh on each version, not migrated. Scripts are spike:bifrost-update-2-6/1's with only the versions changed.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/run.sh`: a copy of `/home/vscode/spike-scratch/bifrost-27-2/run.sh`, which the command used
- `files/stub.py`: a copy of `/home/vscode/spike-scratch/bifrost-27-2/stub.py`, which the command used
- `files/client.py`: a copy of `/home/vscode/spike-scratch/bifrost-27-2/client.py`, which the command used
- `files/config.json`: a copy of `/home/vscode/spike-scratch/bifrost-27-2/config.json`, which the command used
