---
type: spike
title: Spike ov-save-skill/10
description: with faster-whisper 1.2.1 baked into hermes 0.22.2-2 (pinned to its uv.lock) and the default STT config, does the gateway voice path transcribe a Telegram .ogg under 2048 MB, and does the model cached on /opt/data work offline after a restart?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T15:06:45+00:00'
slug: ov-save-skill
n: 10
outcome_written: true
---

# Spike ov-save-skill/10

with faster-whisper 1.2.1 baked into hermes 0.22.2-2 (pinned to its uv.lock) and the default STT config, does the gateway voice path transcribe a Telegram .ogg under 2048 MB, and does the model cached on /opt/data work offline after a restart?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-voice2/spike.sh
```

## Outcome

With faster-whisper 1.2.1 baked into hermes 0.22.2-2 and pinned to hermes' uv.lock (`uv export --frozen --extra stt-whisper` as constraints, so av 18.1.0 and ctranslate2 4.8.1), the gateway voice path transcribes with no `stt` config at all: provider `local`, model `base`, transcript "The quick brown fox dumps over the lazy dog. Please save this link." for a 5.4 s espeak .ogg/opus.
The first run took 6.5 s including the download and peaked at 593 MB of cgroup memory, which is 536 MB above the driver's 57 MB before transcription. The model (142 MB) went to /opt/data/.cache/huggingface, because HOME=/opt/data. A new container on the same volume with `--network none` transcribed the same text in 1.9 s at a 384 MB peak. The image grew by 397 MB.
Against the ~800 MB gateway and dashboard baseline, the worst case is about 1.34 GB of 2048 MB, so about 700 MB is left. This settles risk 1 for the bake-in choice.
Limits: only `base` was measured (`small` was not), the peak includes page cache, and the handler was driven directly as uid 10000, not through s6 and Telegram.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-voice2/spike.sh`, which the command used
- `files/drive.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-voice2/drive.py`, which the command used
