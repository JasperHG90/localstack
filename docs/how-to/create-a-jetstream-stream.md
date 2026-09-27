# How to create a JetStream stream

## Introduction

Use JetStream when you need durability, replay, or work-queue semantics
(worker pulls one message, acks, next worker pulls the next). This creates a
stream, publishes to it, and reads it back through a durable consumer.

## Prerequisites

- The `nats` CLI with a cluster context, see
  [How to set up the nats CLI](set-up-the-nats-cli.md).

## Directions

### Step 1: Create the stream

```bash
# create a stream that captures all subjects under hermes.events.*
nats stream add hermes-events \
  --subjects 'hermes.events.*' \
  --storage file --retention limits \
  --max-age 30d --max-bytes 1GB \
  --max-msgs=-1 --max-msg-size=-1 \
  --discard old --dupe-window 2m \
  --replicas 1 --defaults
```

### Step 2: Publish to it

```bash
# publish — same pub command, but now persisted
nats pub hermes.events.skill_run '{"name":"medium-reader","status":"ok"}'
```

### Step 3: Add a durable consumer and read one message

```bash
# durable consumer (pull) — survives restarts, tracks ack position
nats consumer add hermes-events worker \
  --pull --deliver=all --ack=explicit --defaults
nats consumer next hermes-events worker --count 1
```

### Step 4: Inspect the stream

```bash
# inspect
nats stream ls
nats stream info hermes-events
nats consumer report hermes-events
```

## Additional resources

- [NATS and JetStream](../reference/nats.md), including what single-node
  JetStream does not give you
- [How to use NATS from Python](use-nats-from-python.md)
