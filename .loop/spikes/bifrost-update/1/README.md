---
type: spike
title: Spike bifrost-update/1
description: does the AirHelp-OSP/bifrost 0.1.1 provider create hermes-shaped virtual keys on Bifrost 2.3.1 with a Postgres store and auth on, and plan clean afterwards?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T08:30:17+00:00'
slug: bifrost-update
n: 1
outcome_written: true
---

# Spike bifrost-update/1

does the AirHelp-OSP/bifrost 0.1.1 provider create hermes-shaped virtual keys on Bifrost 2.3.1 with a Postgres store and auth on, and plan clean afterwards?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-bifrost-1/vk_drift.sh 0.1.1 v2.3.1
```

## Outcome

On a throwaway `maximhq/bifrost:v2.3.1` arm64 container with a Postgres 16 config store, `auth_config` on and the same ollama, gemini and embark providers as `bifrost.hcl`, provider `AirHelp-OSP/bifrost` 0.1.1 created the hermes, memex and openviking virtual keys (3 added, no consistency error), and the next `terraform plan -detailed-exitcode` exited 0 with "No changes".
An in-place update (hermes gemini weight 1 to 2) applied cleanly, the API showed the new weight with `allow_all_keys` kept, and a further plan also exited 0.
This rules out drift or post-apply errors from 2.3.1's virtual key responses for this resource shape, so the provider can stay at `~>0.1.0` and 0.4.x was not needed. Settles risk 1.
Limit: keys were created fresh on 2.3.1. It did not test state created on 2.0.0 and refreshed after the store migrates to 2.3.1, which is the path the live apply takes.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/vk_drift.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-bifrost-1/vk_drift.sh`, which the command used
