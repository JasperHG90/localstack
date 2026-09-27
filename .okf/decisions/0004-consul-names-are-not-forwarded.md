---
type: decision
title: "ADR 0004: The .consul zone is not forwarded to Consul"
description: LAN clients cannot resolve .consul names, and that stays so. Forwarding the zone would hand out container bridge addresses that connect to nothing, so clients use node addresses and ports instead.
generated:
  by: claude-opus/5.5
  at: 2026-09-26
tags: [adr, decision, dns, consul, nats]
status: stable
decision_status: Accepted
decided_on: 2026-07-26
sources:
  - id: dns
    resource: git:3ec5d1e:docs/dns.md
    last_modified: 2026-07-26
---

# ADR 0004: The .consul zone is not forwarded to Consul

- Status: Accepted
- Date: 2026-07-26

> Written retrospectively from docs/dns.md, dated 2026-07-26.

## Context

`docs/reference/nats.md` and
[the CDC bridge proposal](/proposals/postgres-nats-cdc-bridge.md) advertise
`nats://nats.service.localstack.consul:4222` as a client URL in several
places. That does not work. Consul answers `.consul` names on port 8600 only,
so an ordinary client never resolves them.

## Decision

Do not forward the `.consul` zone to Consul. Use the node address and port.

Rejected alternative: forwarding the zone to Consul. Consul hands out the
container bridge address for bridge-networked services, so
`nats.service.localstack.consul` resolves to `10.88.0.83`, which is not
routable from the LAN and is unreachable even from firebat, while
`192.168.2.50:4222` is open. Forwarding would have replaced an honest
NXDOMAIN with an answer that connects to nothing and times out.

## Consequences

`.consul` names stay unusable from the LAN. Correcting the NATS documents, or
making Consul advertise routable addresses, belongs to whoever owns NATS.
The user-facing note is in `docs/reference/dns.md`.
