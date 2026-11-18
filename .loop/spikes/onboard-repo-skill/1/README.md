---
type: spike
title: Spike onboard-repo-skill/1
description: does APM 0.33.0 apm install, apm install --frozen or apm prune (the kmctl-install recipes) delete or overwrite a skill folder under .claude/skills/ that apm.yml does not list?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-18T14:43:54+00:00'
slug: onboard-repo-skill
n: 1
outcome_written: true
---

# Spike onboard-repo-skill/1

does APM 0.33.0 apm install, apm install --frozen or apm prune (the kmctl-install recipes) delete or overwrite a skill folder under .claude/skills/ that apm.yml does not list?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/2e7fce49-b865-4028-af55-9a588a2debef/scratchpad/spike-apm/spike.sh
```

## Outcome

Not the citing run: superseded by spike 3. The sentinel survived `apm install`, the `apm install --frozen` that followed it, and `apm prune`. But `--frozen` failed with exit 1 before deploying anything ("Found multiple package directories for one dependency: apm_modules/JasperHG90, apm_modules/jasperhg90"), so the frozen path was never exercised, and the script did not fail on that.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/2e7fce49-b865-4028-af55-9a588a2debef/scratchpad/spike-apm/spike.sh`, which the command used
