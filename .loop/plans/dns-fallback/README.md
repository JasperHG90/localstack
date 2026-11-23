---
type: plan
title: 'Plan: dns-fallback'
description: Give the two NetworkManager nodes public fallback resolvers so one dropped query to the router no longer fails a lookup.
tags:
- plan
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-23T22:08:14+00:00'
slug: dns-fallback
epic: null
depends_on: []
priority: null
schema_version: '2.0'
---

# dns-fallback

Relayed from: none

## Intent

Bifrost on radxa failed a request with
`lookup ollama.com on 192.168.2.254:53: read udp ...: i/o timeout`. Bifrost
runs with `network_mode = "host"`
(`deployments/applications/services/bifrost.hcl`), so it resolves through
radxa's /etc/resolv.conf. On radxa and orange_pi_4a, NetworkManager writes
that file as a plain file holding only the router, `192.168.2.254`, which
drops a query now and then. firebat, jetson_nano and raspberry_pi_4b resolve
through a local stub at `127.0.0.53` and are out of scope.

A new play in `bootstrap/playbooks/configure_network.yml` drops a
NetworkManager config file on radxa and orange_pi_4a with a `[global-dns]`
section: the router first, then `1.1.1.1` and `9.9.9.9`, with
`options timeout:1 attempts:2`. A config file is used instead of
`nmcli connection modify` because the wired profile on both nodes is an
in-memory default NetworkManager generated (under /run/NetworkManager).

It worked when /etc/resolv.conf on both nodes lists the three servers and
the options, and Bifrost's container, once restarted, shows the same.

## Problems

- P1: radxa and orange_pi_4a list only the router in /etc/resolv.conf, so a query the router drops fails the lookup outright.

## Goals

- G1: A single dropped DNS answer from the router costs about a second, not a failed request, for host-network jobs on those nodes.

## Outcomes

### O1: The network playbook gives radxa and orange_pi_4a three resolvers with a short timeout
- kind: behaviour
- goal: G1
- fixes: P1
- needs: none
- touches: `bootstrap/playbooks/configure_network.yml`, `new:cli/tests/test_bootstrap_dns_fallback.py`
- checked by: `ansible-playbook --syntax-check`, a test that reads the play's hosts and file content, then /etc/resolv.conf on both nodes after the operator runs it
- seen by: operator

### O2: The knowledge bundle records the resolver set-up and why
- kind: support
- goal: G1
- fixes: P1
- needs: O1
- touches: `.okf/nodes/radxa-dragon-q6a.md`, `.okf/nodes/orangepi4a.md`, `.okf/decisions/`
- checked by: `kmctl check`
- seen by: nobody

## Could invalidate this plan

- R1: NetworkManager 1.36 (orange_pi_4a, `rc-manager=file`) or 1.46 (radxa) may not support a `[global-dns]` drop-in with `servers` and `options`, or may let the connection's DHCP DNS win over it; then the plan needs another mechanism. Settled by spike:dns-fallback/2: both versions document the keys, parse the drop-in from /etc/NetworkManager/conf.d/ into the merged config, say global servers override the active connection's, and write /etc/resolv.conf themselves. Options go in `[global-dns]` as a comma list (`options=timeout:1,attempts:2`). Whether a reload alone rewrites the live file is not plan-breaking (a NetworkManager restart applies the same file) and eval row r4 checks it after the real run.
