# How to check JetStream disk usage

## Introduction

JetStream stores every retained message on the `nats_data` host volume on
radxa-dragon-q6a. This shows how much each stream uses and how much room the
volume has left.

## Prerequisites

- The `nats` CLI with a cluster context, see
  [How to set up the nats CLI](set-up-the-nats-cli.md).
- `curl`, `jq`, and the `nomad` CLI with read access to nodes.

## Directions

### Step 1: Check stream storage

```bash
nats stream report
curl -s http://192.168.2.50:8222/jsz | jq '.config, .streams, .bytes'
```

### Step 2: Check the volume's headroom

JetStream's host volume is `nats_data` (2–20 GiB on radxa-dragon-q6a). Check headroom with:

```bash
nomad node status -stats $(nomad node status | awk '/radxa/ {print $1}') | grep -A1 nats_data
```

### Step 3: Make room if the volume is crowded

If a stream's `max-bytes` plus the others starts to crowd the volume, either raise the volume's `capacity_max` in `deployments/infrastructure/services.tf` or trim the stream's retention.

## Additional resources

- [NATS and JetStream](../reference/nats.md)
- [How to remove a JetStream stream](remove-a-jetstream-stream.md)
