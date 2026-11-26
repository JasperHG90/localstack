---
type: spike
title: Spike hermes-update-0-23/3
description: does the hermes v0.23.4 unattended gateway, with the OpenViking catalog plugin 2.1.1 copied in as the Dockerfile does and our openviking_tools wrapper, load memory.provider openviking_tools without error and send viking_search to OPENVIKING_ENDPOINT?
tags:
- spike
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-26T13:38:55+00:00'
slug: hermes-update-0-23
n: 3
outcome_written: true
---

# Spike hermes-update-0-23/3

does the hermes v0.23.4 unattended gateway, with the OpenViking catalog plugin 2.1.1 copied in as the Dockerfile does and our openviking_tools wrapper, load memory.provider openviking_tools without error and send viking_search to OPENVIKING_ENDPOINT?

The command exited 0:

```
/home/vscode/spike-scratch/hermes-2/ov.sh
```

## Outcome

An image built `FROM nousresearch/hermes-agent:v0.23.4` with the Dockerfile's own catalog-plugin `RUN` (pin `9f150ece`, version 2.1.1) and `COPY openviking_tools`, run as the unattended `hermes gateway run` with config.yaml rendered from `hermes.hcl` (`memory.provider: "openviking_tools"`), logged `Memory provider 'openviking_tools' registered (7 tools)` and `activated`, with no error, traceback or compat warning about the provider. `hermes memory status` shows `openviking_tools ← active`.
One API-server turn made the model call `viking_search`, which sent 1 `POST /api/v1/search/find` with the placeholder key to the stub at `OPENVIKING_ENDPOINT` (127.0.0.1:1934), and the reply came back after the result. The container had no route off the host and nothing was installed under /opt/data/plugins.
This rules out a plugin bump or wrapper rewrite for the load path and settles risk 2. Limits: stubs stood in for the sidecar and Bifrost, the apt and faster-whisper layers were left out of the image, and only viking_search of the seven tools was called.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/ov.sh`: a copy of `/home/vscode/spike-scratch/hermes-2/ov.sh`, which the command used
