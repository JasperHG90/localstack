---
type: node
title: firebat, the manager
description: "firebat (192.168.2.30) is the only amd64 node and the single copy of every control-plane service: Consul server, Vault, Nomad server, the Tailscale route and the HAProxy edge, plus Postgres. Its CPU is fully reserved, so new jobs go elsewhere, and when it goes down the whole cluster loses its control plane and every lab name."
tags: [node, firebat, manager, amd64, consul, vault, nomad, haproxy, postgres, tailscale]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: inventory
    resource: git:3ec5d1e:bootstrap/inventory/cluster.ini
  - id: server-playbook
    resource: git:3ec5d1e:bootstrap/playbooks/configure_hashistack_server.yml
  - id: nomad-server-template
    resource: git:3ec5d1e:bootstrap/roles/nomad_server/templates/nomad.hcl.j2
  - id: consul-server-template
    resource: git:3ec5d1e:bootstrap/roles/consul_server/templates/consul.hcl.j2
  - id: vault-server-tasks
    resource: git:3ec5d1e:bootstrap/roles/vault_server/tasks/main.yml
  - id: configure-network
    resource: git:3ec5d1e:bootstrap/playbooks/configure_network.yml
  - id: infra-services
    resource: git:3ec5d1e:deployments/infrastructure/services.tf
  - id: haproxy-jobspec
    resource: git:3ec5d1e:deployments/infrastructure/services/haproxy.hcl
  - id: postgres-jobspec
    resource: git:3ec5d1e:deployments/infrastructure/services/postgres.hcl
  - id: registry-jobspec
    resource: git:3ec5d1e:deployments/applications/services/registry.hcl
  - id: backups-off-firebat
    resource: git:4b0af46:deployments/infrastructure/services/backup-postgres.hcl
  - id: U1-upgrade-pin-hashistack-versions
    resource: loop:U1-upgrade-pin-hashistack-versions
  - id: U3-upgrade-nomad-2x
    resource: loop:U3-upgrade-nomad-2x
  - id: U4-upgrade-consul-2x
    resource: loop:U4-upgrade-consul-2x
  - id: breakglass-runbook
    resource: git:3ec5d1e:cli/src/localstack_cli/commands/breakglass_runbook.md
---

# firebat, the manager

firebat is the one host in the Ansible `[manager]` group and the only place
the control plane runs. Every other node is a Nomad and Consul client that
dials it. The cross-node picture is [node placement](/nodes/placement.md).

| Fact | Value | Source |
|---|---|---|
| Names | inventory `firebat`, Nomad and Consul `firebat`, SSH user `firebat` | `bootstrap/inventory/cluster.ini` |
| Address | `192.168.2.30` | same |
| Board | not recorded in the repo | |
| OS and arch | Ubuntu noble, amd64 (the only amd64 node) | U1 plan, read over SSH on 2026-07-31 |
| Disk | `/` had 75G free, `/var/lib/consul` 66M | U4 plan |
| Nomad | server (`bootstrap_expect = 1`) and client, pool `default`, no node class | `bootstrap/roles/nomad_server/templates/nomad.hcl.j2` |
| Tailnet | the only node on it, advertising `192.168.2.0/24` | [Tailscale subnet router](/components/tailscale-subnet-router.md) |

## What runs here

Outside Nomad, from Ansible:

- **Consul server**, `bootstrap_expect = 1`, UI on, data in `/var/lib/consul`
  (`bootstrap/roles/consul_server/templates/consul.hcl.j2`). It is the only
  Consul server.
- **Vault**, storage `consul` at `127.0.0.1:8500`, plain HTTP on 8200. The
  unseal keys and root token are in `/opt/vault/init.json` on this same disk.
- **Nomad server and client** in one agent. Its `client` block has no
  `reserved` stanza, unlike the workers, and its Consul address is
  `192.168.2.30:8500` rather than loopback.
- **Tailscale**, the subnet router. The workers stop `tailscaled`.

Nomad jobs pinned here by a literal `value = "firebat"`:

| Job | Why here |
|---|---|
| `haproxy` (80, 443, 8404) | No comment records the first reason. It cannot move now without a DNS change: lab names resolve publicly to `192.168.2.30` ([ADR 0003](/decisions/0003-lab-names-resolve-from-public-dns.md)). See [the edge proxy](/components/edge-proxy.md). |
| `postgres` and its exporter sidecar (5432, 9187) | No comment or ticket records why. The `postgres` host volume holds it here now. See [Postgres](/components/postgres.md). |

The system jobs `node-exporter` and `alloy` run here as on every node.

Host volume: `postgres`, 10 to 100 GiB.

## Firewall rules that name this node

| Rule | Where |
|---|---|
| 22 from the LAN and the tailnet, then Consul, Vault, Nomad and `20000:32000` from the LAN | `bootstrap/playbooks/configure_network.yml`, manager play |
| `postgres` 5432 from the LAN | `deployments/infrastructure/services.tf` |
| `postgres_exporter` 9187 and `node_exporter_firebat` 9100 from `.47` | same |
| `haproxy` 80, 443 and 8404 from the LAN and the tailnet | same |
| Still live, no longer declared: 53/udp and 53/tcp from the retired dnsmasq | [host firewall](/components/host-firewall.md), N2 |

The Consul ports are 8300, 8301, 8500 and 8600, Vault's are 8200 and 8201,
and Nomad's are 4646 to 4648.

As a source address, `192.168.2.30` appears in rules on the other nodes for
two reasons:

