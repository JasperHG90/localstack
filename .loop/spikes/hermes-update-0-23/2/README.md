---
type: spike
title: Spike hermes-update-0-23/2
description: on hermes-agent v0.23.4 (arm64, uv 0.13.5, Python 3.14.9), does the faster-whisper uv.lock-pinned RUN line build, import with av 18.1.0, and transcribe a Telegram .ogg through the gateway voice path with model base?
tags:
- spike
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-26T13:36:13+00:00'
slug: hermes-update-0-23
n: 2
outcome_written: true
---

# Spike hermes-update-0-23/2

on hermes-agent v0.23.4 (arm64, uv 0.13.5, Python 3.14.9), does the faster-whisper uv.lock-pinned RUN line build, import with av 18.1.0, and transcribe a Telegram .ogg through the gateway voice path with model base?

The command exited 0:

```
/home/vscode/spike-scratch/hermes-1/spike.sh
```

## Outcome

On nousresearch/hermes-agent:v0.23.4 (arm64, Python 3.14.9), the repo's faster-whisper RUN line with uv switched to `uv-0.13.5-linux-arm64` builds with `--no-cache` in 7 s. `uv export --frozen --extra stt-whisper` against the revision-5 uv.lock works, and the install pulls arm64 cp314 wheels for all 12 packages: faster-whisper 1.2.1, av 18.1.0, ctranslate2 4.8.3 (was 4.8.1 on 0.22.2), onnxruntime 1.31.0. The image grew by 398 MB.
The image imports faster_whisper as uid 10000. The gateway voice path (`GatewayInboundMixin._enrich_message_with_transcription`, still in `gateway/run_inbound.py`) with no `stt` config picks provider `local`, model `base`. It downloaded the 142 MB model to /opt/data and transcribed a 5.4 s espeak .ogg/opus as "The quick brown fox dumps over the lazy dog. Please save this link." in 9.9 s, peaking at 574 MB of a 2048 MB cgroup.
This settles risk 1: the export, the install and the av/ctranslate2 wheels all work on the new base.
Watch: uv warns that av 18.1.0 is yanked ("double free when decoding audio with custom channel layouts, upgrade to 18.1.1"). Hermes' own lock pins it, so the line installs it anyway. Mono opus voice notes decoded fine here.
Limits: one run, network on. The offline restart from spike:ov-save-skill/10 was not repeated, and the gateway was driven directly, not through s6 and Telegram.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/home/vscode/spike-scratch/hermes-1/spike.sh`, which the command used
- `files/drive.py`: a copy of `/home/vscode/spike-scratch/hermes-1/drive.py`, which the command used
