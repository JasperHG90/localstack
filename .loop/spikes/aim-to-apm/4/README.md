---
type: spike
title: Spike aim-to-apm/4
description: does just check-install pass on a clean clone once step 8 widens the pre-commit exclude and the tracked APM files equal what the frozen install writes, after prek run --all-files?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-21T04:32:37+00:00'
slug: aim-to-apm
n: 4
outcome_written: true
---

# Spike aim-to-apm/4

does just check-install pass on a clean clone once step 8 widens the pre-commit exclude and the tracked APM files equal what the frozen install writes, after prek run --all-files?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-apm5/spike.sh
```

## Outcome

Flawed run, superseded by spike:aim-to-apm/5. The script wrote its logs inside the clone, so the second `just check-install` failed on the untracked `b2.log`. The final clean status came only from the script deleting that log, so the exit 0 proves nothing.
Its part (a) still stands and matches run 5: at 501356f, check-install fails on `.agents/skills/audit/evals/sample-findings.json` and `opencode.json`, both missing a trailing newline when the install writes them. After step 8, prek modified no file.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/spike.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/spike-apm5/spike.sh`, which the command used
