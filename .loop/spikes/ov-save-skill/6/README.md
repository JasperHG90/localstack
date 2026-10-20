---
type: spike
title: Spike ov-save-skill/6
description: does a plain "save this <url>" make Hermes (0.22.2-1, deepseek-v4.1-flash) load the save-to-openviking skill before saving, and ask where when no place was given, with one pointer line in SOUL.md?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T14:55:14+00:00'
slug: ov-save-skill
n: 6
outcome_written: true
---

# Spike ov-save-skill/6

does a plain "save this <url>" make Hermes (0.22.2-1, deepseek-v4.1-flash) load the save-to-openviking skill before saving, and ask where when no place was given, with one pointer line in SOUL.md?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-skillpick/spike_skillpick.sh
```

## Outcome

With the one pointer line in SOUL.md, the draft skill in the skills library and the real model (ollama/deepseek-v4.1-flash via the lab Bifrost), 8 of 8 fresh sessions called `skill_view("save-to-openviking")` as their first tool call, then `viking_read` of `.map.md`. No session called `viking_add_resource` before the skill. Spikes 4 and 5 had broken harnesses, but their first tool call was the same in 16 of 16 sessions.
No place given (5 runs): 0 writes. All 5 proposed `blogs/anthropic/` and asked the operator to confirm. Run 1 ended "Confirm that, or name another place" with no "?", so the driver's "?" check failed it and the spike exited 1. That check was too strict, and the behavior matches the plan.
Place given (3 runs): 3 of 3 saved with `parent=viking://user/jasper/resources/blogs/anthropic/` without asking. The stub's fixed `root_uri` (`resources/x`) then sent the model into checking where the save landed.
The model skips the skill only rarely, so the SOUL pointer is enough, and the `system_prompt_block` placement was not tried. This settles risk 3 in substance, but the run exited 1.
Limits: a live anthropic.com URL replaced example.com (a 404, which the model would not save). The post-turn self-improvement review was off. The driver called AIAgent directly, not the Telegram gateway.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike_skillpick.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-skillpick/spike_skillpick.sh`, which the command used
