---
type: spike
title: Spike ov-no-auto-capture/1
description: does an openviking_tools wrapper provider (upstream OpenVikingMemoryProvider with writes forced off, empty prefetch, static prompt) load in the hermes 0.22.2-1 image, keep the six viking_* tools, and send no search, session or commit request for a plain turn, /new, or startup
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T14:02:13+00:00'
slug: ov-no-auto-capture
n: 1
outcome_written: true
---

# Spike ov-no-auto-capture/1

does an openviking_tools wrapper provider (upstream OpenVikingMemoryProvider with writes forced off, empty prefetch, static prompt) load in the hermes 0.22.2-1 image, keep the six viking_* tools, and send no search, session or commit request for a plain turn, /new, or startup

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovtools/spike_literal.sh
```

## Outcome

The plan's wrapper works except at startup. In the 0.22.2-1 image with `memory.provider: openviking_tools`, Hermes's own agent path (agent_init, then MemoryManager) loaded it from the bundled dir as `plugins.memory.openviking_tools` and activated it. `hermes memory status` marks it active, and all six viking_* tools reached the model. The model was a scripted stub, not an LLM.
A plain Telegram-platform turn, `/new` (the CLI's commit_session_boundary_async), a built-in memory write and shutdown sent 0 requests to the 1934 stub. An explicit viking_search sent 1 `POST /api/v1/search/find`, and the result reached the model.
It fails one check. The upstream `initialize` runs `_recover_pending_sessions` whether or not writes are on, so it committed a seeded stale pending session (`POST /api/v1/sessions/stale-spike/commit`). Forcing `agent_context` does not stop that, which contradicts the plan's "so no pending session is recovered".
Also, the wrapper inherits `name` = 'openviking', so the manager logs "Memory provider 'openviking' registered (6 tools)". Activation and status use `openviking_tools`.
This does not settle risk 1 as written. spike:ov-no-auto-capture/2 tests the fix.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike_literal.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-ovtools/spike_literal.sh`, which the command used
