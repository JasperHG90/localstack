---
type: eval
title: 'Eval: onboard-repo-skill'
description: 'Definition of done for onboard-repo-skill: 5 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-18T14:47:56+00:00'
slug: onboard-repo-skill
signoff:
  signer: delegated:jasperginn@gmail.com/planner
  hash: 596367b2edb81a21ee592dee8d219ed003fb3289210d7fdf2ace1d724e433032
  at: '2026-11-18T14:47:56+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: the onboard-repo skill is tracked by git: .gitignore does not ignore .claude/skills/onboard-repo/SKILL.md, and its front matter has name onboard-repo and a description
  Fails when: git check-ignore matches the file, the file is missing, or the name or description is absent or different
- r2: every repository path the skill cites in backticks exists in the repository
  Fails when: a cited path does not exist
- r3: the caller workflow the skill prints uses only inputs the lab-auth action declares, passes no tailscale-client-id or tailscale-audience, sets environment lab and id-token write, and has no pull_request trigger
  Fails when: the workflow names an undeclared input, a Tailscale input, misses environment lab or id-token write, or triggers on pull_request or pull_request_target
- r4 (judgment): the skill applies only a saved plan it checked: it calls terraform plan -out and terraform apply on that file, never just apply or a bare terraform apply, and stops for the operator on any change outside the expected list
  Fails when: the skill runs just apply, a terraform apply without a plan file, pipes yes, or applies without the stop-on-unexpected check
- r5 (judgment): the skill covers every onboarding step: lab environment, vault_ci_callers entry, prefix map when syncing docs, the exact-list tests, both applies with a vault read check, commit through the loop, asking before push, and the pinned caller workflow; the how-to links to it
  Fails when: a step is missing or wrong, it pushes without asking, or the how-to does not link the skill
