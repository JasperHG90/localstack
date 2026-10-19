---
type: eval
title: 'Eval: docs-reference'
description: 'Definition of done for docs-reference: 5 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T17:51:06+00:00'
slug: docs-reference
signoff:
  signer: delegated:jasperginn@gmail.com/orchestrator
  hash: fd700de7e85c3ae4a5884fc8544183af28a886031a13f26e9e1eed91071a72e9
  at: '2026-10-19T17:51:06+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: every page in docs/reference has front matter with description, stale_after and non-empty sources, and no other key than those and verified
  Fails when: a page other than README.md lacks one of the three keys, has empty sources, or carries another key
- r2: kmctl review due reports no notice for a page in docs/reference
  Fails when: any notice has a path under docs/reference/
- r3: kmctl check passes and prints no warning that names docs/reference
  Fails when: kmctl check exits nonzero, or a warning line contains docs/reference/
- r4: no backticked file name in docs/reference is shorthand for a tracked file: each one that names a tracked file is written from the repo root
  Fails when: an inline-code token with a file extension does not exist from the repo root while a tracked file ends with /<token>
- r5 (judgment): each page in docs/reference matches the code it describes, its build-history lines (ticket codes as provenance, at-the-time-of-writing state) listed in spike:docs-reconcile/1 are rewritten as current facts, and changed pages follow the plain-language and slop-scan rules
  Fails when: a reviewer finds a claim the code contradicts, a listed build-history line left as is, or a slop pattern the rules name
