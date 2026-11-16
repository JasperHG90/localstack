---
type: eval
title: 'Eval: lab-auth-check-errexit'
description: 'Definition of done for lab-auth-check-errexit: 3 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T06:42:13+00:00'
slug: lab-auth-check-errexit
signoff:
  signer: delegated:jasperginn@gmail.com/claude-opus-5-5
  hash: 9d69d8a6a9a1f0dd3f3b7630f6c716573baf89036f5d7bb2003363ce721e7f82
  at: '2026-11-16T06:42:13+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: the lab-auth-check check step, run as GitHub runs shell: bash (bash --noprofile --norc -e -o pipefail), reaches OVERALL=PASS when every closed-port probe times out and every edge answers
  Fails when: the step's script exits before printing OVERALL, or prints fewer than five 'timed out' rows, under bash -e -o pipefail with stub curl, timeout and tailscale
- r2: the repo gates pass
  Fails when: just pre_commit exits non-zero
- r3 (judgment): a workflow_dispatch run of lab-auth-check on main prints PASS for the token, the three edges and the five closed ports, and a dispatch from a throwaway branch is refused at the Vault login
  Fails when: either run's log does not show it
