---
type: eval
title: 'Eval: tf-validate-partial-init'
description: 'Definition of done for tf-validate-partial-init: 4 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-11-16T14:55:49+00:00'
slug: tf-validate-partial-init
signoff:
  signer: delegated:jasperginn@gmail.com/claude
  hash: 9f1d6e64f4477657c9ffec6e886b8eb03e4cd473328ecd2e4bcd199b749992f6
  at: '2026-11-16T14:55:49+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: when the script's own init fails on a root that had no .terraform/, the script exits non-zero and the root has no .terraform/ afterwards
  Fails when: the script exits 0 after the failed init, or .terraform/ still exists in that root
- r2: a root that already has .terraform/ is validated without init and keeps its .terraform/, even when validate fails
  Fails when: the stub records an init call for that root, or its .terraform/ is gone after the run
- r3: a root with no .terraform/ whose init succeeds is initialized with -backend=false and then validated
  Fails when: the stub does not record init -backend=false followed by validate for that root, or the script exits non-zero
- r4: the repo gates pass
  Fails when: just pre_commit or the cli test suite exits non-zero
