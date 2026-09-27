---
type: component
title: Node placement
description: "Five nodes on 192.168.2.0/24: firebat is the only amd64 host and runs every server, the four arm64 workers each carry a fixed set of jobs. Placement is by hostname constraint, host volume and literal IP, so moving a job touches four places and one of them is on the node."
tags: [nodes, hardware, nomad, placement, firewall, ansible]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: inventory
    resource: git:3ec5d1e:bootstrap/inventory/cluster.ini
  - id: consul-client-template
    resource: git:3ec5d1e:bootstrap/roles/consul_client/templates/consul.hcl.j2
  - id: nomad-client-template
    resource: git:3ec5d1e:bootstrap/roles/nomad_client/templates/nomad.hcl.j2
  - id: configure-tailscale
    resource: git:3ec5d1e:bootstrap/playbooks/configure_tailscale.yml
  - id: configure-nvidia-ctk
    resource: git:3ec5d1e:bootstrap/playbooks/configure_nvidia_ctk.yml
  - id: infra-services
    resource: git:3ec5d1e:deployments/infrastructure/services.tf
  - id: apps-services
    resource: git:3ec5d1e:deployments/applications/services.tf
  - id: apps-justfile
    resource: git:3ec5d1e:deployments/applications/justfile
  - id: U4-upgrade-consul-2x
    resource: loop:U4-upgrade-consul-2x
  - id: U3-upgrade-nomad-2x
    resource: loop:U3-upgrade-nomad-2x
---

# Node placement

Five hosts on `192.168.2.0/24`. Every job is pinned to one of them by name,
and nothing reschedules a job elsewhere when its node dies. This page covers
what is common to all five. Each node has its own page in this section:
[firebat](/nodes/firebat.md), [orangepi4a](/nodes/orangepi4a.md),
[jetson-orin-nano](/nodes/jetson-orin-nano.md), [ubuntu](/nodes/ubuntu.md)
and [radxa-dragon-q6a](/nodes/radxa-dragon-q6a.md).

## The five hosts

A node has up to three names, and they differ. The inventory name is what
Ansible uses. The Nomad hostname (`attr.unique.hostname`) is what every job
constraint and host volume matches. The Consul client template sets
`node_name = "{{ inventory_hostname }}"`, so a worker's Consul node name is
its inventory name, not its hostname.

| Inventory | SSH user | Address | Nomad hostname | OS and arch | Role |
|---|---|---|---|---|---|
| `firebat` | `firebat` | 192.168.2.30 | `firebat` | Ubuntu noble, amd64 | manager: Consul server, Vault, Nomad server and client, Tailscale subnet router |
| `orange_pi_4a` | `orangepi` | 192.168.2.29 | `orangepi4a` | Ubuntu jammy, arm64 | worker |
| `jetson_nano` | `localstack` | 192.168.2.46 | `jetson-orin-nano` | Ubuntu jammy, arm64 | GPU worker |
| `raspberry_pi_4b` | `raspberry` | 192.168.2.47 | `ubuntu` | Ubuntu noble, arm64 | worker |
| `radxa` | `radxa` | 192.168.2.50 | `radxa-dragon-q6a` | Ubuntu noble, arm64 | worker |

The OS and arch column comes from the per-node apt output recorded in the U4
plan. The Raspberry Pi's hostname is the generic `ubuntu`, so a constraint
reading `value = "ubuntu"` means that board, not the distribution.

The SSH user in this table appears three times in the repo: the inventory,
and the `ssh_user` of each `null_resource.firewall` entry in both Terraform
roots. They must agree.

A sixth board, an Orange Pi RV2 (riscv64), is planned in
[the RISC-V worker proposal](/proposals/riscv-worker-node.md) and is not in
the inventory.

## What runs where

Every service and batch job carries a `constraint` on
`attr.unique.hostname`. Only `node-exporter` and `alloy` are `system` jobs and
run everywhere.

