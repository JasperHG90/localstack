---
type: spike
title: Spike ci-tailscale-access/1
description: from a second repo calling a composite action, which repository, ref, environment and workflow_ref does the GitHub OIDC token carry, and does a Vault JWT role bound on them accept probe.yaml/main/lab and refuse another workflow, another branch and a job without the environment?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T19:54:14+00:00'
slug: ci-tailscale-access
n: 1
outcome_written: true
---

# Spike ci-tailscale-access/1

from a second repo calling a composite action, which repository, ref, environment and workflow_ref does the GitHub OIDC token carry, and does a Vault JWT role bound on them accept probe.yaml/main/lab and refuse another workflow, another branch and a job without the environment?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ts3/vault_bind.sh /tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ts3/tokens
```

## Outcome

Broken run: `docker exec` without `-i` dropped the role JSON on stdin, so role `probe` was never written and every login failed with "role could not be found". It answers nothing. spike:ci-tailscale-access/2 reran the same tokens with the fix.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/vault_bind.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ts3/vault_bind.sh`, which the command used
