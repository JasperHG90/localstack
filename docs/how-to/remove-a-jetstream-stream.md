# How to remove a JetStream stream

## Introduction

This drains a stream you don't want any more, deleting it and the messages
it holds.

## Prerequisites

- The `nats` CLI with a cluster context, see
  [How to set up the nats CLI](set-up-the-nats-cli.md).

## Directions

### Step 1: Remove the stream

```bash
nats stream rm hermes-events --force
```

## Additional resources

- [NATS and JetStream](../reference/nats.md)
- [How to check JetStream disk usage](check-jetstream-disk-usage.md)
