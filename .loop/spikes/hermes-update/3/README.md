---
type: spike
title: Spike hermes-update/3
description: can a Dockerfile layer on hermes-agent v0.22.2 pin the openviking catalog plugin 2.1.1 at build time (uv pip install, or a copy into the bundled memory dir) so the gateway loads it offline with no runtime install
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T08:49:00+00:00'
slug: hermes-update
n: 3
outcome_written: true
---

# Spike hermes-update/3

can a Dockerfile layer on hermes-agent v0.22.2 pin the openviking catalog plugin 2.1.1 at build time (uv pip install, or a copy into the bundled memory dir) so the gateway loads it offline with no runtime install

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-hermes-1/spike_alt.sh
```

## Outcome

`uv pip install` of the catalog plugin (2.1.1 at 9f150ece, subdirectory examples/hermes-plugin) fails to build ("Multiple top-level modules discovered in a flat-layout"). The plugin also declares no `hermes_agent.memory_providers` entry point, so a pip install could not register the provider even if it built. That rules out the pip/uv route.
Copying the same pinned subdirectory into /opt/hermes/plugins/memory/openviking in a Dockerfile layer works: find_provider_dir resolves it, and the gateway on a fresh volume with no route off the host sent viking_search to the 1934 stub with the placeholder key. It made no runtime install attempt, wrote nothing to /opt/data/plugins, and started no openviking-server.
This is a working build-time alternative to risk 1's lazy install, with the same stub limits as spike 2.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike_alt.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-hermes-1/spike_alt.sh`, which the command used