| Node | Jobs | Host volumes |
|---|---|---|
| [`firebat`](/nodes/firebat.md) | haproxy, postgres | `postgres` |
| [`orangepi4a`](/nodes/orangepi4a.md) | minio, ov-dash | `minio_data` |
| [`jetson-orin-nano`](/nodes/jetson-orin-nano.md) | embark | `embark_data`, `memex_data` |
| [`ubuntu`](/nodes/ubuntu.md) | prometheus, grafana, loki, tempo, registry, acme | `prometheus_data`, `grafana_data`, `loki_data`, `tempo_data`, `acme_lego_state` |
| [`radxa-dragon-q6a`](/nodes/radxa-dragon-q6a.md) | hermes, bifrost, openviking, dash, registry-ui, driftwatch, redis, nats, both oauth2-proxy jobs, backup-postgres, backup-minio | `hermes_data`, `openviking_data`, `driftwatch_data`, `registry_ui_data`, `nats_data` |

Why each node holds what it does, and what stops when it goes down, is on
that node's page.

## Architecture

firebat is the only amd64 node. The images the applications justfile builds
(hermes, dash, registry-ui) are built with `--platform linux/arm64` in
`deployments/applications/justfile`, so none of them can run on firebat.
Upstream images used on firebat must publish an amd64 variant.

`install_dependencies.yml` maps `aarch64` and `x86_64` to HashiCorp's
`arm64` and `amd64` and nothing else. A RISC-V board needs cross-compiled
binaries and a new map entry, which
[the RISC-V worker proposal](/proposals/riscv-worker-node.md) plans and
nothing has built.

## Per-node configuration

- Workers reserve 500 MHz CPU, 512 MB memory and 10 GB disk for the host
  (`nomad_client` template). firebat's server template has a `client` block
  with no reservation.
- Every Nomad agent advertises one explicit address. Without it a restart can
  advertise the podman bridge `10.88.0.1` and the cluster loses its clients
  (see [Ansible bootstrap](/components/bootstrap.md)).
- Worker Nomad clients talk to their local Consul agent on `127.0.0.1:8500`.
  firebat's agent uses `192.168.2.30:8500`. All reach Vault at
  `http://192.168.2.30:8200` over plain HTTP.
- Only firebat runs Tailscale. It advertises `192.168.2.0/24`, and
  `configure_tailscale.yml` stops `tailscaled` on the workers. Only firebat
  admits SSH from the tailnet range `100.64.0.0/10`.
- `configure_network.yml` gives every node ufw default deny, SSH and the
  HashiStack ports from `192.168.0.0/16`. Per-service ports are added by the
  Terraform roots.

## Moving a job to another node

A job's placement is written in up to four places, and nothing checks that
they agree:

1. The hostname constraint, usually a `*_hostname` value passed to
   `templatefile` in the root's `services.tf`, sometimes a literal in the
   jobspec.
2. The `*_host` IP literal next to it, and any other job that dials this one
   by IP.
3. The host volume in `deployments/infrastructure/services.tf`, which does
   not follow the job. The comment on `embark_data` says so: move one without
   the other and the job stops placing.
4. The `firewall_rules` entry (`host` and `ssh_user`). Terraform adds the new
   rules but never deletes the old ones, so the old node stays open until
   someone runs `ufw delete` on it. Rules on other nodes that admit this job's
   node as a caller (`allow from <address>`) have to follow it too.
   [ufw rules outside user.rules](/practices/ufw-rules-outside-user-rules.md)
   has the details.

A volume's data does not move either, and nothing in the repo copies it.

## Node setup notes

- Every node needs the repo's `.ssh/id_rsa` public key and passwordless sudo
  before Ansible can run (`bootstrap/README.md`).
- Board-specific setup (the Jetson's flashing notes, the Orange Pi's move to
  NVMe) is on [jetson-orin-nano](/nodes/jetson-orin-nano.md) and
  [orangepi4a](/nodes/orangepi4a.md).

Related: [host volumes](/components/host-volumes.md),
[the host firewall](/components/host-firewall.md) and
[the Tailscale subnet router](/components/tailscale-subnet-router.md).
