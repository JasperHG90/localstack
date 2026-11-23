---
type: verdict
title: 'Verdict: dns-fallback plan-reviewer round 2'
description: 'plan-reviewer verdict for round 2 of dns-fallback: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-23T22:15:35+00:00'
slug: dns-fallback
pass: plan-reviewer
round: 2
body_schema: verdict/1
---

## Summary

Both round 1 findings are resolved. The plan adds `searches=home` to
`[global-dns]` and explains why, and r2 and r4 check for it, with r4 also
checking that `getent hosts firebat` still resolves. r4 no longer counts a
NetworkManager restart as failure, which matches R1. I found no new risk that
could break the plan.

## Checked

- Plan, draft eval rows, round 1 verdict and spike dns-fallback/2 (README and
  run.json). The spike still settles R1 as far as key support and parsing go.
- Live, read-only: `man NetworkManager.conf` on radxa (NM 1.46.0) and
  orange_pi_4a (NM 1.36.6) documents `searches` under the `[global-dns]`
  section on both, so the new key is supported on both versions. Both
  /etc/resolv.conf files still read `search home` plus only 192.168.2.254.
- Repo: `bootstrap/playbooks/configure_network.yml` exists (firewall plays for
  manager and worker), and radxa and orange_pi_4a are inventory host names in
  `bootstrap/inventory/cluster.ini`, so a play scoped to those two hosts is
  possible. Both node pages named in O2's touches exist.
- 2.0 facts: P1, G1, O1 (behaviour, now including search home) and O2
  (support, needs O1) match the prose. O1's touches cover the playbook and the
  new test.

## Findings

- p1: resolved. `searches=home` is in the plan, and r2 and r4 check for it.
- p2: resolved. r4 and R1 agree that a restart is an acceptable way to apply
  the file.

## Notes

The Intent prose says the servers go in the `[global-dns]` section. In
NetworkManager they go in `[global-dns-domain-*]`, as the spike's merged
config and r2 both say. r2 will catch a builder who follows the prose
literally, so this is not plan-breaking. Read the servers line as
`[global-dns-domain-*]`.
