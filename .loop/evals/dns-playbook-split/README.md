---
type: eval
title: 'Eval: dns-playbook-split'
description: 'Definition of done for dns-playbook-split: 6 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-24T07:03:50+00:00'
slug: dns-playbook-split
signoff:
  signer: delegated:jasperginn@gmail.com/orchestrator
  hash: c1bffa10d6d9963797f2ca371f623ccdc77f15a94f5ba7068e35459a7e237fee
  at: '2026-11-24T07:03:50+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: the DNS test reads the play from configure_dns.yml and still pins hosts, server order, options and searches=home
  Fails when: the test does not read bootstrap/playbooks/configure_dns.yml, or any of its assertions fail
- r2: configure_network.yml is byte for byte its state before dns-fallback, so it holds only the firewall plays
  Fails when: git diff between 4ae98ed7^1 and the working tree shows any change to bootstrap/playbooks/configure_network.yml
- r3: both playbooks parse, and configure_dns.yml holds exactly one task, the DNS drop-in
  Fails when: either syntax check exits nonzero, or --list-tasks on configure_dns.yml shows any task other than 'Add public fallback resolvers after the router'
- r4: just bootstrap runs configure_dns.yml
  Fails when: the bootstrap recipe in bootstrap/justfile does not run playbooks/configure_dns.yml
- r5: the knowledge bundle passes its checks with ADR 0033 corrected by an appended section and the pages naming the new playbook
  Fails when: kmctl check exits nonzero
- r6 (judgment): ADR 0033's body above the new Correction section is unchanged; only its sources entry and the appended section differ
  Fails when: the diff of ADR 0033 against main touches any line other than the sources resource line and lines after the last existing line
