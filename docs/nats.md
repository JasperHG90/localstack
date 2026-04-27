# Using NATS + JetStream on the cluster

How to connect to and use the cluster's NATS broker for pub/sub and durable streams. Assumes the `nats` service from `deployments/infrastructure/services/nats.hcl` is running.

## TL;DR

- **Server:** `nats://nats.service.localstack.consul:4222` (Consul DNS) or `nats://192.168.2.50:4222` (direct).
- **Auth:** none. LAN-only via UFW (`192.168.0.0/16`). Treat the bus as trusted; don't put it on the public internet.
- **JetStream is on:** durable streams up to 10 GB on disk, 256 MB in memory, store at `/data/jetstream` on radxa-dragon-q6a.
- **Monitoring:** `http://192.168.2.50:8222/` — `/varz`, `/jsz`, `/connz`, `/healthz` for liveness.

---

## 1. CLI

The `nats` CLI is the fastest way to inspect and prod the bus.

```bash
# install (pick one)
brew install nats-io/nats-tools/nats           # macOS
go install github.com/nats-io/natscli/nats@latest

# context once, then everything else is short
nats context add localstack \
  --server nats://192.168.2.50:4222 \
  --select
nats server check connection
nats server info
```

### Core pub/sub (no JetStream)

Best for fire-and-forget signals — no durability, lost if no subscriber is connected.

```bash
# terminal A
nats sub 'orders.*'

# terminal B
nats pub orders.created '{"id": 1}'
nats pub orders.shipped '{"id": 1}'
```

### JetStream

Use when you need durability, replay, or work-queue semantics (worker pulls one message, acks, next worker pulls the next).

```bash
# create a stream that captures all subjects under hermes.events.*
nats stream add hermes-events \
  --subjects 'hermes.events.*' \
  --storage file --retention limits \
  --max-age 30d --max-bytes 1GB \
  --max-msgs=-1 --max-msg-size=-1 \
  --discard old --dupe-window 2m \
  --replicas 1 --defaults

# publish — same pub command, but now persisted
nats pub hermes.events.skill_run '{"name":"medium-reader","status":"ok"}'

# durable consumer (pull) — survives restarts, tracks ack position
nats consumer add hermes-events worker \
  --pull --deliver=all --ack=explicit --defaults
nats consumer next hermes-events worker --count 1

# inspect
nats stream ls
nats stream info hermes-events
nats consumer report hermes-events
```

Single-node JetStream means **no replication and no failover** — if radxa-dragon-q6a goes down, the stream is unavailable until it comes back. Acceptable for homelab; don't use this bus as the source of truth for anything you can't rebuild.

---

## 2. Python

`nats-py` is the official asyncio client. JetStream API is on the same connection object.

```bash
uv add nats-py
```

### Plain pub/sub

```python
import asyncio
import nats

async def main():
    nc = await nats.connect("nats://nats.service.localstack.consul:4222")

    async def handler(msg):
        print(msg.subject, msg.data.decode())
    await nc.subscribe("orders.*", cb=handler)

    await nc.publish("orders.created", b'{"id": 1}')
    await asyncio.sleep(1)
    await nc.drain()

asyncio.run(main())
```

### JetStream — publisher

```python
js = nc.jetstream()

# declare-or-update is idempotent; safe to call on every startup
await js.add_stream(name="hermes-events", subjects=["hermes.events.*"])

ack = await js.publish("hermes.events.skill_run", b'{"status":"ok"}')
print(ack.stream, ack.seq)
```

### JetStream — durable pull consumer (the workhorse pattern)

```python
psub = await js.pull_subscribe(
    subject="hermes.events.*",
    durable="worker",       # name persists ack state across restarts
    stream="hermes-events",
)

while True:
    try:
        msgs = await psub.fetch(batch=10, timeout=5)
    except nats.errors.TimeoutError:
        continue
    for msg in msgs:
        try:
            handle(msg)               # your work
            await msg.ack()
        except Exception:
            await msg.nak(delay=30)   # retry in 30s
```

`ack=explicit` + `nak(delay=...)` gives you at-least-once with a retry/backoff. If a message is poisoning the consumer, set a `max_deliver` on the consumer config and use `term()` to drop it permanently.

---

## 3. Wiring into a Nomad job

Treat NATS the way other shared infra is treated — Consul DNS, no secrets, just env vars.

```hcl
task "myapp" {
  driver = "podman"

  service {
    name = "myapp"
    # ... your usual stuff
  }

  template {
    data = <<EOF
NATS_URL=nats://nats.service.localstack.consul:4222
EOF
    destination = "secrets/file.env"
    env         = true
  }
}
```

No firewall changes needed for clients — outbound to `192.168.2.50:4222` is allowed by default within the LAN. The inbound rule on radxa is already open from `192.168.0.0/16`.

---

## 4. Conventions

- **Subjects are dot-namespaced**, lower-case, `app.domain.event` (e.g. `hermes.events.skill_run`, `memex.notes.created`). Wildcards: `*` (one token), `>` (rest of the path).
- **Pick core NATS for ephemeral signals**, JetStream for anything you'd be sad to lose. Defaulting to JetStream "just in case" is wasteful — every retained message lives on disk on a single edge node.
- **One stream per producer app** is the simplest mental model. Filter by subject within the stream rather than spinning up a stream per event type.
- **Idempotent consumers.** `Msg-Id` headers + the JetStream dedupe window (2m above) make exactly-once *publishing* easy; exactly-once *processing* still requires the consumer to be idempotent.
- **No long-lived synchronous request/reply across the bus.** Use NATS request/reply for sub-second internal RPC, but anything that takes >100 ms or might fail should be a JetStream message with an explicit reply subject.

---

## 5. Operations

### Storage check
```bash
nats stream report
curl -s http://192.168.2.50:8222/jsz | jq '.config, .streams, .bytes'
```

### Drain a stream you don't want any more
```bash
nats stream rm hermes-events --force
```

### Reset a misbehaving consumer
```bash
nats consumer rm hermes-events worker --force
# next subscribe with the same durable name re-creates it from the latest config
```

### Disk on radxa
JetStream's host volume is `nats_data` (2–20 GiB on radxa-dragon-q6a). Check headroom with:
```bash
nomad node status -stats $(nomad node status | awk '/radxa/ {print $1}') | grep -A1 nats_data
```

If a stream's `max-bytes` plus the others starts to crowd the volume, either raise the volume's `capacity_max` in `deployments/infrastructure/services.tf` or trim the stream's retention.

---

## See also

- NATS docs — <https://docs.nats.io/>
- `nats-py` — <https://github.com/nats-io/nats.py>
- Job spec — `deployments/infrastructure/services/nats.hcl`
- Volume + firewall wiring — `deployments/infrastructure/services.tf`
