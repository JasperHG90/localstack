---
type: eval
title: 'Eval: ci-lint-nomad-addr'
description: 'Definition of done for ci-lint-nomad-addr: 3 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T12:06:29+00:00'
slug: ci-lint-nomad-addr
signoff:
  signer: delegated:jasperginn@gmail.com/claude-opus-5-5
  hash: 0260962d36b002ba619a40c2fda3dd0fff910dcbf390a8257db4cd0597b8329f
  at: '2026-11-16T12:06:29+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: the ci lint job's prek step sets NOMAD_ADDR so terraform validate finds the nomad provider's address
  Fails when: the prek step has no NOMAD_ADDR in its env
- r2: the repo gates pass
  Fails when: just pre_commit exits non-zero
- r3 (judgment): after a push, the ci workflow run on main succeeds, lint and knowledge jobs
  Fails when: the run's lint or knowledge job fails
