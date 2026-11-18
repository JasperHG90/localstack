---
type: eval
title: 'Eval: lab-auth-immutable-subject'
description: 'Definition of done for lab-auth-immutable-subject: 6 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-18T13:18:18+00:00'
slug: lab-auth-immutable-subject
signoff:
  signer: delegated:jasperginn@gmail.com/planner
  hash: 37ad7485d9973595d474b29cd3a177710ec032952e31a58e7c32b401506d1979
  at: '2026-11-18T13:18:18+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: the lab-auth action reads the job's OIDC sub and hands tailscale/github-action the new credential (client T4Y1pq366F11CNTRL-kysCUqvnvH11CNTRL) for a repo:JasperHG90@8079803/ subject and the old one (client T4Y1pq366F11CNTRL-kcbC29ubym11CNTRL) for a repo:JasperHG90/ subject
  Fails when: either subject format gets the other format's client ID or audience, or the step exits nonzero for a valid token
- r2: a caller that passes tailscale-client-id and tailscale-audience gets exactly those values, whatever its subject format
  Fails when: an explicit input is replaced by the picked credential
- r3: vault_ci_callers holds loop-engineering-harness-openviking-sync, and its rendered jwt-github role binds repository JasperHG90/loop-engineering-harness, ref refs/heads/main, environment lab and workflow_ref JasperHG90/loop-engineering-harness/.github/workflows/openviking-sync.yaml@refs/heads/main, with ov_sync on
  Fails when: the entry is missing, any bound claim differs, or ov_sync is off
- r4: the ov-sync consumer's prefix map sends JasperHG90/loop-engineering-harness/ to viking://user/jasper/resources/projects/loop-engineering-harness/ and keeps the localstack entry
  Fails when: the harness prefix is missing or maps elsewhere, or the localstack entry changed
- r5 (judgment): the how-to no longer tells the reader to create a second Tailscale identity or pass Tailscale inputs, the reference names how the action picks the credential, and a new decision record amends ADR 0027's second-identity consequence without editing ADR 0027
  Fails when: a doc still instructs creating the identity or passing the inputs, the reference omits the picking rule, or ADR 0027's text changed
- r6 (judgment): both Terraform roots are applied, and vault read auth/jwt-github/role/loop-engineering-harness-openviking-sync shows all four bound claims
  Fails when: either apply was not run or failed, or the role is absent from Vault
