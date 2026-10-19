---
description: Send and receive fire-and-forget messages with core NATS pub/sub from the nats CLI.
stale_after: 2027-01-19
sources:
  - resource: deployments/infrastructure/services/nats.hcl
---

# How to publish and subscribe with the nats CLI

## Introduction

This sends and receives messages with core NATS pub/sub, without JetStream.
Use it for fire-and-forget signals: nothing is stored, and a message sent
while no subscriber is connected is lost.

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
