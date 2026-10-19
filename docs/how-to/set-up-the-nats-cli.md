---
description: "Install the nats CLI, point a context at the cluster's broker, and check the connection."
stale_after: 2027-01-19
sources:
  - resource: deployments/infrastructure/services/nats.hcl
---

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

Point the context at radxa's address. The `.consul` zone is not forwarded
to Consul, so `nats.service.localstack.consul` does not resolve on the LAN.

```bash
# context once, then everything else is short
nats context add localstack \
  --server nats://192.168.2.50:4222 \
  --select
```

### Step 3: Check the connection

```bash
nats server check connection
nats account info
```

The first should print `OK Connection OK`. The second should show your
account with JetStream enabled. `nats server info` does not work here: it
asks the system account, and the server defines no user in it. Read server
details from the monitor port instead, with
`curl http://192.168.2.50:8222/varz`.

## Additional resources

- [NATS and JetStream](../reference/nats.md)
- [How to publish and subscribe with the nats CLI](publish-and-subscribe-with-the-nats-cli.md)
- [How to create a JetStream stream](create-a-jetstream-stream.md)
