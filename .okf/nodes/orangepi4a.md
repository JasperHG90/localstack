---
type: node
title: orangepi4a, the storage node
description: "The Orange Pi 4A (192.168.2.29) holds MinIO and its 1 to 3.5 TiB volume, plus ov-dash in the room the retired phoenix job left. Memory is its limit, several jobs hardcode its address even where a Consul lookup exists, and losing it takes every bucket, so Loki and Tempo cannot flush and the registry cannot serve a blob."
tags: [node, orangepi4a, orange-pi, arm64, minio, ov-dash, storage, nvme]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: inventory
    resource: git:3ec5d1e:bootstrap/inventory/cluster.ini
  - id: infra-services
    resource: git:3ec5d1e:deployments/infrastructure/services.tf
  - id: apps-services
    resource: git:3ec5d1e:deployments/applications/services.tf
  - id: minio-jobspec
    resource: git:3ec5d1e:deployments/infrastructure/services/minio.hcl
  - id: ov-dash-jobspec
    resource: git:3ec5d1e:deployments/applications/services/ov-dash.hcl
  - id: alloy-jobspec
    resource: git:3ec5d1e:deployments/infrastructure/services/alloy.hcl
  - id: alloy-128mb
    resource: git:daf8619:deployments/infrastructure/services/alloy.hcl
  - id: phoenix-retired
    resource: git:74fc590:deployments/applications/services.tf
  - id: ov-dash-deployed
    resource: git:30292e2:deployments/applications/services/ov-dash.hcl
  - id: nvme-howto
    resource: git:73742f6:docs/how-to/move-orange-pi-os-to-nvme.md
  - id: U1-upgrade-pin-hashistack-versions
    resource: loop:U1-upgrade-pin-hashistack-versions
  - id: U3-upgrade-nomad-2x
    resource: loop:U3-upgrade-nomad-2x
  - id: U4-upgrade-consul-2x
    resource: loop:U4-upgrade-consul-2x
---

# orangepi4a, the storage node

orangepi4a runs the cluster's only object store and the one job that was
small enough to fit beside it. The cross-node picture is
[node placement](/nodes/placement.md).

| Fact | Value | Source |
|---|---|---|
| Names | inventory `orange_pi_4a` (also its Consul node name), Nomad `orangepi4a`, SSH user `orangepi` | `bootstrap/inventory/cluster.ini` |
| Address | `192.168.2.29` | same |
| Board | Orange Pi 4A (from the inventory name) | same |
| OS and arch | Ubuntu jammy, arm64 | U4 plan |
| RAM, CPU | not recorded | |
| Storage | `minio_data` declares 1.0 to 3.5 TiB. A procedure for moving an Orange Pi's OS to NVMe exists, but whether it ran on this node is not recorded | `deployments/infrastructure/services.tf`, `docs/how-to/move-orange-pi-os-to-nvme.md` |
| Nomad | client, pool `default`, no node class, worker reservation (500 MHz, 512 MB, 10 GB) | [placement](/nodes/placement.md) |
| Tailnet | not on it, `tailscaled` stopped | `bootstrap/playbooks/configure_tailscale.yml` |

## What runs here

| Job | Ports | Why here |
|---|---|---|
| `minio` (5000 MHz, 2560 MB) | 9000 API, 9001 console | Literal `value = "orangepi4a"` in `minio.hcl`, held by the `minio_data` volume. No comment records the first reason. See [MinIO](/components/minio.md). |
| `ov-dash` (200 MHz, 512 MB, one alloc) | 4182 | `ov_dash_hostname = "orangepi4a"` in `deployments/applications/services.tf`. It would otherwise run next to OpenViking, but radxa had 598 MB free and its stateful neighbors there are pinned by volumes. ov-dash holds nothing on disk, so it moved, at the cost of a LAN hop to 1933 (`ov-dash.hcl` header, commit `30292e2`). See [ov-dash](/components/ov-dash.md). |

The system jobs `node-exporter` and `alloy` run here too.

Host volume: `minio_data`, 1.0 to 3.5 TiB, the largest in the cluster.

