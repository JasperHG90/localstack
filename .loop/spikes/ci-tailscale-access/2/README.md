---
type: spike
title: Spike ci-tailscale-access/2
description: from a second repo calling a composite action, which repository, ref, environment and workflow_ref does the GitHub OIDC token carry, and does a Vault JWT role bound on them accept probe.yaml/main/lab and refuse another workflow, another branch and a job without the environment?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T19:54:15+00:00'
slug: ci-tailscale-access
n: 2
outcome_written: true
---

# Spike ci-tailscale-access/2

from a second repo calling a composite action, which repository, ref, environment and workflow_ref does the GitHub OIDC token carry, and does a Vault JWT role bound on them accept probe.yaml/main/lab and refuse another workflow, another branch and a job without the environment?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ts3/vault_bind.sh /tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ts3/tokens
```

## Outcome

Real GitHub OIDC tokens from 5 jobs in `JasperHG90/lab-auth-probe` (composite action `.github/actions/claims`, audience `spike-only-not-trusted`) carry the caller's claims: `repository=JasperHG90/lab-auth-probe`, `ref=refs/heads/<branch>`, `environment=lab` (absent with no environment), `workflow_ref`=`job_workflow_ref`=`JasperHG90/lab-auth-probe/.github/workflows/<file>@refs/heads/<branch>`. `sub` uses the immutable-ID form `repo:JasperHG90@8079803/lab-auth-probe@1459171707:environment:lab`.
A local Vault 1.21.1 `jwt` mount (`oidc_discovery_url` set to GitHub) with a role holding string `bound_claims` on all four claims and `bound_audiences` accepted 1 of 5: probe.yaml, main, lab. It refused other.yaml (workflow_ref), spike-branch (ref) and both no-env jobs ("environment" is missing). 5/5 matched what we expected.
This settles risk 3 for claims and binding. Limits: the composite action lived in the same repo, not in localstack called cross-repo (the token is minted per job, so the action's repo should not change it, but this run did not test that). Vault fetched GitHub's keys from the devcontainer, not from the cluster. The tokens are in the spike only as runtime input and were not kept.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/vault_bind.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ts3/vault_bind.sh`, which the command used
