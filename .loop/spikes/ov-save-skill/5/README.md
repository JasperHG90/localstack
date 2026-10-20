---
type: spike
title: Spike ov-save-skill/5
description: does a plain "save this <url>" make Hermes (0.22.2-1, deepseek-v4.1-flash) load the save-to-openviking skill before saving, and ask where when no place was given, with one pointer line in SOUL.md?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T14:50:53+00:00'
slug: ov-save-skill
n: 5
outcome_written: true
---

# Spike ov-save-skill/5

does a plain "save this <url>" make Hermes (0.22.2-1, deepseek-v4.1-flash) load the save-to-openviking skill before saving, and ask where when no place was given, with one pointer line in SOUL.md?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-skillpick/spike_skillpick.sh
```

## Outcome

Harness was wrong again, so this run does not answer risk 3. The stub's `/health` had no `version` and it had no `/api/v1/system/status`. The plugin's health check rejected it, so every `viking_*` call returned "OpenViking server not connected". The model then spent its 12-iteration cap debugging the plugin.
What it did show (pointer line in SOUL.md, live anthropic.com article URL): in 8 of 8 fresh sessions the first tool call was `skill_view("save-to-openviking")`, and the second was `viking_read` of `.map.md`. Superseded by the next run.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike_skillpick.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-skillpick/spike_skillpick.sh`, which the command used
