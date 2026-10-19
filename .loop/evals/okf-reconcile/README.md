---
type: eval
title: 'Eval: okf-reconcile'
description: 'Definition of done for okf-reconcile: 11 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T17:50:59+00:00'
slug: okf-reconcile
signoff:
  signer: delegated:jasperginn@gmail.com/orchestrator
  hash: dbac42457f9137fd8183732b4852d341e99b07641ae16e3b205d2fbffe3af47a
  at: '2026-10-19T17:50:59+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: kmctl check passes on the bundle with no warning line
  Fails when: kmctl check exits nonzero or prints any line starting with warning
- r2: kmctl review due reports no notices, and every due entry is due only because no person has verified it
  Fails when: the notices list is not empty, or any due entry has a reason other than unverified
- r3: every concept in components, nodes, practices, proposals and architecture names at least one source
  Fails when: any such concept other than index.md has no sources entry
- r4: the summary is written: at most 500 words, no kmctl template sentence left, and it links a concept in each section
  Fails when: the body is over 500 words, a template sentence remains, or a section among architecture, components, decisions, nodes, practices and proposals has no link from it
- r5: the manifesto is written: each of its three sections has content, every invariant carries a planned or enforced status, and the values are marked as a draft
  Fails when: a section is empty, an invariant line has neither planned nor enforced, or the Values section does not say it is a draft for the operator
- r6 (judgment): every enforced invariant names a test in cli/tests that passes, and every invariant id appears in the Depicts section of an architecture page
  Fails when: an enforced invariant names no test, its test fails or does not exist, or an invariant id is in no Depicts section
- r7: every concept the change touches is named in a line the change adds to .okf/log.md, and no earlier log line changes
  Fails when: a changed concept id is missing from the added log lines, or the diff removes or rewrites a log line
- r8: decision record bodies only grow by appended sections; front matter may change; ADR 0001 and 0014 are left to r9
  Fails when: the body after the front matter of any decision other than 0001 and 0014 is not a prefix-preserving extension of its body at the merge base
- r9: ADR 0014 is marked superseded by ADR 0001, and ADR 0001 names 0014
  Fails when: 0014 is not status deprecated or does not link 0001, or 0001 does not mention 0014
- r10: no agent marks a concept verified
  Fails when: the diff adds a verified entry anywhere under .okf
- r11 (judgment): each audited concept matches the code its sources name, R10 to R12 keyless MinIO for loki, registry and memex are recorded, and the drafted values come from the decisions and practices
  Fails when: a reviewer finds a concept claim the code contradicts, R10 to R12 are absent, or a value has no grounding in a decision or practice