History: the `phoenix` tracing job ran here until `74fc590` retired it on
2026-09-09. ov-dash took its place the same day.

## Firewall rules that name this node

| Rule | Where |
|---|---|
| Worker base ports (SSH, Consul, Nomad, `20000:32000`) from `192.168.0.0/16` | `bootstrap/playbooks/configure_network.yml` |
| `minio` 9000 and 9001 from the LAN, `node_exporter_orangepi4a` 9100 from `.47` | `deployments/infrastructure/services.tf` |
| `ov_dash` 4182 from `.30` only | `deployments/applications/services.tf` |
| Still live, no longer declared: phoenix's 6006 and 4317 from the LAN | comment above `ov_dash` in `deployments/applications/services.tf`, with the `ufw delete` lines owed |

As a caller, `192.168.2.29` is admitted by Loki (3100) and Tempo (4317, 4318)
on ubuntu, for this node's Alloy, and by OpenViking (1933) on radxa, for
ov-dash.

## What dials it by literal address

The applications root looks MinIO up in the Consul catalog
(`data.consul_service.minio`), but several jobs also write `192.168.2.29`
out by hand, so a move does not follow the lookup:

- `loki.hcl` and `registry.hcl` get `minio_host` from Consul for the STS
  exchange, then name `192.168.2.29:9000` literally as the S3 endpoint.
- `tempo.hcl` names `192.168.2.29:9000` twice and takes no lookup at all.
- `backup-minio`'s `minio_host` and the `minio` firewall entry in
  `deployments/infrastructure/services.tf`.
- HAProxy's `minio`, `s3` and `ovdash` backends, and Prometheus's scrape
  targets.

## Quirks and traps

- **Memory is the limit.** It had 72 MB free before phoenix left
  (`deployments/applications/services.tf`, the comment on `nomad_job.ov_dash`).
  Alloy's 256 MB reservation once could not place here, so this node shipped
  no logs while the other four looked healthy. Alloy now reserves 128 MB
  (commit `daf8619`). The `memory_max = 256` beside it grants nothing, because
  oversubscription is off at the server. `alloy.hcl` and that commit say the
  opposite, and the measurement in `embark.hcl` wins.
- **Apply ov-dash after phoenix is gone.** Terraform draws no edge between a
  destroy and an unrelated create, so a new job can register while the old
  one still holds memory. Nomad parks a blocked evaluation, which looks like a
  broken deploy and heals itself.
- **If the NVMe move was done, the SD card stays in.** The how-to copies the
  root filesystem to NVMe and points `rootdev=UUID=` in the SD card's
  `/boot/orangepiEnv.txt` at it, so the SD card still boots the machine. The
  repo does not record whether this node was migrated. Check `lsblk` before
  pulling the card.
- **SSH host key changed.** On 2026-07-31 SSH refused the node with `REMOTE
  HOST IDENTIFICATION HAS CHANGED` (U1 plan), again on 2026-08-22 (SY1 plan
  review). The cause is not recorded. Check the key before trusting it.
- **Stale apt cache.** U4 found this node still offering Consul `1.22.6-1`
  as its candidate while the repo listing was correct. Run `apt update`
  before an upgrade.
- **The Nomad agent outlived an outage.** In the 2026-07-31 advertise
  incident this node's agent stayed up since 2026-04-26, dialing
  `10.88.0.1`, and its allocations kept rendering Vault templates while Nomad
  counted it down (U3 plan).

## If orangepi4a goes down

- Every bucket is gone: Loki and Tempo cannot flush to object storage,
  the registry cannot serve a blob, so embark cannot pull a model on its next
  start, OpenViking loses its blob store, and `backup-minio` fails.
- `minio.lab`, `s3.lab` and `openviking.lab` (ov-dash) stop answering.
- `minio_data` is on this node only. The nightly backup copies one bucket,
  `openviking`, to GCS ([GCS backups](/components/gcs-backups.md)). The other
  buckets have no copy.

Related: [host volumes](/components/host-volumes.md),
[the host firewall](/components/host-firewall.md),
[the observability pipeline](/components/observability-pipeline.md).
