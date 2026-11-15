---
type: spike
title: Spike bifrost-decision-router/6
description: through Bifrost, how fast is ollama/clef for a three-choice complexity question, and do the three tier models answer?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T23:07:55+00:00'
slug: bifrost-decision-router
n: 6
outcome_written: true
---

# Spike bifrost-decision-router/6

through Bifrost, how fast is ollama/clef for a three-choice complexity question, and do the three tier models answer?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/loopspikes/ollama_live.sh
```

## Outcome

Run by the operator with the same key and `ollama/clef` (no tag): every decision returned 403 `model_blocked` ("Model 'clef' is not allowed"), so the bare name is not the one Bifrost knows. The tag `clef:27b` is (spike:bifrost-decision-router/7).

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/ollama_live.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/loopspikes/ollama_live.sh`, which the command used
