# How to use NATS from Python

## Introduction

`nats-py` is the official asyncio client. JetStream API is on the same
connection object. This covers plain pub/sub, publishing to a JetStream
stream, and the durable pull consumer.

## Prerequisites

- A Python project managed with `uv`.
- A host that can reach the broker, see
  [NATS and JetStream](../reference/nats.md).

## Directions

### Step 1: Add the client

```bash
uv add nats-py
```

### Step 2: Publish and subscribe

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

### Step 3: Publish to a JetStream stream

```python
js = nc.jetstream()

# declare-or-update is idempotent; safe to call on every startup
await js.add_stream(name="hermes-events", subjects=["hermes.events.*"])

ack = await js.publish("hermes.events.skill_run", b'{"status":"ok"}')
print(ack.stream, ack.seq)
```

### Step 4: Consume with a durable pull consumer

The durable pull consumer is the workhorse pattern.

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

## Additional resources

- [NATS and JetStream](../reference/nats.md)
- [How to connect a Nomad job to NATS](connect-a-nomad-job-to-nats.md)
