---
type: spike
title: Spike docs-reconcile/3
description: does kmctl check enforce its docs body sections or sources paths once a docs page has front matter?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T17:44:33+00:00'
slug: docs-reconcile
n: 3
outcome_written: true
---

# Spike docs-reconcile/3

does kmctl check enforce its docs body sections or sources paths once a docs page has front matter?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/5fcab3ba-3b32-4596-9541-452df76bd1a5/scratchpad/spike-docs-r1/check.sh
```

## Outcome

Added description, stale_after and sources front matter to one how-to (log-in-to-vault), one reference (bootstrap-secrets) and one explanation page (cluster-roles), all keeping the repo's own sections, then ran kmctl v0.10.0 `check --fix` and `check`: all checks passed, with no section finding of any kind (exit 0).
kmctl's section lists (kinds.py) feed only the JSON schema and the `kmctl new doc` skeleton. `check_docs` validates indexes, links and the shape of front matter fields, never body headings.
`check` does not verify that `sources` paths exist (does/not/exist.tf passed). Only `kmctl review due` reports it, as a `notice ... source not resolved`, not a failure.
The section set is not configurable: v0.10.0 has no kmctl config file, and the sections are hard-coded in `KINDS`. Since nothing enforces them, that does not matter here.
Settles risk 1: adding front matter does not force kmctl's sections, so the repo's how-to skeleton can stay. Limit: three pages, kmctl v0.10.0 only, and a later kmctl that starts checking sections would reopen this.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/check.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/5fcab3ba-3b32-4596-9541-452df76bd1a5/scratchpad/spike-docs-r1/check.sh`, which the command used
