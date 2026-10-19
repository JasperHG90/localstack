---
description: Reset a misbehaving JetStream consumer by deleting it so the next subscriber re-creates it.
stale_after: 2027-01-19
sources:
  - resource: deployments/infrastructure/services/nats.hcl
---

# How to reset a JetStream consumer

## Introduction

This resets a misbehaving consumer by deleting it and letting the next
subscriber re-create it. `hermes-events` and `worker` are the example stream
and consumer from
[How to create a JetStream stream](create-a-jetstream-stream.md). Use your
own names.

## Prerequisites

- The `nats` CLI with a cluster context, see
  [How to set up the nats CLI](set-up-the-nats-cli.md).

## Directions

### Step 1: Remove the consumer

```bash
nats consumer rm hermes-events worker --force
# next subscribe with the same durable name re-creates it from the latest config
```

## Additional resources

- [NATS and JetStream](../reference/nats.md)
- [How to use NATS from Python](use-nats-from-python.md)
