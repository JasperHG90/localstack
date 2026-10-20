---
type: spike
title: Spike hermes-update/2
description: does hermes v0.22.2 unattended install the openviking catalog plugin onto its data volume, keep it across an offline restart, send viking_search to the 1934 sidecar with the placeholder key and start no openviking-server
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T08:48:59+00:00'
slug: hermes-update
n: 2
outcome_written: true
---

# Spike hermes-update/2

does hermes v0.22.2 unattended install the openviking catalog plugin onto its data volume, keep it across an offline restart, send viking_search to the 1934 sidecar with the placeholder key and start no openviking-server

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-hermes-1/spike_lazy.sh
```

## Outcome

In the v0.22.2 arm64 image with config.yaml and the bifrost plugin rendered from hermes.hcl, the unattended gateway (no TTY, API server) installed the openviking catalog plugin 2.1.1 into /opt/data/plugins/openviking on the first agent turn ("moved out of core — installed its plugin from the catalog"). It wrote nothing outside the volume, since the deps (httpx, psutil, packaging) already ship in the venv.
A new container on the same volume, on a network with no route off the host, loaded the plugin without reinstalling it. Both runs sent viking_search (POST /api/v1/search/find) and the prefetch search to the 127.0.0.1:1934 stub with the placeholder key, and neither started openviking-server, which is not on PATH and is skipped while the port has a listener.
Limit: the provider sends no X-OpenViking-Account header when a key is set (the 0.21 code has the same `_headers`), so account `lab` comes from the sidecar's token, which this spike did not test. Stubs stood in for the sidecar and Bifrost, and the dashboard and chat platforms were off.
This settles risk 1 for the lazy-install path. The first start needs GitHub reachable from the node, and a failed install backs off for an hour or more.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike_lazy.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-hermes-1/spike_lazy.sh`, which the command used
