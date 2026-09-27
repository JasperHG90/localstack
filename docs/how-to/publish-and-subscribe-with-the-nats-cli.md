# How to publish and subscribe with the nats CLI

## Introduction

Core pub/sub (no JetStream) is best for fire-and-forget signals — no
durability, lost if no subscriber is connected.

## Prerequisites

- The `nats` CLI with a cluster context, see
  [How to set up the nats CLI](set-up-the-nats-cli.md).

## Directions

### Step 1: Subscribe in one terminal

```bash
# terminal A
nats sub 'orders.*'
```

### Step 2: Publish from a second terminal

```bash
# terminal B
nats pub orders.created '{"id": 1}'
nats pub orders.shipped '{"id": 1}'
```

## Additional resources

- [NATS and JetStream](../reference/nats.md)
- [How to create a JetStream stream](create-a-jetstream-stream.md)
