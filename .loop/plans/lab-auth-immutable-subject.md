---
type: plan
title: 'Plan: lab-auth-immutable-subject'
description: The lab-auth action picks the Tailscale credential that matches the caller's GitHub OIDC subject format, and loop-engineering-harness gets its Vault role and ov-sync prefix.
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-18T13:05:25+00:00'
slug: lab-auth-immutable-subject
epic: null
depends_on: []
priority: null
---

# lab-auth-immutable-subject

Relayed from: none

## Intent

GitHub gives repositories created after 2026-07-15 an OIDC subject with
fixed IDs (`repo:JasperHG90@8079803/<repo>@<id>:...`). The Tailscale
credential in `.github/actions/lab-auth/action.yml` trusts only the old
subject (`repo:JasperHG90/*:environment:lab`), so a newer repository, such as
`JasperHG90/loop-engineering-harness`, gets a 403 when it tries to join. The
operator created a second credential today with subject
`repo:JasperHG90@8079803/*:environment:lab` (client ID
`T4Y1pq366F11CNTRL-kysCUqvnvH11CNTRL`).

This ticket:

1. Makes the action read the job's OIDC `sub` before it joins the tailnet
   and pick the credential that matches it: the old one for
   `repo:JasperHG90/...`, the new one for `repo:JasperHG90@8079803/...`.
   `tailscale-client-id` and `tailscale-audience` still override when a
   caller passes them. No caller passes Tailscale values any more.
2. Adds `loop-engineering-harness-openviking-sync` to `vault_ci_callers` in
   `deployments/infrastructure/variables.tf` (repository
   `JasperHG90/loop-engineering-harness`, `refs/heads/main`, environment
   `lab`, workflow `openviking-sync.yaml`, `ov_sync = true`), and the prefix
   `JasperHG90/loop-engineering-harness/` to the consumer's map in
   `deployments/applications/services.tf`, then applies both roots.
3. Updates `cli/tests/test_lab_auth_action.py`,
   `docs/how-to/authenticate-a-github-workflow-to-the-lab.md` (drop the
   "create a second identity" step), `docs/reference/github-actions.md`, and
   records a decision that amends ADR 0027's consequence about the second
   identity.

Outcome: a `lab` job in an immutable-subject repository joins the tailnet
through the action with no Tailscale inputs, and
`vault read auth/jwt-github/role/loop-engineering-harness-openviking-sync`
shows all four bound claims.

## Could invalidate this plan

- The new credential may not admit an immutable-subject repository's `lab`
  job, or a composite step may not be able to read `sub` and pass the chosen
  credential to `tailscale/github-action`. Either breaks item 1.
  Settled by spike:lab-auth-immutable-subject/1: in `JasperHG90/lab-auth-probe`
  a composite step read `sub`, picked the new credential, and the `lab` job
  joined and reached Vault. A job without `environment: lab` still got a
  403. The old-format branch did not run there; `localstack`'s
  `lab-auth-check.yaml` covers it after merge.
