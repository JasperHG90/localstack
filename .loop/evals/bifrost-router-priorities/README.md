---
type: eval
title: 'Eval: bifrost-router-priorities'
description: 'Definition of done for bifrost-router-priorities: 3 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T14:58:05+00:00'
slug: bifrost-router-priorities
signoff:
  signer: delegated:jasperginn@gmail.com/claude-opus-5-5
  hash: c6939c91b2266500e3e8c6beaf19a01d7d2d53ca16926260c4e1ff72d7ce5e58
  at: '2026-11-16T14:58:05+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: every routing rule in bifrost.hcl has a priority above 3, the passthrough rule has the lowest priority among them, and no two share one
  Fails when: a rule's priority is 3 or below, the passthrough is not first among the router rules, or two rules share a priority
- r2: the repo gates and the CLI test suite pass
  Fails when: just pre_commit or uv run --directory cli pytest exits non-zero
- r3 (judgment): after the operator applies, Bifrost boots and stays healthy, the Claude Code haiku/sonnet/opus/fable rules still route, and scripts/bifrost_smoke.py passes with BIFROST_ROUTER_VK set
  Fails when: Bifrost fails to boot, a Claude Code alias no longer reaches its Ollama model, or the smoke script fails
