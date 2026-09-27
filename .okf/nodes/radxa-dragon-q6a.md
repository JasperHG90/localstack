---
type: node
title: radxa-dragon-q6a, the application node
description: "The Radxa Dragon Q6A (192.168.2.50) carries the application tier: Hermes, Bifrost, OpenViking, dash, registry-ui, driftwatch, Redis, NATS, both oauth2-proxy gates and the nightly backups. Several jobs reach each other over loopback and so cannot move alone, five host volumes hold the rest in place, and its memory was down to 598 MB free by September 2026."
tags: [node, radxa-dragon-q6a, radxa, arm64, hermes, bifrost, openviking, redis, nats, backups]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: inventory
    resource: git:3ec5d1e:bootstrap/inventory/cluster.ini
  - id: infra-services
    resource: git:3ec5d1e:deployments/infrastructure/services.tf
  - id: apps-services
    resource: git:3ec5d1e:deployments/applications/services.tf
  - id: infra-database
    resource: git:3ec5d1e:deployments/infrastructure/database.tf
  - id: hermes-jobspec
    resource: git:3ec5d1e:deployments/applications/services/hermes.hcl
  - id: openviking-jobspec
    resource: git:3ec5d1e:deployments/applications/services/openviking.hcl
  - id: driftwatch-jobspec
    resource: git:3ec5d1e:deployments/applications/services/driftwatch.hcl
  - id: redis-jobspec
    resource: git:3ec5d1e:deployments/infrastructure/services/redis.hcl
  - id: ov-dash-jobspec
    resource: git:3ec5d1e:deployments/applications/services/ov-dash.hcl
  - id: backups-off-firebat
    resource: git:4b0af46:deployments/infrastructure/services/backup-postgres.hcl
  - id: hermes-deployed
    resource: git:669435d:deployments/applications/services.tf
  - id: sy1-node-probe
    resource: git:3ec5d1e:.loop/verdicts/SY1-switchyard-deployment.plan-validator.snapshot.md
  - id: U1-upgrade-pin-hashistack-versions
    resource: loop:U1-upgrade-pin-hashistack-versions
  - id: U4-upgrade-consul-2x
    resource: loop:U4-upgrade-consul-2x
---

# radxa-dragon-q6a, the application node

radxa runs more jobs than the other four nodes together. Most of what a
person uses on the cluster, other than storage and monitoring, is here. The
cross-node picture is [node placement](/nodes/placement.md).

| Fact | Value | Source |
|---|---|---|
| Names | inventory `radxa` (also its Consul node name), Nomad `radxa-dragon-q6a`, SSH user `radxa` | `bootstrap/inventory/cluster.ini` |
| Address | `192.168.2.50` | same |
| Board | Radxa Dragon Q6A (from the hostname) | |
| OS and arch | Ubuntu noble, arm64 | U1 plan |
| CPU, RAM | 8 CPUs. 5.4 GiB available on 2026-08-22, 598 MB free by 2026-09-09. Total not recorded | SY1 plan review, `ov-dash.hcl` header |
| Nomad | client, pool `default`, no node class, worker reservation | [placement](/nodes/placement.md) |
| Tailnet | not on it, `tailscaled` stopped | `bootstrap/playbooks/configure_tailscale.yml` |

## What runs here

Pinned by `value = "radxa-dragon-q6a"`, either literal in the jobspec or a
`*_hostname` value in `deployments/applications/services.tf`.

| Job | Ports | Why here |
|---|---|---|
| `hermes` (three tasks, 6000 MHz and 2048 MB for the gateway) | 8642, 9119, sidecar 1934 on loopback | Deployed here in `669435d`. It now has to stay with Bifrost and OpenViking: its model provider is `http://127.0.0.1:8080/v1`, and it reaches OpenViking on `192.168.2.50:1933` over `lo`. See [Hermes](/components/hermes.md). |
| `bifrost` (600 MHz, 512 MB) | 8080 | No reason recorded. Hermes's loopback URL ties it here. See [Bifrost](/components/bifrost.md). |
| `openviking` (5000 MHz, 1536 MB) | 1933 | "On radxa beside Bifrost" (`openviking.hcl` header). Its config dials Bifrost at `192.168.2.50:8080`, not loopback. See [the OpenViking service](/components/openviking-service.md). |
| `dash` (two tasks) | 8000, 8001 | Next to `oauth2-proxy`, which reaches it at `127.0.0.1:8000` and `:8001`. See [dash](/components/dash.md). |
| `registry-ui` (two tasks) | 8002, 8003 | Next to `oauth2-proxy-registry-ui`, same loopback shape. See [registry-ui](/components/registry-ui.md). |
| `oauth2-proxy`, `oauth2-proxy-registry-ui` (200 MHz, 128 MB each) | 4180, 4181 | firebat had about 100 MHz left when L1 placed the first one ([the edge proxy](/components/edge-proxy.md)). |
| `driftwatch` (200 MHz, 384 MB) | 8010 | Off the Jetson, so the canary does not share the node it measures, and embark's rule already admitted `.50` (`driftwatch.hcl` header). See [driftwatch](/components/driftwatch.md). |
| `redis` (500 MHz, 512 MB) | 6379 | No reason recorded. See [Redis](/components/redis.md). |
| `nats` with its exporter | 4222, 8222, 7777 | Built here instead of on the planned RISC-V board ([proposal](/proposals/riscv-worker-node.md)). See [NATS](/components/nats.md). |
| `backup-postgres` (02:00), `backup-minio` (03:00) | none | Moved off CPU-full firebat on 2026-07-07, because radxa had spare CPU and memory and hosts neither service (commit `4b0af46`). See [GCS backups](/components/gcs-backups.md). |

