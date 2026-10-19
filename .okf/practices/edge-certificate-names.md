---
type: practice
title: Edge certificate names must be flat and under a real domain
description: "The edge's earlier `*.localstack` wildcard failed in every client even for flat names, because a wildcard has to sit at least two labels above the root."
tags: [tls, haproxy, edge, dns, lesson]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-26
sources:
  - id: acme-jobspec
    resource: deployments/infrastructure/services/acme.hcl
  - id: acme-domain-variable
    resource: deployments/infrastructure/variables.tf
  - id: haproxy-jobspec
    resource: deployments/infrastructure/services/haproxy.hcl
---

# Edge certificate names must be flat and under a real domain

A new edge hostname has to be flat, one label in front of
`lab.orangecluster.nl`, because a TLS wildcard matches a single label. That
rule is in `docs/how-to/add-a-service-to-the-edge.md`. The code site is
`deployments/infrastructure/services/acme.hcl`, which asks lego for
`*.${acme_domain}` and the bare `${acme_domain}` and nothing deeper, so the
certificate the edge serves does not match a name such as
`a.b.lab.orangecluster.nl`.

The edge's previous certificate failed for a different reason worth knowing:
it was issued for `*.localstack`, and a wildcard has to sit at least two
labels above the root. `grafana.localstack` was already flat and still no
client would accept it. Flat names are necessary, not sufficient, and the
domain underneath has to be a real one.
