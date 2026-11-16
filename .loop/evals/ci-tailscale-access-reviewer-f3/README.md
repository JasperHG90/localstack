---
type: eval
title: 'Eval: ci-tailscale-access-reviewer-f3'
description: 'Definition of done for ci-tailscale-access-reviewer-f3: 2 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T08:01:38+00:00'
slug: ci-tailscale-access-reviewer-f3
signoff:
  signer: delegated:jasperginn@gmail.com/claude-opus-5-5
  hash: db280dfdd295c5926f0c322fc756b1b08b08d0490a9d67d437b0a1fac3a0309b
  at: '2026-11-16T08:01:38+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: when GitHub's OIDC endpoint answers without a value field, the lab-auth login step fails with an error naming the OIDC token, before it masks anything or posts to Vault
  Fails when: with a stub curl whose OIDC response is {}, the step's script exits 0, sends a request to the Vault login URL, prints ::add-mask::null, or prints no error naming the OIDC token
- r2: the repo gates pass
  Fails when: just pre_commit exits non-zero
