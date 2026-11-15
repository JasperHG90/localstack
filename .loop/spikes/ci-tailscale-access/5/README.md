---
type: spike
title: Spike ci-tailscale-access/5
description: from a lab-Environment job in localstack (legacy OIDC subject) calling the join composite action by its remote ref, does tailscale/github-action@v4 join with only the federated client id, audience and tag, and does a job without the environment fail to join?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T21:37:44+00:00'
slug: ci-tailscale-access
n: 5
outcome_written: true
---

# Spike ci-tailscale-access/5

from a lab-Environment job in localstack (legacy OIDC subject) calling the join composite action by its remote ref, does tailscale/github-action@v4 join with only the federated client id, audience and tag, and does a job without the environment fail to join?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/ts-spike/check_run.sh 43764572127 join
```

## Outcome

GitHub Actions run 43764572127 in JasperHG90/localstack, on the throwaway branch `spike/lab-auth-reach` (created through the GitHub API, not merged). Both jobs called the composite action by its remote ref, `JasperHG90/localstack/.github/actions/join@spike/lab-auth-reach`, which wraps `tailscale/github-action@v4` with only `oauth-client-id`, `audience` and `tags: tag:ci` (empty `args`, since v4 adds `--accept-routes` itself).

- `with-env` (`environment: lab`): "Tailscale up command completed successfully on attempt 1".
- `no-env`: "failed to exchange JWT for access token: token exchange failed with status 403 ... Unauthorized", so it never joined.

localstack issues the legacy OIDC subject (`repo:JasperHG90/localstack:environment:lab`, `use_immutable_subject: false`), which the federated identity's subject `repo:JasperHG90/*:environment:lab` matches. That is why this works where spike:ci-tailscale-access/3 failed: lab-auth-probe is a new repo and GitHub gives repos created after mid-2026 the immutable subject (`repo:JasperHG90@8079803/...`). A caller repo with the immutable format needs a second federated identity, or this one changed, in the Tailscale console. That is an operator step for each such repo, recorded in the how-to; it does not block this repo.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/check_run.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/ts-spike/check_run.sh`, which the command used
- `files/lab-auth-reach-spike.yaml`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/ts-spike/repo/.github/workflows/lab-auth-reach-spike.yaml`, which the command used
- `files/action.yml`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/ts-spike/repo/.github/actions/join/action.yml`, which the command used
