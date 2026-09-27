---
type: decision
title: "ADR 0003: Lab names resolve from public DNS, not a local resolver"
description: Names under lab.orangecluster.nl are public A records pointing at a private address, and the dnsmasq split-horizon resolver on firebat was removed. This trades a little disclosure for household DNS that does not depend on the cluster.
generated:
  by: claude-opus/5.5
  at: 2026-09-26
tags: [adr, decision, dns, edge]
status: stable
decision_status: Accepted
decided_on: 2026-07-26
sources:
  - id: dns
    resource: git:3ec5d1e:docs/dns.md
    last_modified: 2026-07-26
---

# ADR 0003: Lab names resolve from public DNS, not a local resolver

- Status: Accepted
- Date: 2026-07-26

> Written retrospectively from docs/dns.md, dated 2026-07-26.

## Context

A dnsmasq instance on firebat used to answer this zone, with nothing published
publicly. That arrangement is called split horizon.

Making it work for every device meant pointing the router's DHCP at it, which
would have made the whole household's internet depend on a machine in the
cluster: firebat rebooting, or Nomad rescheduling the allocation, would have
taken DNS down for everyone.

## Decision

Publish two A records in the TransIP control panel, `*.lab` and `lab`, both
answering `192.168.2.30`, and remove the local resolver.

Rejected alternative: a second instance on another node would have fixed the
availability problem while keeping the zone private, but the operator declined
to tie household DNS to cluster machines at all.

## Consequences

Public records trade a little disclosure for that independence. Nothing in the
house now depends on the cluster to resolve anything.

What a remote attacker gains is information rather than access: the internal
address, and the fact that the lab zone exists. The address is RFC1918, so
reaching the cluster still requires being on the LAN or the tailnet.

Some resolvers and routers refuse public DNS answers that point into private
address ranges. Where such filtering is enabled, lab names will not resolve,
and there is no longer a local resolver to fall back on.

The user-facing account of the exposure is
`docs/explanation/public-lab-dns.md`, and the records are
`docs/reference/dns.md`.
