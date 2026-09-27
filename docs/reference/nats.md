# NATS and JetStream

The cluster's NATS broker for pub/sub and durable streams. It runs the `nats`
service from `deployments/infrastructure/services/nats.hcl`.

## Connection facts

- **Server:** `nats://nats.service.localstack.consul:4222` (Consul DNS) or `nats://192.168.2.50:4222` (direct).
- **Auth:** none. LAN-only via UFW (`192.168.0.0/16`). Treat the bus as trusted; don't put it on the public internet.
- **JetStream is on:** durable streams up to 10 GB on disk, 256 MB in memory, store at `/data/jetstream` on radxa-dragon-q6a.
- **Monitoring:** `http://192.168.2.50:8222/` — `/varz`, `/jsz`, `/connz`, `/healthz` for liveness.

Single-node JetStream means **no replication and no failover** — if radxa-dragon-q6a goes down, the stream is unavailable until it comes back. Acceptable for homelab; don't use this bus as the source of truth for anything you can't rebuild.

JetStream's host volume is `nats_data` (2–20 GiB on radxa-dragon-q6a).

## Conventions

- **Subjects are dot-namespaced**, lower-case, `app.domain.event` (e.g. `hermes.events.skill_run`, `memex.notes.created`). Wildcards: `*` (one token), `>` (rest of the path).
- **Pick core NATS for ephemeral signals**, JetStream for anything you'd be sad to lose. Defaulting to JetStream "just in case" is wasteful — every retained message lives on disk on a single edge node.
- **One stream per producer app** is the simplest mental model. Filter by subject within the stream rather than spinning up a stream per event type.
- **Idempotent consumers.** `Msg-Id` headers + the JetStream dedupe window (2m in [How to create a JetStream stream](../how-to/create-a-jetstream-stream.md)) make exactly-once *publishing* easy; exactly-once *processing* still requires the consumer to be idempotent.
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

- NATS docs — <https://docs.nats.io/>
- `nats-py` — <https://github.com/nats-io/nats.py>
- Job spec — `deployments/infrastructure/services/nats.hcl`
- Volume + firewall wiring — `deployments/infrastructure/services.tf`
