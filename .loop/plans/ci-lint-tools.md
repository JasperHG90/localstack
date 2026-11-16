---
type: plan
title: 'Plan: ci-lint-tools'
description: Install pinned nomad and terraform in the ci lint job so prek's hooks run on GitHub's runner.
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T11:26:05+00:00'
slug: ci-lint-tools
epic: null
depends_on: []
priority: null
---

# ci-lint-tools

<!-- This template was registered in planning. To capture an idea as a stub
instead (intent for later, promoted by the operator), write the plan with
`status: draft` in its front matter before running loopctl ticket register.
A hand-written plan's front matter needs type: plan, title, description and
slug; loopctl ticket register fills in generated. Optional: epic, depends_on,
priority, status, strictness and blocking. -->

Relayed from: none

## Intent

`.github/workflows/ci.yaml` runs `uvx prek@0.5.5 run --all-files` on
`ubuntu-latest`, and the job has failed on main since at least 2026-10-20
(runs 39493835054, 43818142122, 43826394019, 43826973355):
`Failed to run hook nomad-fmt ... No such file or directory`. The
`language: system` hooks in `.pre-commit-config.yaml` expect `nomad`
(`nomad-fmt`) and `terraform` (`terraform-fmt`, `terraform-validate` through
`scripts/tf_validate.sh`) on PATH, and the runner has neither. uv comes from
`astral-sh/setup-uv`, and prek installs Go for the `golang` hook itself.

The lint job installs Terraform 1.16.5 with `hashicorp/setup-terraform` and
Nomad 2.0.4 from releases.hashicorp.com, checked against the release's
SHA256SUMS, before prek runs. Those are the versions in the devcontainer.
Every provider either root needs is on the public registry, so
`terraform init -backend=false` works on a fresh runner.

Outcome: a test asserts the lint job installs both at those versions before
the prek step; after the operator pushes, the `ci` run on main is green.

## Could invalidate this plan

- none
