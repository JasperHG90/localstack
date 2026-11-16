---
type: eval
title: 'Eval: ci-lint-tools'
description: 'Definition of done for ci-lint-tools: 3 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T11:26:08+00:00'
slug: ci-lint-tools
signoff:
  signer: delegated:jasperginn@gmail.com/claude-opus-5-5
  hash: 4366625ce6f10d0b9b8b4864939d42ae33888a99f538ca4edec65c446184a158
  at: '2026-11-16T11:26:08+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: the ci lint job installs Terraform 1.16.5 and Nomad 2.0.4 (the Nomad zip checked against the release SHA256SUMS) in steps before the prek step
  Fails when: either tool is missing, pinned to another version, installed after the prek step, or the Nomad download is not checksum-verified
- r2: the repo gates pass
  Fails when: just pre_commit exits non-zero
- r3 (judgment): after the operator pushes, the ci workflow run on main succeeds, both the lint and knowledge jobs
  Fails when: the run's lint or knowledge job fails
