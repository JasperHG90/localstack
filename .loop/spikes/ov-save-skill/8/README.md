---
type: spike
title: Spike ov-save-skill/8
description: with faster-whisper 1.2.1 baked into hermes 0.22.2-2 and the default STT config, does the gateway voice path transcribe a Telegram .ogg under 2048 MB, and does the model cached on /opt/data work offline after a restart?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T15:06:36+00:00'
slug: ov-save-skill
n: 8
outcome_written: true
---

# Spike ov-save-skill/8

with faster-whisper 1.2.1 baked into hermes 0.22.2-2 and the default STT config, does the gateway voice path transcribe a Telegram .ogg under 2048 MB, and does the model cached on /opt/data work offline after a restart?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-voice2/spike.sh
```

## Outcome

The baked line from the briefing (`uv pip install ... faster-whisper==1.2.1`, unpinned) builds and imports, and the default config (no `stt` section) then picks provider `local`, model `base`. But every transcription fails: uv resolves PyAV to 19.0.1, which dropped the `metadata_errors` keyword that faster-whisper 1.2.1 passes to `av.open`, so the agent gets only the audio path. Hermes' own uv.lock pins av 18.1.0, which accepts it.
The model download itself worked: 142 MB under /opt/data/.cache/huggingface (HOME=/opt/data), and the `--network none` run loaded it without a download. Peak cgroup memory was 579 MB, the image grew by 393 MB.
This run does not settle risk 1. It shows that the unpinned line is wrong. spike:ov-save-skill/10 reruns with the install constrained to hermes' uv.lock.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-voice2/spike.sh`, which the command used
- `files/drive.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-voice2/drive.py`, which the command used
