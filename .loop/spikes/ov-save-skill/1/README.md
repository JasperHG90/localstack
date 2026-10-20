---
type: spike
title: Spike ov-save-skill/1
description: does hermes 0.22.2-1 transcribe an inbound Telegram .ogg voice note with local faster-whisper under the 2048 MB cap, and does the install survive a restart?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T14:58:32+00:00'
slug: ov-save-skill
n: 1
outcome_written: true
---

# Spike ov-save-skill/1

does hermes 0.22.2-1 transcribe an inbound Telegram .ogg voice note with local faster-whisper under the 2048 MB cap, and does the install survive a restart?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-voice/spike.sh
```

## Outcome

In ghcr.io/jasperhg90/hermes:0.22.2-1 under a 2048 MB cap, the gateway's inbound voice path (`GatewayInboundMixin._enrich_message_with_transcription`) did not transcribe a 3 s espeak .ogg/opus clip. It returned "[voice message could not be transcribed automatically; the audio is available at: ...]" in 1.1 s at a cgroup peak of 105 MB. The result was the same after a restart on the same /opt/data volume.
Nothing was installed: faster_whisper is missing before and after, and /opt/data stays at 24K. So the lazy install in the plan never runs from this path.
Risk 1 is real. spike:ov-save-skill/3 gives the reason.
Limit: the handler was driven directly as uid 10000, not through s6 or Telegram.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-voice/spike.sh`, which the command used
