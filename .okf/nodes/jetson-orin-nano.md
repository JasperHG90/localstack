---
type: node
title: jetson-orin-nano, the GPU node
description: "The Jetson Orin Nano (192.168.2.46) is the only GPU, and it serves embark's embedding and rerank models from 7619 MB of memory the GPU and the OS share. Root Podman runs the NVIDIA runtime, the CUDA libraries are bind-mounted by path, memex is parked off it for lack of memory, and losing it stops every embedding in the cluster."
tags: [node, jetson-orin-nano, jetson, gpu, cuda, arm64, embark, memex]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: inventory
    resource: git:3ec5d1e:bootstrap/inventory/cluster.ini
  - id: configure-nvidia-ctk
    resource: git:3ec5d1e:bootstrap/playbooks/configure_nvidia_ctk.yml
  - id: embark-jobspec
    resource: git:3ec5d1e:deployments/applications/services/embark.hcl
  - id: embark-readme
    resource: git:3ec5d1e:deployments/applications/services/embark/README.md
  - id: memex-jobspec
    resource: git:3ec5d1e:deployments/applications/services/memex.hcl
  - id: apps-services
    resource: git:3ec5d1e:deployments/applications/services.tf
  - id: infra-services
    resource: git:3ec5d1e:deployments/infrastructure/services.tf
  - id: haproxy-jobspec
    resource: git:3ec5d1e:deployments/infrastructure/services/haproxy.hcl
  - id: embark-deployed
    resource: git:db51630:deployments/applications/services/embark.hcl
  - id: embark-memory
    resource: git:528ef7f:deployments/applications/services/embark.hcl
  - id: sy1-node-probe
    resource: git:3ec5d1e:.loop/verdicts/SY1-switchyard-deployment.plan-validator.snapshot.md
  - id: U1-upgrade-pin-hashistack-versions
    resource: loop:U1-upgrade-pin-hashistack-versions
---

# jetson-orin-nano, the GPU node

The Jetson is the one node with a GPU, and it runs one service job, embark.
The cross-node picture is [node placement](/nodes/placement.md).

| Fact | Value | Source |
|---|---|---|
| Names | inventory `jetson_nano` (also its Consul node name), Nomad `jetson-orin-nano`, SSH user `localstack` | `bootstrap/inventory/cluster.ini` |
| Address | `192.168.2.46` | same |
| Board | NVIDIA Jetson Orin Nano, firmware above 36.0 | [flashing notes](/practices/jetson-orin-nano-flashing.md) |
| OS and arch | Ubuntu jammy, arm64, like orangepi4a. The other three run noble | U1 and U4 plans |
| CPU, RAM | 6 CPUs, 7619 MB unified memory with no separate VRAM | SY1 plan review (2026-08-22), `embark.hcl` |
| CUDA | libraries at `/usr/local/cuda-12.6/lib64`, cuDNN 9 under `/usr/lib/aarch64-linux-gnu` | `embark.hcl` bind mounts |
| Storage | not recorded. The flashing notes link guides for moving to NVMe after SD card setup, without saying it was done | [flashing notes](/practices/jetson-orin-nano-flashing.md) |
| Nomad | client, pool `default`, no node class, worker reservation | [placement](/nodes/placement.md) |
| Tailnet | not on it, `tailscaled` stopped | `bootstrap/playbooks/configure_tailscale.yml` |

## GPU setup

`bootstrap/playbooks/configure_nvidia_ctk.yml` targets this host alone. It
deletes the broken OCI hook
`/usr/share/containers/oci/hooks.d/oci-nvidia-hook.json`, makes
`nvidia-container-runtime` root Podman's default runtime in
`/etc/containers/containers.conf` (root, because the Nomad Podman driver runs
as root), and sets `no-cgroups = true`, which Jetson/Tegra requires.

The runtime injects the driver but not the toolkit. A job that wants the GPU
needs three things, all measured on this node (`embark.hcl`, commit
`db51630`, and `deployments/applications/services/embark/README.md`):

1. `NVIDIA_VISIBLE_DEVICES=all` and
   `NVIDIA_DRIVER_CAPABILITIES=compute,utility`.
   Without them there is no `libcuda.so.1` and no `/dev/nvhost-*`, and
   onnxruntime falls back to CPU with the health check green.
