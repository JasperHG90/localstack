---
type: spike
title: Spike bifrost-decision-router/5
description: through Bifrost, how fast is ollama/clef:cloud for a three-choice complexity question, and do the three tier models answer?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T23:07:54+00:00'
slug: bifrost-decision-router
n: 5
outcome_written: true
---

# Spike bifrost-decision-router/5

through Bifrost, how fast is ollama/clef:cloud for a three-choice complexity question, and do the three tier models answer?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/loopspikes/ollama_live.sh
```

## Outcome

Run by the operator through the live Bifrost with their own virtual key (`jasper-laptop-cc`). Every `ollama/clef:cloud` decision returned 403 `model_blocked` ("not allowed for virtual key") in under 150 ms, so clef latency was not measured. `ollama/gpt-oss:120b-cloud` chat returned 403; `ollama/deepseek-v4.1-flash` (0.55 s) and `ollama/mistral-large-4` (1.37 s) returned 200. Cause, found next: Bifrost's ollama provider calls ollama.com directly, where model names carry no cloud suffix. Superseded by spike:bifrost-decision-router/7.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/ollama_live.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/loopspikes/ollama_live.sh`, which the command used
