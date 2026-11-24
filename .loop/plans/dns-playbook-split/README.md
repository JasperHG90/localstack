---
type: plan
title: 'Plan: dns-playbook-split'
description: Move the DNS fallback play out of the firewall playbook into its own playbook, so applying DNS never runs the firewall role.
tags:
- plan
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-24T06:59:41+00:00'
slug: dns-playbook-split
epic: null
depends_on: []
priority: null
schema_version: '2.0'
---

# dns-playbook-split

Relayed from: dns-fallback, the DNS play landed in the firewall playbook `bootstrap/playbooks/configure_network.yml`

## Intent

`dns-fallback` appended its play to `bootstrap/playbooks/configure_network.yml`,
which holds the ufw firewall plays. Running that playbook to apply DNS also
runs the firewall role on the same hosts. The play moves, byte for byte, to
`new:bootstrap/playbooks/configure_dns.yml`, and `configure_network.yml` goes
back to its firewall plays only. `bootstrap/justfile` runs the new playbook in
`bootstrap`. The test, ADR 0033, the two node pages and the bootstrap
component page name the new file.

It worked when `ansible-playbook playbooks/configure_dns.yml --list-tasks`
lists only the DNS task, `configure_network.yml` matches its state before
`dns-fallback`, and the gates pass.

## Problems

- P1: Applying the DNS fallback means running the firewall playbook, which also runs the ufw role on radxa and orange_pi_4a.

## Goals

- G1: The DNS fallback can be applied without touching the firewall.

## Outcomes

### O1: The DNS play lives in its own playbook and the firewall playbook is back to firewall only
- kind: behaviour
- goal: G1
- fixes: P1
- needs: none
- touches: `new:bootstrap/playbooks/configure_dns.yml`, `bootstrap/playbooks/configure_network.yml`, `bootstrap/justfile`, `cli/tests/test_bootstrap_dns_fallback.py`
- checked by: the test reading the new playbook, `--syntax-check` on both playbooks, and a diff of `configure_network.yml` against its state before `dns-fallback`
- seen by: operator

### O2: The knowledge bundle names the new playbook
- kind: support
- goal: G1
- fixes: P1
- needs: O1
- touches: `.okf/decisions/0033-networkmanager-nodes-get-public-fallback-resolvers.md`, `.okf/nodes/radxa-dragon-q6a.md`, `.okf/nodes/orangepi4a.md`, `.okf/components/bootstrap.md`
- checked by: `kmctl check`
- seen by: nobody

## Could invalidate this plan

- none
