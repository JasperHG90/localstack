---
type: spike
title: Spike aim-to-apm/2
description: can APM 0.33.0 apm.yml install single plain .md rules, an agent .md and a skill folder from repos without apm.yml, pinned to commits (one repo at several commits), and does apm install --frozen reproduce them byte-identical to upstream?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T20:56:10+00:00'
slug: aim-to-apm
n: 2
outcome_written: true
---

# Spike aim-to-apm/2

can APM 0.33.0 apm.yml install single plain .md rules, an agent .md and a skill folder from repos without apm.yml, pinned to commits (one repo at several commits), and does apm install --frozen reproduce them byte-identical to upstream?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-apm1/spike.sh
```

## Outcome

APM 0.33.0 cannot install a single plain `.md` file: all 3 of the 4 entries that were files failed (`rules/plain-language.md`, `.claude/rules/slop-scan-for-docs.md`, `agents/feature-planner.md`). The object form (`- git: URL` / `path:` / `ref: SHA`) fails at fetch with "Path '...' is not a directory". The string shorthand `owner/repo/path.md#sha` fails at parse because a single file must end in `.prompt.md`, `.instructions.md` or `.agent.md` (`VIRTUAL_FILE_EXTENSIONS` in `apm_cli/models/dependency/reference.py`).
The skill folder works. `skills/tools/generate-art` pinned to 516c105 landed in `.claude/skills/generate-art/` and `.agents/skills/generate-art/` (opencode reads the shared `.agents/skills/`). The bytes match a git checkout at the pin, `apm.lock.yaml` records the SHA, and after deleting the deployed files `apm install --frozen` restored them byte for byte.
One repo at two commits works: two skill folders from jasperhg90/skills at 516c105 and 7e0ee1b installed side by side, each locked to its own SHA. A failed file entry aborts the whole install with no lockfile.
Risk 1 holds for rules and agents, not for skill folders. This was not tested: renaming upstream to `.instructions.md`/`.agent.md`, or a wrapper package with its own `apm.yml`.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-apm1/spike.sh`, which the command used
