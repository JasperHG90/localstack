---
type: spike
title: Spike ci-tailscale-access/3
description: 'does tailscale/github-action@v4 join with only oauth-client-id, audience and tags from inside a composite action in an environment: lab job, and does a job without environment: lab fail to join?'
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T19:55:58+00:00'
slug: ci-tailscale-access
n: 3
outcome_written: true
---

# Spike ci-tailscale-access/3

does tailscale/github-action@v4 join with only oauth-client-id, audience and tags from inside a composite action in an environment: lab job, and does a job without environment: lab fail to join?

The command exited 1:

```
/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ts12/check_run.sh 43754977347 join
```

## Outcome

Run 43754977347 in `JasperHG90/lab-auth-probe` (commit fc0c9f8): both jobs failed at join. Both the `environment: lab` job and the job without an environment got a 403 from the Tailscale token exchange (`failed to exchange JWT for access token ... Unauthorized`). So "no-env fails to join" means nothing here, because the lab job failed the same way.
The likely cause is the subject. The probe repo issues GitHub's immutable-ID `sub` (`repo:JasperHG90@8079803/lab-auth-probe@1459171707:environment:lab`, see spike 2), which the federated identity's subject `repo:JasperHG90/*:environment:lab` cannot match. This is not proven: the run never saw the trust credential's settings.
Settles risk 2: no, the risk is real as configured. Whether the action works from inside a composite step is still unshown. The fix is the federated identity's subject (for example `repo:JasperHG90@8079803/*:environment:lab`) or the repo's OIDC subject setting, then a rerun.
Also found: v4 always passes `--accept-routes` itself. Adding it to `args` makes `tailscale up` fail with "flag provided multiple times" (earlier run 43754902630), so the plan's action must leave `args` empty.
A local `./.github/actions/join` composite stood in for the cross-repo `uses:` call. The token and the join run in the caller's job either way.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/check_run.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ts12/check_run.sh`, which the command used
- `files/join-action.yml`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ts12/join-action.yml`, which the command used
- `files/reach.yaml`: a copy of `/tmp/claude-1000/-home-vscode-workspace/39954680-d360-4c77-9baf-bede6c6eafa0/scratchpad/spike-ts12/reach.yaml`, which the command used