- **HAProxy is the only caller** of oauth2-proxy (4180, 4181), ov-dash
  (4182), the Hermes dashboard (9119) and the registry (5000).
- **HAProxy is one of several callers** of hermes 8642, OpenViking 1933,
  Tempo's query API 3200 and Prometheus 9090.
- **firebat's own Alloy** is why `.30` is on Loki 3100 and Tempo's OTLP
  4317 and 4318, which admit all five nodes.

Moving the edge off this address means rewriting the first two groups. The
third stays as long as Alloy runs here.

## What dials it by literal address

`192.168.2.30` is written into more places than any other address:

- The Ansible playbooks that render every agent's config:
  `bootstrap/playbooks/configure_hashistack_server.yml` and
  `bootstrap/playbooks/configure_hashistack_clients.yml` (Vault address,
  Consul and Nomad `retry_join`).
- Both Terraform roots' state backend
  (`deployments/*/vars/backend-config.hcl`) and the applications root's
  Consul provider (`deployments/applications/providers.tf`).
- HAProxy's own `vault`, `nomad` and `consul` backends.
- Prometheus scrape targets for Nomad, Consul, HAProxy stats and
  postgres_exporter, and its `consul_address`.
- `dash`'s `nomad_addr` and `consul_addr`, hermes's `NOMAD_ADDR` and
  `CONSUL_ADDR`, the `acme` job's `VAULT_ADDR`, and `backup-postgres`'s
  `postgres_host` (`deployments/infrastructure/services.tf`).
- The CLI's breakglass addresses
  (`cli/src/localstack_cli/commands/breakglass.py`).

The applications root finds Postgres through the Consul catalog
(`data.consul_service.postgres`) instead, so those consumers follow a move.

## Capacity: this node is full

firebat has about 3200 MHz of allocatable CPU (commit `4b0af46`). Postgres
reserves 2200 MHz across its two tasks and HAProxy 500. With node-exporter
and Alloy at 200 each, that commits 3100. That has sent three jobs
elsewhere:

- `backup-postgres` and `backup-minio` were pinned here until 2026-07-07. The
  700 MHz backup group could not place, and with `prohibit_overlap = true` the
  stuck child blocked every nightly run for about two months. Commit `4b0af46`
  moved both to [radxa-dragon-q6a](/nodes/radxa-dragon-q6a.md).
- The oauth2-proxy jobs went to radxa because about 100 MHz was left when L1
  ran ([the edge proxy](/components/edge-proxy.md)).
- The registry went to [ubuntu](/nodes/ubuntu.md): the scheduler refused to
  place it here (`deployments/applications/services/registry.hcl`, the comment
  above its constraint).

A new job pinned here will very likely not place.

## Quirks and traps

- **The Nomad advertise address was a coin flip.** On 2026-07-31
  unattended-upgrades patched openssl and restarted Nomad, which advertised
  the podman bridge `10.88.0.1`. Four of five nodes went `down` while the
  HTTP API kept answering, and running allocations on the workers kept
  running (U3 plan). The `advertise` block in both Nomad templates fixes it
  now. Unattended-upgrades still runs here.
- **Vault starts sealed.** Nothing unseals it on boot. Re-running
  `configure_hashistack_server.yml` does, with three keys read from
  `/opt/vault/init.json`. A sealed Vault stops every template that reads a
  secret on its next render.
- **The tailnet skips ufw.** On 2026-08-01 tailscaled's `ts-input` chain was
  measured ahead of ufw, so every port here is open to the tailnet whatever
  the rules say ([host firewall](/components/host-firewall.md)).
- **The route can vanish.** The Tailscale role applies
  `--advertise-routes` only on first join. In September 2026 the route was
  gone and was restored by hand
  ([Tailscale subnet router](/components/tailscale-subnet-router.md)).
- **Host key changed.** On 2026-08-22 SSH to firebat failed with `REMOTE HOST
  IDENTIFICATION HAS CHANGED` (SY1 plan review,
  `.loop/verdicts/SY1-switchyard-deployment.plan-validator.snapshot.md`).
  The cause is not recorded. That review also guessed firebat was arm64,
  which the U1 plan's SSH reading contradicts.
- **dnsmasq used to run here** as the lab zone's resolver, and was removed so
  household DNS no longer depends on this machine
  ([ADR 0003](/decisions/0003-lab-names-resolve-from-public-dns.md)). Its
  port 53 rule outlived it.

## If firebat goes down

Everything that needs the control plane stops, and there is no second copy of
any part of it:

- No Consul catalog or KV. Both Terraform roots keep their state in Consul
  here, so neither can plan. The applications root's catalog lookups for
  MinIO and Postgres fail.
- No Vault, so no secret renders, no workload identity exchange, no brokered
  Nomad or Consul token, and no human login.
- No Nomad server, so nothing schedules. Allocations already running on
  workers keep running, as the 2026-07-31 outage showed.
- No edge: every `*.lab.orangecluster.nl` name stops answering, and off-site
  access through the tailnet ends with it.
- No Postgres: OpenViking, Bifrost's config store and every other database
  consumer fails.

The breakglass runbook (`cli/src/localstack_cli/commands/breakglass_runbook.md`)
notes that the edge and the direct LAN address both die with firebat. Its
third route, SSH plus loopback, helps only while the host is up and a
service on it is not.

Related: [Ansible bootstrap](/components/bootstrap.md),
[host volumes](/components/host-volumes.md),
[Nomad OIDC discovery](/components/nomad-oidc-discovery.md).
