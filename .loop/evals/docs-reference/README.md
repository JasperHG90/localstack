---
type: eval
title: 'Eval: docs-reference'
description: 'Definition of done for docs-reference: 5 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T18:04:02+00:00'
slug: docs-reference
signoff:
  signer: delegated:jasperginn@gmail.com/orchestrator
  hash: d99bfc1d09fbf958dda397bfe054b3abdb8f3082fb3a163ae09a689a125660d0
  at: '2026-10-19T18:04:02+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: every page in docs/reference has front matter with description, stale_after and non-empty sources, and no other key than those and verified
  Fails when: a page other than README.md lacks one of the three keys, has empty sources, or carries another key
- r2: kmctl review due reports no notice anywhere: no page in docs/reference names a missing source, and no .okf concept is left pointing at a page this change renamed or deleted
  Fails when: the notices list from kmctl review due --json is not empty
- r3: kmctl check passes and prints no warning that names docs/reference
  Fails when: kmctl check exits nonzero, or a warning line contains docs/reference/
- r4: no backticked file name in docs/reference is shorthand for a tracked file: each one that names a tracked file is written from the repo root
  Fails when: an inline-code token with a file extension, outside fenced code and not on the allow-list of other-codebase names (embark.json), does not exist from the repo root while a tracked file ends with /<token>
- r5 (judgment): each page in docs/reference matches the code it describes, its build-history lines (ticket codes as provenance, at-the-time-of-writing state) listed in spike:docs-reconcile/1 are rewritten as current facts, and changed pages follow the plain-language and slop-scan rules
  Fails when: a reviewer finds a claim the code contradicts, a listed build-history line left as is, or a slop pattern the rules name
