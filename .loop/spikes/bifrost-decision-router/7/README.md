---
type: spike
title: Spike bifrost-decision-router/7
description: through Bifrost, how fast is ollama/clef for a three-choice complexity question, and do the three tier models answer?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T23:07:56+00:00'
slug: bifrost-decision-router
n: 7
outcome_written: true
---

# Spike bifrost-decision-router/7

through Bifrost, how fast is ollama/clef for a three-choice complexity question, and do the three tier models answer?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/loopspikes/ollama_live.sh
```

## Outcome

Run by the operator through the live Bifrost with their own virtual key. Five `ollama/clef:27b` decisions with a three-choice SIMPLE/MEDIUM/COMPLEX question all returned 200: 697, 438, 493, 840 and 548 ms (worst 840 ms, under the default 1500 ms classifier timeout but close enough that the build sets 3000 ms). Tiers were sensible: "Say hi.", a one-line summary and a haiku SIMPLE (the haiku at confidence 0.44), a primes proof MEDIUM (confidence 0.23), a multi-region event store design COMPLEX. Chat calls answered for `ollama/gpt-oss:120b` (0.64 s), `ollama/deepseek-v4.1-flash` (0.55 s) and `ollama/mistral-large-4` (4.28 s). So the router's model names are `clef:27b`, `gpt-oss:120b`, `deepseek-v4.1-flash` and `mistral-large-4`, with no cloud suffix (spike:bifrost-decision-router/5 and spike:bifrost-decision-router/6 got 403 with the suffixed and untagged names). The key used passed `clef:27b`, so it may be in Bifrost's catalog; the build checks before choosing `"*"` or an explicit list.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/ollama_live.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/loopspikes/ollama_live.sh`, which the command used
