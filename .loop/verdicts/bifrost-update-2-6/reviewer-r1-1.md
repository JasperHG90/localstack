---
type: verdict
title: 'Verdict: bifrost-update-2-6 reviewer round 1'
description: 'reviewer verdict for round 1 of bifrost-update-2-6: reject.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-27T10:39:41+00:00'
slug: bifrost-update-2-6
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The code change is correct and small. The pin moved to 2.6.0, the pin test
moved with it, and the gates and the live gateway check out. But row r2, the
pre-apply dump that the plan treats as the only rollback for 12 one-way store
migrations, was skipped. The migrations have now run, so no fix to this tree
can satisfy r2. The plan and the contract still require the dump, so the
operator has to rule on it: confirm the skip and amend or waive r2, or decide
on some other recovery. I am rejecting so the ticket goes to the operator
instead of starting a round the implementer cannot fix.

## Checked

- Diff: the worktree changes are uncommitted against HEAD 0ee1dc51, and HEAD
  matches main in every non-`.loop` path. I read all three changed files in
  full. `services.tf` changes one line (`bifrost_version = "2.6.0"`).
  `providers.tf` is untouched and stays at `~>0.1.0`.
- Gates: `loopctl gate stamp` from the worktree printed `pass gate
  pre_commit`, `pass gate cli_tests`, `pass eval-row r1`, `stamp green:
  6c5a81d787b9614df9dbaeb256eba1798bc49a258bb4e1a7a54c35d7da69aa4c`.
- r1: `cli/tests/test_bifrost_version.py` asserts that the pin list equals
  exactly `["2.6.0"]`, so a floating tag, a second pin or another version
  fails. It asserts `~>0.1.0` inside the bifrost provider block, and it
  asserts the `access_not_found` probe is present and `virtual_key_not_found`
  is absent. That covers every clause of fails_when.
- r2 (judgment): failed. No dump exists, and the component page records that
  there is no restore point. See f1.
- r3 (judgment): I re-ran `scripts/bifrost_smoke.py --base-url
  http://192.168.2.50:8080` myself. It printed gateway "v2.6.0" and ok for
  inference auth, metrics auth, no open admin path, the virtual keys surviving
  and embeddings reaching embark. `nomad job status bifrost` shows the job
  running with a healthy allocation, and `nomad job inspect` shows image
  `docker.io/maximhq/bifrost:v2.6.0`. I did not repeat the rerank, the Gemini
  chat or the second plan. I accept the implementer's recorded evidence for
  those (rerank 200 with scores, Gemini 2.5 flash chat 200, the second plan
  with no `bifrost_virtual_key` change). r3 passes.
- r4 (judgment): the page's lead names v2.6.0. The new paragraph covers both
  the one-way migrations and the `bifrost_upstream_latency_seconds` change. A
  grep for 2.3.1 outside `.loop/` finds only the component page, where it
  appears as history, and `.okf/log.md`. r4 passes, apart from the caveat in
  f2.
- Consistency: the pin test's docstring now names the 2.6 spikes and the
  one-way migrations. It is accurate enough.

## Findings

- f1: the contract row r2 and the plan's G2/O2 call for a dump taken before
  the apply. The implementer skipped it on an operator instruction that only
  the implementer has relayed. Neither the plan nor rows.json was changed to
  match. The apply has already run, so a dump taken now restores 2.6.0's
  schema and cannot take the store back to 2.3.1. This is a contract decision
  for the operator, so I set eval_row r2 and invalidates_plan. If the operator
  confirms the skip, amend or waive r2 (and plan step 3 / O2), and the rest of
  the change can land as it is.
- f2: the page says the x509 chains are accepted without saying the spike ran
  from the devcontainer. Only Gemini was called live from the node after the
  apply. Add that caveat, and split the two semicolon splices ("nobody has run
  that", "that wait is"). This does not block.

## Notes

The implementer's explanation for targeting the apply is wrong. They said this
branch predates the hermes-update change on main, but HEAD and main have the
same code. The hermes-update-0-23 change is live from its own worktree (ticket
stage `verifying`) and is not on main yet. Until that ticket lands, an
untargeted apply from main would also roll Hermes back. That does not affect
this tree, but whoever applies next should know it.
