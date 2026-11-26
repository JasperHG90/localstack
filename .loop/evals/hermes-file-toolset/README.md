---
type: eval
title: 'Eval: hermes-file-toolset'
description: 'Definition of done for hermes-file-toolset: 2 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-26T13:49:10+00:00'
slug: hermes-file-toolset
signoff:
  signer: delegated:jasperginn@gmail.com/claude
  hash: 5c4ed5656889833e57c8695e0c85f9ad6c319bfa01093423d981ce0238779b16
  at: '2026-11-26T13:49:10+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: Every entry in both platform_toolsets lists (email, telegram) in the config.yaml that deployments/applications/services/hermes.hcl renders is a toolset name hermes-agent defines, so the file toolset is named `file`.
  Fails when: any platform_toolsets entry, including `files`, is not in the test's list of upstream toolset names, or `file` is missing from either list
- r2 (judgment): After the apply, the hermes gateway log has no 'references unknown toolset' warning, and a Telegram request to read a file on the data volume is answered using a file tool.
  Fails when: the warning still appears, the request gets no file tool, or the evidence is not recorded in the review
