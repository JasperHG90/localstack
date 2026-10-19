---
type: eval
title: 'Eval: docs-howto'
description: 'Definition of done for docs-howto: 6 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T17:51:03+00:00'
slug: docs-howto
signoff:
  signer: delegated:jasperginn@gmail.com/orchestrator
  hash: bbafc1c903542c27f35c9ad0d3521a5d8bfaf6055b1d7f79609af24228abb9d9
  at: '2026-10-19T17:51:03+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: every page in docs/how-to has front matter with description, stale_after and non-empty sources, and no other key than those and verified
  Fails when: a page other than README.md lacks one of the three keys, has empty sources, or carries another key
- r2: kmctl review due reports no notice for a page in docs/how-to
  Fails when: any notice has a path under docs/how-to/
- r3: kmctl check passes and prints no warning that names docs/how-to
  Fails when: kmctl check exits nonzero, or a warning line contains docs/how-to/
- r4: no backticked file name in docs/how-to is shorthand for a tracked file: each one that names a tracked file is written from the repo root
  Fails when: an inline-code token with a file extension does not exist from the repo root while a tracked file ends with /<token>
- r5 (judgment): each page in docs/how-to matches the code it describes, its build-history lines (ticket codes as provenance, at-the-time-of-writing state) listed in spike:docs-reconcile/1 are rewritten as current facts, and changed pages follow the plain-language and slop-scan rules
  Fails when: a reviewer finds a claim the code contradicts, a listed build-history line left as is, or a slop pattern the rules name
- r6: the note sync config and the notes folder are gone
  Fails when: docs/note-sync.toml or docs/notes exists
