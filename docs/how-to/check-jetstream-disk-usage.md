---
description: See how much disk each JetStream stream uses and how much room is left on radxa-dragon-q6a.
stale_after: 2027-01-19
sources:
  - resource: deployments/infrastructure/services/nats.hcl
  - resource: deployments/infrastructure/services.tf
---

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

### Step 2: Check the headroom

Two limits apply. JetStream refuses writes past `max_file_store`, which is
10GB in `deployments/infrastructure/services/nats.hcl`. `nats account info`
shows the file storage used against that limit:

```bash
nats account info
```

The `nats_data` volume declares 2 to 20 GiB, but the `mkdir` plugin makes it
a plain directory, so the other limit is radxa-dragon-q6a's own disk. Check
the disk figure under the node's host resource use:

```bash
nomad node status -stats $(nomad node status | awk '/radxa/ {print $1}')
```

### Step 3: Make room if storage is crowded

If the streams' `max-bytes` together near `max_file_store`, trim a stream's
retention, or raise `max_file_store` in
`deployments/infrastructure/services/nats.hcl` while keeping it below the free
disk on radxa. Raising the volume's `capacity_max` in
`deployments/infrastructure/services.tf` alone frees nothing.

## Additional resources

- [NATS and JetStream](../reference/nats.md)
- [How to remove a JetStream stream](remove-a-jetstream-stream.md)
