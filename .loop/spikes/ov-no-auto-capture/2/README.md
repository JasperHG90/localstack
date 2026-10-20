---
type: spike
title: Spike ov-no-auto-capture/2
description: does the openviking_tools wrapper with startup recovery also skipped (_recover_pending_sessions a no-op) load in the hermes 0.22.2-1 image, keep the six viking_* tools, and send no search, session or commit request at startup, a plain turn or /new
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T14:02:14+00:00'
slug: ov-no-auto-capture
n: 2
outcome_written: true
---

# Spike ov-no-auto-capture/2

does the openviking_tools wrapper with startup recovery also skipped (_recover_pending_sessions a no-op) load in the hermes 0.22.2-1 image, keep the six viking_* tools, and send no search, session or commit request at startup, a plain turn or /new

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovtools/spike_amended.sh
```

## Outcome

This is the same harness as spike 1, with the wrapper also overriding `_recover_pending_sessions` as a no-op. With the stale pending-session marker seeded, startup sent only `GET /health`. A plain turn, `/new`, a built-in memory write and shutdown sent 0 requests to the 1934 stub. An explicit viking_search sent 1 `POST /api/v1/search/find`, and its result reached the model.
Hermes loaded and activated the provider from `/opt/hermes/plugins/memory/openviking_tools` with all six viking_* tools on the tool surface. `hermes memory status` shows `openviking_tools ← active`.
This settles risk 1, provided the plan adds the `_recover_pending_sessions` override (spike 1 shows the wrapper as written still commits stale sessions at start).
Limits: stubs stood in for OpenViking and Bifrost. The driver called AIAgent directly with platform=telegram rather than a running gateway with a real Telegram chat. `/new` was the MemoryManager call the CLI makes, not the gateway's command handler.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike_amended.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovtools/spike_amended.sh`, which the command used
