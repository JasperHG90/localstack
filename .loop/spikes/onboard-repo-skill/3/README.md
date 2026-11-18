---
type: spike
title: Spike onboard-repo-skill/3
description: does APM 0.33.0 apm install, apm install --frozen or apm prune (the kmctl-install recipes) delete or overwrite a skill folder under .claude/skills/ that apm.yml does not list?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-18T14:43:44+00:00'
slug: onboard-repo-skill
n: 3
outcome_written: true
---

# Spike onboard-repo-skill/3

does APM 0.33.0 apm install, apm install --frozen or apm prune (the kmctl-install recipes) delete or overwrite a skill folder under .claude/skills/ that apm.yml does not list?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/2e7fce49-b865-4028-af55-9a588a2debef/scratchpad/spike-apm/spike3.sh
```

## Outcome

APM 0.33.0 (`uvx --from apm-cli==0.33.0 apm`, as the justfile's `kmctl-install` and `kmctl-install-frozen` recipes call it) left an unlisted `.claude/skills/onboard-repo/SKILL.md` and its `.agents/skills/` copy byte-identical (sha256) after `apm install`, `apm install --frozen` and `apm prune`. Each install ran in its own fresh copy of the committed tree with no `apm_modules/`, and installed 23 dependencies with exit 0. `apm prune` reported "No orphaned packages found": it prunes `apm_modules/` only, not deployed skill folders. `.claude/skills` went from 23 to 24 entries, and no tracked skill file changed.
APM only writes and removes the paths listed under `deployed_files` in `apm.lock.yaml`, so a folder it never deployed is left alone. This settles risk 1. Not covered: a skill named the same as an APM package's skill, which APM would overwrite. The repo has no `just install` recipe. The `apm.yml` header comment names one, but the real recipes are `kmctl-install` and `kmctl-install-frozen`. Their `kmctl plugin patch`, `cp` and `rm` steps were not run, and none of them touches `.claude/skills/`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike3.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/2e7fce49-b865-4028-af55-9a588a2debef/scratchpad/spike-apm/spike3.sh`, which the command used
