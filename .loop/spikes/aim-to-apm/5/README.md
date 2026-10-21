---
type: spike
title: Spike aim-to-apm/5
description: does just check-install pass on a clean clone once step 8 widens the pre-commit exclude and the tracked APM files equal what the frozen install writes, after prek run --all-files?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-21T04:32:36+00:00'
slug: aim-to-apm
n: 5
outcome_written: true
---

# Spike aim-to-apm/5

does just check-install pass on a clean clone once step 8 widens the pre-commit exclude and the tracked APM files equal what the frozen install writes, after prek run --all-files?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-apm5/spike.sh
```

## Outcome

On a clean clone of HEAD, `just check-install` fails today (exit 1) on exactly 2 files: `.agents/skills/audit/evals/sample-findings.json` and `opencode.json`. The frozen install and `kmctl plugin patch` write both without a final newline, and end-of-file-fixer added one when they were committed.
With only the step-8 exclude (`.agents/`, `.opencode/`, `opencode.json`, `.mcp.json`, `apm.lock.yaml`) and those 2 files committed as the install writes them (3 files changed in all), `prek run --all-files` modified nothing. A second `just check-install` then exited 0 and `git status --porcelain` came back empty.
No other hook rewrites an APM-managed file. The only hook that failed was terraform-validate, because the clone has no gitignored `.ssh/id_rsa`. That failure is environmental and changes no file.
Settles risk 2: step 8 is enough, as long as the same commit takes the two install-written files without their trailing newline. Run at c000408, which has the same APM files and config as 501356f.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-apm5/spike.sh`, which the command used
