---
type: spike
title: Spike docs-reconcile/1
description: how many docs pages are mainly repo-worker content that belongs in .okf
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T17:22:56+00:00'
slug: docs-reconcile
n: 1
outcome_written: true
---

# Spike docs-reconcile/1

how many docs pages are mainly repo-worker content that belongs in .okf

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/5fcab3ba-3b32-4596-9541-452df76bd1a5/scratchpad/spike-docs-r3/classify.sh
```

## Outcome

None of the 81 pages under docs/how-to, docs/reference and docs/explanation is mainly repo-worker content: 0 are a plan, audit, handoff or decision record, so none has to move to `.okf/`. 24 pages hit a build-history marker or a ticket code (F9, G2, M1); read by hand, 11 are user pages carrying a few lines of build history to edit in place (ticket codes as provenance, "M1 landed this", "Since G2", "at the time of writing", verify-memex-oidc's G1-G5 change-guardrails), and the rest are log strings, dated measurements or backup file names.
This settles risk 3: the work stays in docs/ and does not move into okf-reconcile. The heaviest residue is verify-memex-oidc Step 16 and workload-identity's audience-registry owner column.
Limit: "mainly" is a reading, recorded as verdict lines in the script; the grep only finds candidates and can miss build history written without a marker.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/classify.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/5fcab3ba-3b32-4596-9541-452df76bd1a5/scratchpad/spike-docs-r3/classify.sh`, which the command used
