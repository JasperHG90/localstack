---
type: component
title: Host volumes
description: "Every stateful job's data is a Nomad dynamic host volume declared in the infrastructure root's services.tf, pinned to one node by a literal hostname that the consuming job must repeat. Half the consumers are in the applications root, so nothing orders the volume before the job except applying infrastructure first."
tags: [nomad, host-volume, storage, terraform, component]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: infra-services
    resource: git:3ec5d1e:deployments/infrastructure/services.tf
  - id: infra-machine-roles
    resource: git:3ec5d1e:deployments/infrastructure/machine_roles.tf
  - id: app-services
    resource: git:3ec5d1e:deployments/applications/services.tf
  - id: embark-jobspec
    resource: git:3ec5d1e:deployments/applications/services/embark.hcl
  - id: ov-dash-jobspec
    resource: git:3ec5d1e:deployments/applications/services/ov-dash.hcl
  - id: delete-volume-howto
    resource: git:3ec5d1e:docs/how-to/delete-a-nomad-dynamic-host-volume.md
---

# Host volumes

A stateful job on this cluster keeps its data in a `nomad_dynamic_host_volume`
with `plugin_id = "mkdir"`, `single-node-writer` and `file-system` attachment.
All fourteen are in the `### Dynamic Host Volumes` part of
`deployments/infrastructure/services.tf`, whichever root runs the job that
mounts them.

## Which volume, where, for whom

| Volume | Node | Mounted by | Job's root |
| --- | --- | --- | --- |
| `postgres` | firebat | postgres | infrastructure |
| `minio_data` | orangepi4a | minio | infrastructure |
| `prometheus_data`, `grafana_data`, `acme_lego_state` | ubuntu | prometheus, grafana, acme | infrastructure |
| `nats_data` | radxa-dragon-q6a | nats | infrastructure |
| `loki_data`, `tempo_data` | ubuntu | loki, tempo | applications |
| `embark_data` | jetson-orin-nano | embark | applications |
| `memex_data` | jetson-orin-nano | memex (job commented out) | applications |
| `hermes_data`, `openviking_data`, `driftwatch_data`, `registry_ui_data` | radxa-dragon-q6a | hermes, openviking, driftwatch, registry-ui | applications |

The `###` comment above each newer volume says what it holds and whether
losing it matters. Read it before resizing or moving one.

## Invariants and what enforces them

- **Volume and job name the same node, twice.** The volume's `constraint` is a
  literal hostname in `services.tf`. The job pins itself separately, with a
  literal in its own jobspec (postgres, loki, registry-ui) or a `*_hostname`
  value in `deployments/applications/services.tf` (for example
  `embark_hostname`). A
  volume does not follow its job, so moving one without the other leaves the
  job unplaceable. Nothing checks the pair.
- **Apply infrastructure first.** Four infrastructure jobs carry `depends_on`
  their volume (prometheus, grafana, nats, acme). postgres and minio do not. The applications root cannot reference resources in the other
  root, so its jobs have no ordering at all. A job applied before its volume
  exists fails to place.
- **Volumes belong to root.** The `mkdir` plugin creates each directory as
  `root:root 0700` (recorded in `embark.hcl`). A task whose image runs as
  another user cannot read or write it, so loki, tempo, grafana, prometheus,
  nats and embark's two tasks set `user = "root"`, and hermes sets
  `user = "0"`. A new stateful job needs the same, or its own fix. Root has a
  second use: loki runs as root also so it can read its own identity file.
- **The deployer needs two grants.** `nomad_acl_policy.deploy` in
  `deployments/infrastructure/machine_roles.tf` carries the namespace
  capabilities `host-volume-create/register/read/write/delete`, which manage
  the volume resource, and `host_volume "*" { mount-readwrite }`, which lets a
  job it submits mount one. The mount grant is a wildcard on purpose: the
  `host-volume-*` grants are already unscoped, and a named list would 403 the
  next new volume.

## Traps

- **A volume pins the jobs next to it.** Because `single-node-writer` volumes
  cannot move, their jobs cannot either, and the node's free memory decides
  what else fits. ov-dash runs on orangepi4a rather than beside OpenViking for
  this reason: radxa had 598 MB free, and two of the volumes there
  (`openviking_data`, `driftwatch_data`) held their jobs in place.
- **Capacity numbers are declarations.** `capacity_min` and `capacity_max`
  are what Terraform asks Nomad for. With the `mkdir` plugin the volume is a
  plain directory, so treat the node's disk and the service's own limits (such
  as JetStream's `max_file_store`) as the real bound. This is not measured on
  the cluster.
- **Destroying the resource deletes the volume.** Removing the block plans a
  destroy, and Nomad deletes the volume it created. Renaming a volume or
  changing its node constraint very likely plans a replacement too (check the
  plan, this is not measured here). Treat either as deleting the data.
- **Deleting by hand does not stick.** The next apply recreates it, empty.
  Remove the block instead. The by-hand procedure, for volumes Terraform does
  not own, is `docs/how-to/delete-a-nomad-dynamic-host-volume.md`.
- **Not everything is backed up.** The nightly jobs cover Postgres and one
  MinIO bucket. Every other volume has only its node's disk. See
  [GCS backups](/components/gcs-backups.md).

## Where the data really is

Several volumes hold working state rather than the store itself, and their
comments say so: `loki_data` and `tempo_data` hold what has not yet been
flushed to MinIO, `openviking_data` holds scratch while vectors are in
Postgres and blobs in MinIO, and `registry_ui_data` holds a digest-keyed cache.
`embark_data` holds ModelKits that can be pulled again, at the cost of a slow
start. `acme_lego_state` is the one whose loss has an outside cost: without it
lego re-registers and re-issues on every run and hits Let's Encrypt's weekly
limit within days.
