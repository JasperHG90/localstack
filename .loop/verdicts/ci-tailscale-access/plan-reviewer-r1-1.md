---
type: verdict
title: 'Verdict: ci-tailscale-access plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of ci-tailscale-access: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-15T21:40:10+00:00'
slug: ci-tailscale-access
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

The three listed risks are settled by real evidence. spike:ci-tailscale-access/6
shows a live tag:ci node reaches the three edge names on 443 and times out on
all five closed targets. spike:ci-tailscale-access/5 shows a federated join from
a composite action called by remote ref, in this repo, with a no-environment job
refused. spike:ci-tailscale-access/2 shows the caller's claims in the token and
a Vault role bound on all four refusing the wrong workflow, branch and missing
environment. One gap remains: the outcome depends on a push to origin/main and a
terraform apply the plan never names, so it fails until it says who does them
and when.

## Checked

- Read spikes 2, 5 and 6 (README, stdout, run.json) and the files spike 5 ran.
  Spike 2's limits (action in the same repo, keys fetched from the devcontainer)
  are named in the plan and left to the first lab-auth-check login, which is a
  fair handoff: a failure there would be fixed by building, not a redesign.
- Spike 5 confirms localstack issues the legacy subject
  (use_immutable_subject: false), which the federated identity matches. The
  immutable-subject gap is limited to other repos and sits outside this
  ticket's outcome, as the plan says.
- `git rev-list --count origin/main..main` is 213. No `.github/actions/`
  exists yet. The loop config's integration_branch is local main.
- `.github/workflows/claude-ollama.yaml` sets id-token: write at workflow level
  and has no `environment:`, so its token carries no environment claim. Spike 5
  shows such a token is refused by Tailscale, and spike 2 shows it is refused by
  a role bound on environment. The plan's bindings cover it.
- HAProxy routes vault.lab by Host header with no source ACL, so the login path
  is reachable as sys/health was in spike 6.
- identity.tf scopes MFA to the userpass mount, so the new mount is not caught.

## Findings

- p1: the push to origin/main and the terraform apply are missing from the plan,
  and the outcome cannot run without both.

## Notes

- The "What the action does" step 1 says to pass `--accept-routes`. Spike 5
  shows v4 adds it and a repeat fails, and the risk section already says to
  leave `args` empty. A builder will hit this on the first run, so it is not a
  finding.
- The `lab` Environment has no branch policy, so any branch in an operator repo
  whose workflow declares `environment: lab` can join the tailnet and reach the
  443 edge. Vault still gates tokens on ref. That matches the plan's stated
  split (Tailscale admits, Vault decides) and only the owner can push branches,
  so it is a choice the operator has made, not a risk to the plan. A main-only
  branch policy would move the non-main refusal from Vault to GitHub, which
  would change how the outcome's refusal check reads.
- The throwaway branch spike/lab-auth-reach on origin still holds the spike
  workflow and join action. Deleting it is cleanup, not plan scope.
