---
type: spike
title: Spike docs-reconcile/2
description: is drift between docs/ pages and the code a docs bug or a code bug?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T17:23:29+00:00'
slug: docs-reconcile
n: 2
outcome_written: true
---

# Spike docs-reconcile/2

is drift between docs/ pages and the code a docs bug or a code bug?

The command exited 0:

```
python3 /tmp/claude-1000/-home-vscode-workspace/5fcab3ba-3b32-4596-9541-452df76bd1a5/scratchpad/spike-docs-r4/drift.py
```

## Outcome

Across all 81 pages in docs/how-to, reference and explanation, 55 backticked file-like paths fail to resolve from the repo root or the page folder. 43 are shorthand for a file that exists (bare `identity.tf`, `oidc.tf`, `services/grafana.hcl` and so on). 1 is a deleted file: `deployments/infrastructure/vars/prod.tfvars`, untracked in 529d176. 7 are runtime paths that the code names (Nomad `local/`, `secrets/`, Vault `bootstrap/*`, `auth.json`). The other 4 are files in other codebases (`token.json` and `memex_common/config.py` in memex, `telemetry/tracer.py` in OpenViking, `docker-entrypoint.sh` in the postgres image), so none of them is a code bug here.
All 100 `just` and `localstack` invocations on 23 pages, in inline code and fenced blocks, match a recipe in one of the repo's justfiles or the CLI's --help (subcommands and `--flags`).
This rules out "the code is wrong" as a meaningful share of the drift: 0 of 44 drift items are code bugs, so the drift a sample can find is docs-side. Risk 4 is settled.
Limits: the check covers paths, recipes and CLI flags only. It does not cover prose claims about behavior (ports, policies, TTLs). A `just` recipe counts as found if any justfile has it, not necessarily the one in the page's folder.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/drift.py`: a copy of `/tmp/claude-1000/-home-vscode-workspace/5fcab3ba-3b32-4596-9541-452df76bd1a5/scratchpad/spike-docs-r4/drift.py`, which the command used
