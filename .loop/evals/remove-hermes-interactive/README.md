---
type: eval
title: 'Eval: remove-hermes-interactive'
description: 'Definition of done for remove-hermes-interactive: 3 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T12:05:54+00:00'
slug: remove-hermes-interactive
signoff:
  signer: delegated:jasperginn@gmail.com/claude
  hash: 2ea5134d4c7cbc46a7ac15c5bc56b08e593c1baec28b9e846d1db574386463e4
  at: '2026-11-16T12:05:54+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: the hermes-interactive workflow is gone and nothing outside .loop/ refers to it
  Fails when: git tracks .github/workflows/hermes-interactive.yaml, or git grep finds 'hermes-interactive' in any tracked file outside .loop/
- r2: the OLLAMA_API_KEY secret is still used by claude-ollama, so removing hermes leaves no orphaned secret to delete
  Fails when: .github/workflows/claude-ollama.yaml no longer references secrets.OLLAMA_API_KEY
- r3: the repo gates pass
  Fails when: just pre_commit or the cli test suite exits non-zero
