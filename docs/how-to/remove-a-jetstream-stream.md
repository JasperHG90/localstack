---
description: Delete a JetStream stream and the messages it holds.
stale_after: 2027-01-19
sources:
  - resource: deployments/infrastructure/services/nats.hcl
---

# How to remove a JetStream stream

## Introduction

This deletes a stream you don't want any more, and the messages it holds.
`hermes-events` is the example stream from
[How to create a JetStream stream](create-a-jetstream-stream.md). Use your
stream's name.

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
