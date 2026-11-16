---
type: plan
title: 'Plan: remove-hermes-interactive'
description: 'Delete the hermes-interactive workflow, whose agent can push to the local actions the lab-credentialed sync runs.'
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T12:04:36+00:00'
slug: remove-hermes-interactive
epic: null
depends_on: []
priority: null
---

# remove-hermes-interactive

Relayed from: none

## Intent

Delete `.github/workflows/hermes-interactive.yaml`. It runs on
`issue_comment` and `pull_request_review_comment` with `contents: write`, and
loads `JasperHG90/toiminnot/actions/hermes-interactive@main` unpinned. An agent
working over issue text could therefore push changes to `.github/actions/`,
which `.github/workflows/openviking-sync.yaml` runs by local path with the
lab's OIDC token. The workflow file is the only live reference to it. The
`OLLAMA_API_KEY` secret stays, because `.github/workflows/claude-ollama.yaml`
still uses it.

Outcome: `git ls-files .github/workflows` no longer lists
`hermes-interactive.yaml`, `rg hermes-interactive` finds no match outside
`.loop/`, and the gates pass.

## Could invalidate this plan

- none
