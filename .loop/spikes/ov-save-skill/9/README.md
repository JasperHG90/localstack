---
type: spike
title: Spike ov-save-skill/9
description: on the deployed hermes 0.22.2-2 image, does a plain "save this <url>" make Hermes call skill_view(save-to-openviking) first, ask before saving when no place was given, and save to the named folder when one was?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T15:06:37+00:00'
slug: ov-save-skill
n: 9
outcome_written: true
---

# Spike ov-save-skill/9

on the deployed hermes 0.22.2-2 image, does a plain "save this <url>" make Hermes call skill_view(save-to-openviking) first, ask before saving when no place was given, and save to the named folder when one was?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-skillpick/spike_skillpick2.sh
```

## Outcome

On the deployed image (hermes 0.22.2-2 with its own `openviking_tools` wrapper), with the plan's one pointer line in SOUL.md and the real model (ollama/deepseek-v4.1-flash via Bifrost), 8 of 8 fresh sessions made `skill_view("save-to-openviking")` their first tool call.
No place given: 5 of 5 made no write and no `viking_add_resource` call, proposed `blogs/anthropic/`, and asked the operator to confirm or name another place (4 ended with "?", 1 with "Confirm ... or name another place"). Place given: 3 of 3 saved with `parent=viking://user/jasper/resources/blogs/anthropic/` without asking.
This settles risk 3: the SOUL pointer is enough for the model to load the skill. It reruns spike 6 with the pass condition the plan states. Spike 6 failed only because its driver required a literal "?".
Side finding: after saving, all 3 place-given runs spent their remaining turns checking where the save landed, because the stub returns a fixed `root_uri` (`resources/x`). They used `terminal` with curl despite SOUL's "Do not shell out to curl", and run 5 hit the 12-iteration cap.
Limits: a stub OpenViking, background_review off, AIAgent called directly rather than through the Telegram gateway, one URL.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike_skillpick2.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-skillpick/spike_skillpick2.sh`, which the command used
