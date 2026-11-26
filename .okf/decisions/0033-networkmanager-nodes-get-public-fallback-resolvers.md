---
type: decision
title: "ADR 0033: NetworkManager nodes get public fallback resolvers"
description: "radxa and orange_pi_4a list the router, then 1.1.1.1 and 9.9.9.9, through a NetworkManager global-DNS drop-in, so one dropped query no longer fails a lookup."
tags: [decision]
generated:
  by: process:kmctl/0.14.0
  at: 2026-11-23T22:17:00Z
status: stable
sources:
  - resource: "bootstrap/playbooks/configure_dns.yml"
---

# ADR 0033: NetworkManager nodes get public fallback resolvers

## Context

On 2026-11-23 a Bifrost request failed with
`lookup ollama.com on 192.168.2.254:53: read udp 192.168.2.50:38015->192.168.2.254:53: i/o timeout`.
Bifrost runs with `network_mode = "host"`, so it resolves through the node's
`/etc/resolv.conf`. On radxa and orange_pi_4a NetworkManager writes that file
as a plain file holding only the router, `192.168.2.254`. The router drops a
query now and then: 1 of 5 raw queries timed out once, while later runs of 40
and 100 saw none. With one server there is nothing to fall back to. firebat,
jetson_nano and raspberry_pi_4b resolve through a `127.0.0.53` stub instead.

## Decision

`bootstrap/playbooks/configure_network.yml` writes
`/etc/NetworkManager/conf.d/90-dns-fallback.conf` on radxa and orange_pi_4a.
Its `[global-dns-domain-*]` section lists the router, then `1.1.1.1` and
`9.9.9.9`. Its `[global-dns]` section sets `options=timeout:1,attempts:2` and
`searches=home`. A handler runs `nmcli general reload conf,dns-rc`.

Rejected: `nmcli connection modify` on the wired profile. On both nodes that
profile is an in-memory default NetworkManager generated under
`/run/NetworkManager/system-connections`, so a file Ansible owns is easier to
keep idempotent. Also rejected: `dns_servers` on the Bifrost job, which fixes
one job and not the node. Fixing the router was left out because the repo
does not manage it.

## Consequences

- A single dropped answer from the router costs about a second instead of a
  failed lookup. The worst case is about six seconds per name.
- Global DNS replaces the connection's search domains as well as its servers.
  `searches=home` keeps short names such as `firebat` resolving, and a
  change to the router's DHCP domain now needs a change to this file too.
- When the router stalls, names under `home` get NXDOMAIN from the public
  servers instead of a timeout. They failed in that case before, too.
- Podman copies `resolv.conf` into a container when it creates it, so
  host-network jobs on these nodes, Bifrost among them, see the new servers
  only after a restart.
- spike:dns-fallback/2 checked, read-only, that both NetworkManager versions
  (1.36 and 1.46) parse the drop-in. It did not check that a reload rewrites
  the live file: that is checked after the playbook runs.

## Correction, 2026-11-24

The play now lives in its own playbook,
`bootstrap/playbooks/configure_dns.yml`, which `just bootstrap` runs after
`configure_network.yml`. It first landed at the end of `configure_network.yml`,
the ufw firewall playbook, so applying DNS also ran the firewall role. The
play's content is unchanged.

## Correction, 2026-11-24

The last Consequences bullet says nobody checked that a reload rewrites the
live file. The playbook ran on both nodes on 2026-11-24, and the reload did
it. On radxa (1.46.0) and orange_pi_4a (1.36.6), `/etc/resolv.conf` changed
about two seconds after the drop-in was written, while NetworkManager had been
running since 2026-09-26, so no restart was involved. Both files now list
`192.168.2.254`, `1.1.1.1` and `9.9.9.9`, with `search home` and
`options timeout:1 attempts:2`, and `firebat` and `ollama.com` resolve on both
nodes.
