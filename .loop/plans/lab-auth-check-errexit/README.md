---
type: plan
title: 'Plan: lab-auth-check-errexit'
description: Stop the lab-auth-check step dying on its first expected timeout under GitHub's bash -e.
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T06:41:51+00:00'
slug: lab-auth-check-errexit
epic: null
depends_on: []
priority: null
---

# lab-auth-check-errexit

<!-- This template was registered in planning. To capture an idea as a stub
instead (intent for later, promoted by the operator), write the plan with
`status: draft` in its front matter before running loopctl ticket register.
A hand-written plan's front matter needs type: plan, title, description and
slug; loopctl ticket register fills in generated. Optional: epic, depends_on,
priority, status, strictness and blocking. -->

Relayed from: ci-tailscale-access, found by its first live run (run 43818375094)

## Intent

The check step in `.github/workflows/lab-auth-check.yaml` runs under
`shell: bash`, which GitHub runs as `bash -e -o pipefail`. The first
closed-port probe returns 124 from `timeout`, the result the step wants, and
`-e` ends the script before `case` reads it, so a healthy run fails with exit
124. The step turns `-e` off, because it already counts failures in `fail`
itself. A test in `cli/tests/test_lab_auth_action.py` runs the step's script
under `bash --noprofile --norc -e -o pipefail` with stub `curl`, `timeout` and
`tailscale`, and asserts `OVERALL=PASS`. Done when that test passes and a
dispatch of lab-auth-check on main prints every row as PASS.

## Could invalidate this plan

- none
