---
type: spike
title: Spike bifrost-decision-router/1
description: does the Bifrost 2.3.1 Complexity Router classifier call to ollama/clef:cloud pass virtual-key governance and the catalog check, for a key listing clef:cloud explicitly and for a key whose allowed_models is the wildcard?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T19:55:20+00:00'
slug: bifrost-decision-router
n: 1
outcome_written: true
---

# Spike bifrost-decision-router/1

does the Bifrost 2.3.1 Complexity Router classifier call to ollama/clef:cloud pass virtual-key governance and the catalog check, for a key listing clef:cloud explicitly and for a key whose allowed_models is the wildcard?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-bf2/spike.sh
```

## Outcome

On local Bifrost 2.3.1 (SQLite store, ollama pointed at a logging mock whose /v1/models leaves out clef:cloud), every routed chat (4 of 4) made one `POST /v1/systemone` to clef:cloud upstream. It then landed on the tier's model: SIMPLE to gpt-oss:120b-cloud, COMPLEX to mistral-large-4. This held for the key that lists clef:cloud explicitly and for the `["*"]` key. `routing_metadata.calls` shows the decisions call, with `count_toward_budgets: true`.
The classifier skips virtual-key governance and the catalog check. It uses `PrepareContextForInternalRequest`, which skips the plugin pipeline and clears the key's include-only keys. A direct `POST /v1/decisions` to `ollama/clef:cloud` still returns 403 `model_blocked` on the `["*"]` key, and 200 on the explicit key.
Settles risk 2: classification does not break or fall through for either key. The explicit list matters only for direct decision calls.
Limits: mock upstream, not ollama.com. Global rules matched on complexity_tier only, so risk 1's scoping was not tested. A config.json virtual key also needs `key_ids: ["*"]`. Without it, chat fails with "no keys found" but the classifier still runs.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-bf2/spike.sh`, which the command used