The system jobs `node-exporter` and `alloy` run here too.

Host volumes: `hermes_data` (1 to 5 GiB), `openviking_data` (1 to 10 GiB),
`driftwatch_data` and `registry_ui_data` (100 MiB to 1 GiB each), `nats_data`
(2 to 20 GiB).

## Firewall rules that name this node

| Rule | Where |
|---|---|
| Worker base ports from `192.168.0.0/16` | `bootstrap/playbooks/configure_network.yml` |
| `node_exporter_radxa` 9100 from `.47`, `redis` 6379 from `.46`, `nats` 4222 and 8222 from the LAN and 7777 from `.47`, `oauth2_proxy` 4180 and 4181 from `.30` | `deployments/infrastructure/services.tf` |
| `hermes` 8642 from `.30` and `.46`, 9119 from `.30`, `bifrost` 8080 from the LAN, `dash` 8000 from `.50`, `openviking` 1933 from `.50`, `.30`, `.47` and `.29`, `driftwatch` 8010 from `.50` and `.47` | `deployments/applications/services.tf` |
| Still live, no longer declared: 4182 from `.30` (the deleted OpenViking proxy) and 1933 from the LAN | comments above `oauth2_proxy` and `openviking`, each with the `ufw delete` line owed |
| Very likely still live, inferred from git and not checked on the node: 6379 from the LAN, the rule `redis` started with. Vault reaches Redis through it today, so do not delete it before adding `.30` | [Redis](/components/redis.md) |

As a caller, `192.168.2.50` is admitted by embark (8000) on the Jetson, for
Bifrost and driftwatch, and by Loki and Tempo on ubuntu.

Vault on firebat also has to reach Redis here, at `192.168.2.50:6379` from
`deployments/infrastructure/database.tf`. No declared rule admits `.30` on
that port, which is why the leftover LAN-wide rule above matters.

## What dials it by literal address

HAProxy's `bifrost`, `dash`, `registryui`, `ovapi` and `hermesgw` backends.
Prometheus's scrape targets. `ov.conf.json`'s four Bifrost `api_base`
entries. The `bifrost_ready` gate and the `bifrost` provider through it.
embark's `redis_host`. The NATS exporter. Vault's Redis connection. ov-dash's
`openviking_host`. The `*_host` values beside each `*_hostname` in
`deployments/applications/services.tf`.

## Quirks and traps

- **Loopback pairs move together.** dash with `oauth2-proxy`, registry-ui
  with `oauth2-proxy-registry-ui`, and Hermes with Bifrost all dial
  `127.0.0.1`. The two proxies are in the infrastructure root and their
  upstreams are literals there, so moving either half breaks the pair with no
  plan error.
- **Volumes hold the node full.** `openviking_data` and `driftwatch_data` are
  single-node-writer, so their jobs cannot move to make room. ov-dash went to
  [orangepi4a](/nodes/orangepi4a.md) for that reason.
- **The memory sum is read off jobspecs.** `redis.hcl` puts reservations at
  about 6.7 GB steady, plus about 1.3 GB while the backups run, and says it
  was never measured on the node. Confirm with `free -m` before raising
  anything.
- **Redis loses its users on restart.** Vault-minted ACL users live only in
  memory, so any restart of the Redis task (a node reboot included) leaves
  consumers such as embark serving uncached until they are restarted by hand.
- **Stale apt cache.** U4 found this node still offering Consul `1.22.6-1`
  as its candidate. Run `apt update` before an upgrade.

## If radxa-dragon-q6a goes down

- Hermes, Bifrost and OpenViking stop, so no agent, no model call through the
  gateway, and no context store. `openviking.lab` (ov-dash on orangepi4a)
  loads but cannot search.
- `dash.lab`, `registry-ui.lab`, `bifrost.lab`, `openviking-api.lab` and
  `hermes-gateway.lab` stop answering.
- embark loses its Redis cache. NATS stops, and nothing in the repo uses it
  yet.
- The nightly backups do not run, and nothing alerts on a missed run.

Related: [host volumes](/components/host-volumes.md),
[the host firewall](/components/host-firewall.md),
[Vault's dynamic secrets engines](/components/vault-secrets-engines.md).
