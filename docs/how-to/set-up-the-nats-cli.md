# How to set up the nats CLI

## Introduction

The `nats` CLI is the fastest way to inspect and prod the bus. This installs
it and points it at the cluster's broker once, so every later command is
short.

## Prerequisites

- A machine on the LAN (`192.168.0.0/16`), see
  [NATS and JetStream](../reference/nats.md).
- Homebrew on macOS, or a Go toolchain.

## Directions

### Step 1: Install the CLI

```bash
# install (pick one)
brew install nats-io/nats-tools/nats           # macOS
go install github.com/nats-io/natscli/nats@latest
```

### Step 2: Add a context for the cluster

```bash
# context once, then everything else is short
nats context add localstack \
  --server nats://192.168.2.50:4222 \
  --select
```

### Step 3: Check the connection

```bash
nats server check connection
nats server info
```

## Additional resources

- [NATS and JetStream](../reference/nats.md)
- [How to publish and subscribe with the nats CLI](publish-and-subscribe-with-the-nats-cli.md)
- [How to create a JetStream stream](create-a-jetstream-stream.md)
