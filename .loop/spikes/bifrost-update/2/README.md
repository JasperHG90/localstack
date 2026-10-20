---
type: spike
title: Spike bifrost-update/2
description: does Bifrost 2.3.1 accept a bare-string rerank and forward it, and embeddings, to the openai-based custom provider embark in a shape embark v0.2.1 accepts, as 2.0.0 does, with routing_info naming embark?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T08:32:09+00:00'
slug: bifrost-update
n: 2
outcome_written: true
---

# Spike bifrost-update/2

does Bifrost 2.3.1 accept a bare-string rerank and forward it, and embeddings, to the openai-based custom provider embark in a shape embark v0.2.1 accepts, as 2.0.0 does, with routing_info naming embark?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-bifrost-2/run.sh
```

## Outcome

Same run and result as spike 3 (exit 0: bare-string rerank 200, embeddings routed to embark on 2.0.0 and 2.3.1, identical object-form bodies at embark). Superseded by spike 3 only because this run's evidence kept `run.sh` alone, without the `stub.py`, `client.py` and `config.json` it reads. Cite spike 3.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/run.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-bifrost-2/run.sh`, which the command used
