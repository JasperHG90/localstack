---
type: plan
title: 'Plan: ci-lint-nomad-addr'
description: Give terraform validate in the ci lint job the Nomad provider address it needs, from a placeholder NOMAD_ADDR.
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T12:06:27+00:00'
slug: ci-lint-nomad-addr
epic: null
depends_on: []
priority: null
---

# ci-lint-nomad-addr

<!-- This template was registered in planning. To capture an idea as a stub
instead (intent for later, promoted by the operator), write the plan with
`status: draft` in its front matter before running loopctl ticket register.
A hand-written plan's front matter needs type: plan, title, description and
slug; loopctl ticket register fills in generated. Optional: epic, depends_on,
priority, status, strictness and blocking. -->

Relayed from: ci-lint-tools, its live row r3 (run 43863164828 still red)

## Intent

After `ci-lint-tools`, every hook in the ci lint job passes except
`terraform-validate`: "The argument "address" is required" on
`provider "nomad"` in `deployments/infrastructure/machine_roles.tf:63`
(run 43863164828). Both roots' Nomad providers take their address from the
`NOMAD_ADDR` environment variable, which the devcontainer sets
(`.devcontainer/.env`), and the runner does not. `terraform validate` checks
that the argument is present but never connects, so the prek step in
`.github/workflows/ci.yaml` gets `NOMAD_ADDR: http://127.0.0.1:4646`, a
placeholder. Outcome: the workflow test asserts the prek step sets
`NOMAD_ADDR`; after a push, the ci run on main is green.

## Could invalidate this plan

- none
