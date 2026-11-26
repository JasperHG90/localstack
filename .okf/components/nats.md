---
type: component
title: NATS and JetStream
description: "A single unauthenticated NATS 2.10 server with JetStream on radxa, plus an exporter task, all in the infrastructure root. Its one user is ov-sync-consumer, through the OV_SYNC stream, and its data has no backup."
tags: [nats, jetstream, messaging, radxa, component]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: nats-jobspec
    resource: deployments/infrastructure/services/nats.hcl
  - id: infra-services
    resource: deployments/infrastructure/services.tf
  - id: prometheus-jobspec
    resource: deployments/infrastructure/services/prometheus.hcl
  - id: nats-reference
    resource: docs/reference/nats.md
  - id: ov-sync-stream
    resource: applications/ov-sync-consumer/internal/stream/stream.go
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

## Who uses it

[ov-sync-consumer](/components/ov-sync-consumer.md) is the one user. Its
receiver, inside the seaweedfs job on orangepi4a, publishes filer events to
`ovsync.events`, and its consumer on radxa reads them through the durable
consumer `ov-sync-consumer` and moves failures to `ovsync.dead`. The consumer
creates the stream `OV_SYNC` (file storage, 7 days, 64 MB, 2 min dedupe
window) at start, from `internal/stream/stream.go`. Losing the stream loses
only events in flight, which the consumer's catch-up pass repairs.

The one other consumer design, a Postgres LISTEN/NOTIFY bridge, was never
built: [PostgreSQL CDC to NATS bridge](/proposals/postgres-nats-cdc-bridge.md).
[Adding Orange Pi RV2 (RISC-V) to the Cluster](/proposals/riscv-worker-node.md)
also plans NATS on that node, unbuilt.

## Invariants and what enforces them

- **No auth.** Anyone on `192.168.0.0/16` can publish, subscribe and create
  streams. ufw does not filter 4222 or 8222: the job publishes them through
  Podman's bridge, which DNATs them past `ufw-user-input` (see
  [Host firewall](/components/host-firewall.md)). Only being on the LAN
  gates it. R2, a NATS auth-callout that
  would accept Vault OIDC or Nomad JWTs, was blocked when `5b2ed1b`
  reset the loop and is not in the current loop.
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
  registry-ui, driftwatch, ov-sync-consumer and both backup jobs, among others. NATS
  reserves 500 MHz and 512 MB for the server and 50 MHz and 64 MB for the
  exporter.

## Evidence

Built or recorded from these, which a `sources` entry cannot point at:

- commit `f0bfd08`
- loop ticket `R2-rollout-nats-auth-callout` (its plan and any verdicts are under `.loop/` at commit `48f52e2`, from before the `5b2ed1b` loop reset)