2. Nine bind mounts, `/usr/local/cuda-12.6/lib64` and eight cuDNN libraries,
   plus `LD_LIBRARY_PATH=/usr/local/cuda/lib64`.
3. `security_opt = ["seccomp=unconfined", "label=disable"]`, because seccomp
   blocks the GPU ioctls on `/dev/nvhost-*` and `/dev/nvmap`.

`memex.hcl` carries the same three. The mounts name `cuda-12.6`, so a
JetPack upgrade that moves the toolkit breaks both jobs.

## What runs here

| Job | Why here |
|---|---|
| `embark` (prestart 200 MHz and 256 MB, server 4000 MHz and 5632 MB), port 8000 | Built for this GPU: `embark_hostname = "jetson-orin-nano"`, "embark is built for the Orin Nano's GPU" (`deployments/applications/services.tf`). Its image, `embark-jetson`, is built and pushed by hand. See [embark](/components/embark.md). |
| `memex`, commented out since 2026-09-04 | Pinned here by a literal in `memex.hcl`. Taken off to give embark the node: memex needs about 6.5 GB and does not fit beside it. The comment above the commented block says to change `memex_host` before bringing it back. See [memex](/components/memex.md). |

The system jobs `node-exporter` and `alloy` run here too.

Host volumes: `embark_data` (5 to 50 GiB, ModelKits that can be pulled again
at the cost of a slow start) and `memex_data` (5 to 50 GiB, kept while the
job is off).

## Firewall rules that name this node

| Rule | Where |
|---|---|
| Worker base ports from `192.168.0.0/16` | `bootstrap/playbooks/configure_network.yml` |
| `node_exporter_jetson` 9100 from `.47` | `deployments/infrastructure/services.tf` |
| `embark` 8000 from `.50` (Bifrost, driftwatch), `.46` (its own Consul check) and `.47` (Prometheus) | `deployments/applications/services.tf` |
| Possibly live, no longer declared: memex's LAN-wide 8000 rule, which covers every narrow rule above | comment above `embark` and above `null_resource.firewall` in `deployments/applications/services.tf` |

As a caller, `192.168.2.46` is admitted by Redis (6379) on radxa for
embark's cache, by Loki and Tempo on ubuntu, and by hermes 8642 on radxa, a
memex-era rule that admits nothing today.

## What dials it by literal address

`embark_host` for Bifrost, `embark_url` for driftwatch, the embark firewall
entry, and Prometheus's scrape targets, all `192.168.2.46`. HAProxy's
`memex` backend also still points at `192.168.2.46:8000`, which is now
embark's port.

## Quirks and traps

- **Memory is shared with the GPU.** Every CUDA allocation is charged to the
  task's cgroup. `NvMapMemAllocInternalTagged ... error 12` is the GPU
  allocator hitting that limit. embark's `memory = 5632` leaves about 967 MB
  for a host baseline measured at about 1019 MB. 6144 would move the failure
  to the host OOM killer (commit `528ef7f`).
- **`memory_max` is not headroom.** Oversubscription is off at the server,
  so the cgroup is set from `memory` alone. This was measured here, with
  `memory=4096/memory_max=5120` producing a 4096 MiB cgroup, and every other
  jobspec that cites the finding points at `embark.hcl`.
- **Reservations did not match the box.** On 2026-08-22, with memex still
  here, the node had 389 MiB available of 7.4 GiB (SY1 plan review). Check
  `free -m` before trusting Nomad's numbers on this host.
- **The memex route reaches embark's port.** `backend memex` in
  `deployments/infrastructure/services/haproxy.hcl` still sends
  `memex.lab.orangecluster.nl` to `192.168.2.46:8000`. embark's rules do not
  admit `.30`, so it should fail its check, unless memex's old LAN-wide rule
  survives on the host.
- **Snap hold.** The flashing notes link an NVIDIA forum fix for snaps
  breaking after an update
  ([flashing notes](/practices/jetson-orin-nano-flashing.md)).

## If jetson-orin-nano goes down

- No embeddings or reranking anywhere. Bifrost's `embark/*` models fail,
  OpenViking's readiness check answers 503, and its search stops.
- driftwatch cannot score, since it dials embark directly.
- Nothing else can take the work: no other node has a GPU, and embark's
  config asks for CUDA alone.

Related: [host volumes](/components/host-volumes.md),
[Bifrost](/components/bifrost.md),
[driftwatch](/components/driftwatch.md),
[Redis](/components/redis.md).
