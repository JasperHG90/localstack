---
type: spike
title: Spike ov-save-skill/7
description: with faster-whisper baked into the hermes 0.22.2-1 image venv, does a Telegram .ogg voice note get transcribed under the 2048 MB cap, and what does it cost in image size, memory and time?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T14:58:34+00:00'
slug: ov-save-skill
n: 7
outcome_written: true
---

# Spike ov-save-skill/7

with faster-whisper baked into the hermes 0.22.2-1 image venv, does a Telegram .ogg voice note get transcribed under the 2048 MB cap, and what does it cost in image size, memory and time?

The command exited 11:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-voice/spike3.sh
```

## Outcome

This run is a script bug, not a finding. It exited 11 because buildkit served the bake step from cache, so the grep for uv's "Installed" lines matched nothing. No transcription was attempted.
It does not measure the cost of baking faster-whisper into the image. That is still open: three runs on risk 1 were used up.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike3.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-voice/spike3.sh`, which the command used
- `files/drive.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-voice/drive.py`, which the command used
