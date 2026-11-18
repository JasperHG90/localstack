---
type: plan
title: 'Plan: ci-tailscale-access-reviewer-f3'
description: Deferred hardening from ci-tailscale-access, reviewer finding f3 in review round 1.
tags:
- plan
- hardening
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-15T22:23:42+00:00'
slug: ci-tailscale-access-reviewer-f3
status: draft
epic: ci-lab-access
depends_on: []
priority: null
---

# ci-tailscale-access-reviewer-f3

Relayed from: ci-tailscale-access, reviewer finding f3 in review round 1

## Intent

`jq -r .value` prints the string null when the OIDC response has no value field. The script then masks the word null in the whole log and posts null to Vault, which hides the real cause behind a Vault refusal. `jq -er '.value // empty'` would fail at the right step. at .github/actions/lab-auth/action.yml:53.

## Could invalidate this plan

- none
