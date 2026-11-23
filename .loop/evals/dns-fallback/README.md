---
type: eval
title: 'Eval: dns-fallback'
description: 'Definition of done for dns-fallback: 4 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-23T22:15:52+00:00'
slug: dns-fallback
signoff:
  signer: delegated:jasperginn@gmail.com/orchestrator
  hash: c9a7a1fb64d6399cb873ec8585cf82f9eb487a0552e6288bcb5cbd29ff4dc45c
  at: '2026-11-23T22:15:52+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: the network playbook still parses with the new play in it
  Fails when: ansible-playbook --syntax-check on bootstrap/playbooks/configure_network.yml exits nonzero
- r2: the new play targets only radxa and orange_pi_4a and writes a NetworkManager conf.d file whose [global-dns] has options timeout:1,attempts:2 and searches home, and whose [global-dns-domain-*] servers are 192.168.2.254, 1.1.1.1, 9.9.9.9 in that order
  Fails when: the test finds the play targeting any other host, a different server list or order, different options, or no searches=home
- r3: the knowledge bundle passes its checks with the node pages and the decision record updated
  Fails when: kmctl check exits nonzero
- r4 (judgment): after the operator runs the playbook, /etc/resolv.conf on radxa and orange_pi_4a lists 192.168.2.254, 1.1.1.1 and 9.9.9.9 with options timeout:1 attempts:2 and search home, getent hosts firebat still resolves on both, and after a Bifrost restart its container's /etc/resolv.conf shows the same
  Fails when: either node's resolv.conf lacks a fallback server, the options or search home, a short name such as firebat stops resolving, or Bifrost's container still lists only the router
