---
type: verdict
title: 'Verdict: dns-fallback plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of dns-fallback: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-23T22:14:10+00:00'
slug: dns-fallback
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

The approach works: spike 2 shows both NetworkManager versions parse and
document the `[global-dns]` drop-in, and NetworkManager writes resolv.conf
itself on both nodes. The scope (two hosts) is right. One gap changes what
ships: global DNS also replaces the connection's search domains, so the
planned file silently drops `search home` (p1). The eval also contradicts the
plan on whether a NetworkManager restart is allowed (p2). Both are revisions.
Neither invalidates the plan.

## Checked

- Spike dns-fallback/2 README, stdout.txt, files/check.sh and run.json: 14/14
  checks, a read-only parse of a copy of the real config plus the drop-in on
  both nodes, and man pages that document `servers`/`options` and the
  override. This settles R1 as far as it goes. The live rewrite is left to r4,
  and that is not plan-breaking.
- Live, read-only, on radxa and orange_pi_4a: nsswitch is
  `files mdns4_minimal [NOTFOUND=return] dns`, `nmcli dev show` gives
  IP4.DOMAIN `home`, and `getent hosts firebat` returns `firebat.home` (it
  works only through the search list).
- Inventory: radxa and orange_pi_4a are the only NetworkManager-plain-file
  hosts, and the three stub hosts are out of scope as the brief says. That
  scope is right.
- Public fallbacks and local names: glibc and Go's pure resolver move to the
  next server only on timeout or SERVFAIL/REFUSED, not on NXDOMAIN. A
  `*.home` lookup that times out at the router now gets NXDOMAIN from 1.1.1.1
  instead of a timeout. It fails either way, so nothing that works today
  breaks. Nothing in the repo points these nodes at Consul DNS through
  resolv.conf.
- Go (Bifrost) reads resolv.conf itself and honors server order, `timeout`
  and `attempts`, and it re-reads the file every few seconds. Three servers
  stay within glibc's MAXNS of 3. Worst case is about 6 s per name, against a
  failed request today.
- Podman: a host-network container still gets its own copy of resolv.conf
  (ResolvConfPath under /run/containers), made when the container is created.
  The Nomad podman driver creates a new container when a task starts, so a
  restart picks up the new file. r4 checks this after the real run, so it is
  build-time evidence, not a plan risk.
- 2.0 facts: P1, G1, O1 (behaviour) and O2 (support, needs O1) match the
  prose. O1's touches cover the playbook and the new test. The only mismatch
  is the missing search domain in p1.

## Findings

- p1: `[global-dns]` without `searches=home` drops the DHCP search domain on
  both nodes, so short names like `firebat` stop resolving. The plan should
  set `searches=home` (or say why short names do not matter), and r2 and r4
  should check for it.
- p2: r4 treats a NetworkManager restart as failure, while R1 treats it as an
  equal way to apply the file. Make the two agree.

## Notes

The NetworkManager docs say a SIGHUP/`nmcli general reload` re-reads the
config, and global DNS is among the settings NetworkManager applies on
reload. So a reload alone should probably be enough. That is for the build
and r4 to confirm, not a reason to spike before revising.
