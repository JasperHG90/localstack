---
type: component
title: NATS and JetStream
description: "A single unauthenticated NATS 2.10 server with JetStream on radxa, plus an exporter task, all in the infrastructure root. No job in this repository publishes to it or reads from it yet, its data has no backup, and the one design that would use it is an unbuilt proposal."
tags: [nats, jetstream, messaging, radxa, component]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: nats-jobspec
    resource: git:3ec5d1e:deployments/infrastructure/services/nats.hcl
  - id: infra-services
    resource: git:3ec5d1e:deployments/infrastructure/services.tf
  - id: prometheus-jobspec
    resource: git:3ec5d1e:deployments/infrastructure/services/prometheus.hcl
  - id: nats-reference
    resource: git:3ec5d1e:docs/reference/nats.md
  - id: nats-commit
    resource: git:f0bfd08
  - id: R2-rollout-nats-auth-callout
    resource: loop:R2-rollout-nats-auth-callout
---

# NATS and JetStream

Connection facts and usage conventions are in `docs/reference/nats.md`, with
how-to guides linked from it. This page is what a maintainer needs beyond
that.

## The pieces

| Piece | Where |
| --- | --- |
| Job `nats`, task `nats`, image `docker.io/nats:2.10-alpine`, pinned to radxa-dragon-q6a | `deployments/infrastructure/services/nats.hcl` |
| Server config, rendered to `local/nats-server.conf` | template in the same file |
| Task `nats-exporter`, `prometheus-nats-exporter:0.17.3`, port 7777, host network | same file |
| Host volume `nats_data` (2 to 20 GiB, radxa), mounted at `/data` | `deployments/infrastructure/services.tf` |
| `nomad_job.nats` with `depends_on` the volume | same file |
| Firewall: 4222 and 8222 from `192.168.0.0/16`, 7777 from Prometheus (.47) | `local.firewall_rules["nats"]`, same file |
| Grafana dashboard | `deployments/infrastructure/services/grafana/nats.json` |

It came in with f0bfd08 as "LAN-only, no auth in v1", and that is still its
state.

## How it connects

- Clients reach 4222 on radxa directly. Nothing routes NATS through the edge,
  and the ports are static, so a client uses `192.168.2.50:4222`.
- The exporter reads the monitor port at the literal
  `http://192.168.2.50:8222`, not a Nomad address, because it runs in host
  network mode. Moving the job to another node breaks the exporter until that
  literal changes.
- Prometheus has no static job for NATS. The `nats-exporter` service carries
  the `prometheus` tag, so the `consul_services` job in
  `deployments/infrastructure/services/prometheus.hcl` picks it up.
- The `nats` task runs as `user = "root"`, like the other tasks that write a
  host volume, because the `mkdir` plugin creates volumes owned by root. See
  [Host volumes](/components/host-volumes.md).

## What no one uses yet

No jobspec, Terraform file or CLI module in this repository connects to NATS.
The dash tile advertises it, and the how-to guides show how a job would. The
one concrete consumer design, a Postgres LISTEN/NOTIFY bridge, was never
built: [PostgreSQL CDC to NATS bridge](/proposals/postgres-nats-cdc-bridge.md).
[Adding Orange Pi RV2 (RISC-V) to the Cluster](/proposals/riscv-worker-node.md)
also plans NATS on that node, unbuilt.

## Invariants and what enforces them

- **No auth.** Anyone on `192.168.0.0/16` can publish, subscribe and create
  streams. The firewall is the only control. R2, a NATS auth-callout that
  would accept Vault OIDC or Nomad JWTs, is blocked.
- **JetStream limits sit below the volume.** `max_file_store: 10GB` against a
  volume declared up to 20 GiB, and `max_memory_store: 256MB` against a
  512 MB task. Raising the file store past the volume's size, or the memory
  store near the task limit, trades a JetStream refusal for a full disk or an
  OOM kill. Nothing checks the pair.
- **One node, no replicas.** Streams are unavailable while radxa is down.
  Treat the bus as rebuildable.

## Traps

- **Consul DNS does not work for LAN clients.** The reference page lists
  `nats.service.localstack.consul`, but `.consul` is not forwarded
  ([ADR 0004](/decisions/0004-consul-names-are-not-forwarded.md)). Use the node
  address.
- **No backup.** Neither backup job touches `nats_data`
  ([GCS backups](/components/gcs-backups.md)).
- **Floating tag.** `2.10-alpine` takes any 2.10 patch on the next pull.
- **radxa is crowded.** It also runs hermes, openviking, bifrost, redis, dash,
  registry-ui, driftwatch and both backup jobs, among others. NATS
  reserves 500 MHz and 512 MB for the server and 50 MHz and 64 MB for the
  exporter.
