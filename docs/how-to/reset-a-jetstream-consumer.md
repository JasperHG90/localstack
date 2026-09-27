# How to reset a JetStream consumer

## Introduction

This resets a misbehaving consumer by deleting it and letting the next
subscriber re-create it.

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
