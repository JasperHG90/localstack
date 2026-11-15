---
description: Connection facts, JetStream limits and subject conventions for the cluster's NATS broker.
stale_after: 2027-01-19
sources:
  - resource: deployments/infrastructure/services/nats.hcl
  - resource: deployments/infrastructure/services.tf
  - resource: applications/ov-sync-consumer/internal/stream/stream.go
---

# NATS and JetStream

The cluster's NATS broker for pub/sub and durable streams. It runs the `nats`
service from `deployments/infrastructure/services/nats.hcl`.

## Connection facts

- **Server:** `nats://192.168.2.50:4222`. Use the node address, from a Nomad job
  too. `nats.service.localstack.consul` does not resolve, because the `.consul`
  zone is not forwarded to Consul, and the address Consul holds for it is a
  container bridge address nothing else can reach. See [DNS records](dns.md).
- **Auth:** none. LAN-only via UFW (`192.168.0.0/16`). Treat the bus as trusted,
  and don't put it on the public internet.
- **JetStream is on:** durable streams up to 10 GB on disk, 256 MB in memory, store at `/data/jetstream` on radxa-dragon-q6a.
- **Monitoring:** `http://192.168.2.50:8222/`, with `/varz`, `/jsz`, `/connz`,
  and `/healthz` for liveness.
- **Metrics:** a `prometheus-nats-exporter` task serves port 7777 on the same
  node, open only to Prometheus (`192.168.2.47`).

Single-node JetStream means **no replication and no failover**. If
radxa-dragon-q6a goes down, the stream is unavailable until it comes back.
Neither nightly backup job copies `nats_data`, so don't use this bus as the
source of truth for anything you can't rebuild.

JetStream's host volume is `nats_data` (2 to 20 GiB on radxa-dragon-q6a).

## Streams

| Stream | Subjects | Limits | Written by | Read by |
|---|---|---|---|---|
| `OV_SYNC` | `ovsync.events`, `ovsync.dead` | file storage, 7 days, 64 MB, oldest dropped first, 2 min dedupe window | the `receiver` task in the `seaweedfs` job | the `ov-sync-consumer` job, durable consumer `ov-sync-consumer` |

- `ovsync.events` carries one SeaweedFS filer webhook event per message, as
  the filer sent it, for keys under `/buckets/ov-sync/`. `Nats-Msg-Id` is the
  SHA-256 of the event's canonical JSON, so a redelivered webhook is dropped.
- `ovsync.dead` holds the events the consumer gave up on after 20 tries,
  with the last error in the `Ov-Sync-Error` header. Nothing reads it.
- The consumer creates the stream when it starts. Until then the receiver's
  publishes fail.

## Conventions

- **Subjects are dot-namespaced**, lower-case, `app.domain.event` (e.g. `hermes.events.skill_run`, `memex.notes.created`). Wildcards: `*` (one token), `>` (rest of the path).
- **Pick core NATS for ephemeral signals**, JetStream for anything you'd be sad
  to lose. Defaulting to JetStream "just in case" is wasteful: every retained
  message is stored on disk on a single node.
- **One stream per producer app** is the simplest mental model. Filter by subject within the stream rather than spinning up a stream per event type.
- **Idempotent consumers.** `Msg-Id` headers + the JetStream dedupe window (2m
  in [How to create a JetStream stream](../how-to/create-a-jetstream-stream.md))
  make exactly-once *publishing* easy, but exactly-once *processing* still
  requires the consumer to be idempotent.
- **No long-lived synchronous request/reply across the bus.** Use NATS request/reply for sub-second internal RPC, but anything that takes >100 ms or might fail should be a JetStream message with an explicit reply subject.

## How-to guides

- [How to set up the nats CLI](../how-to/set-up-the-nats-cli.md)
- [How to publish and subscribe with the nats CLI](../how-to/publish-and-subscribe-with-the-nats-cli.md)
- [How to create a JetStream stream](../how-to/create-a-jetstream-stream.md)
- [How to use NATS from Python](../how-to/use-nats-from-python.md)
- [How to connect a Nomad job to NATS](../how-to/connect-a-nomad-job-to-nats.md)
- [How to check JetStream disk usage](../how-to/check-jetstream-disk-usage.md)
- [How to remove a JetStream stream](../how-to/remove-a-jetstream-stream.md)
- [How to reset a JetStream consumer](../how-to/reset-a-jetstream-consumer.md)

## See also

- NATS docs: <https://docs.nats.io/>
- `nats-py`: <https://github.com/nats-io/nats.py>
- Job spec: `deployments/infrastructure/services/nats.hcl`
- Volume and firewall wiring: `deployments/infrastructure/services.tf`
