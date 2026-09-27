---
type: node
title: ubuntu, the observability node
description: "The Raspberry Pi 4B (192.168.2.47), whose Nomad hostname is the generic ubuntu, runs Prometheus, Grafana, Loki, Tempo, the OCI registry and the nightly ACME renewal. Its address is the scrape source that most service firewall rules admit, so moving the monitoring stack means rewriting rules on every node, and losing it silences every alert."
tags: [node, ubuntu, raspberry-pi, arm64, prometheus, grafana, loki, tempo, registry, acme]
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
  - id: registry-jobspec
    resource: git:3ec5d1e:deployments/applications/services/registry.hcl
  - id: tempo-jobspec
    resource: git:3ec5d1e:deployments/applications/services/tempo.hcl
  - id: acme-jobspec
    resource: git:3ec5d1e:deployments/infrastructure/services/acme.hcl
  - id: grafana-jobspec
    resource: git:3ec5d1e:deployments/infrastructure/services/grafana.hcl
  - id: alloy-jobspec
    resource: git:3ec5d1e:deployments/infrastructure/services/alloy.hcl
  - id: registry-added
    resource: git:f1091dc:deployments/applications/services/registry.hcl
  - id: tempo-added
    resource: git:9a84f24:deployments/applications/services/tempo.hcl
  - id: sy1-node-probe
    resource: git:3ec5d1e:.loop/verdicts/SY1-switchyard-deployment.plan-validator.snapshot.md
  - id: N1-netsec-restrict-prometheus-loki-to-cluster
    resource: loop:N1-netsec-restrict-prometheus-loki-to-cluster
  - id: U1-upgrade-pin-hashistack-versions
    resource: loop:U1-upgrade-pin-hashistack-versions
---

# ubuntu, the observability node

`ubuntu` is a Raspberry Pi 4B whose hostname was never changed from the
distribution default. A constraint reading `value = "ubuntu"` means this
board. The cross-node picture is [node placement](/nodes/placement.md).

| Fact | Value | Source |
|---|---|---|
| Names | inventory `raspberry_pi_4b` (also its Consul node name), Nomad `ubuntu`, SSH user `raspberry`. Comments call it `rpi4b` | `bootstrap/inventory/cluster.ini` |
| Address | `192.168.2.47` | same |
| Board | Raspberry Pi 4B (from the inventory name) | same |
| OS and arch | Ubuntu noble, arm64 | U1 plan |
| CPU, RAM | 4 CPUs. 2.6 GiB available on 2026-08-22, before Tempo and the registry arrived on 2026-09-01. Total not recorded | SY1 plan review |
| Nomad | client, pool `default`, no node class, worker reservation | [placement](/nodes/placement.md) |
| Tailnet | not on it, `tailscaled` stopped | `bootstrap/playbooks/configure_tailscale.yml` |

## What runs here

Every job below is pinned by a literal `value = "ubuntu"` in its jobspec.

| Job | Ports | Why here |
|---|---|---|
| `prometheus` (1000 MHz, 1024 MB) | 9090 | The monitoring stack was planned for firebat and shipped here. [The original build plan](/components/monitoring-stack.md) records the change. |
| `grafana` (500 MHz, 256 MB) | 3000 | Same stack. Its datasources dial `192.168.2.47` on this node. |
| `loki` (500 MHz, 512 MB) | 3100, gRPC 9095 | Same stack. |
| `tempo` (500 MHz, 768 MB) | 3200, gRPC 9096, OTLP 4317 and 4318 | "Colocated with the rest of the observability stack" (commit `9a84f24`). |
| `registry` (100 MHz, 256 MB) | 5000, debug 5001 | Stateless, so placement was a capacity question. firebat refused it, and next to MinIO it would save nothing (`registry.hcl`, commit `f1091dc`). See [container registry](/components/container-registry.md). |
| `acme` (periodic, 04:00 daily) | none | Pinned with its `acme_lego_state` volume. See [the ACME job](/components/acme-certificate-job.md). |

The system jobs `node-exporter` and `alloy` run here too. `registry.hcl`
puts the node's commitment at about 3050 MHz and 2.7 GB.

Host volumes: `prometheus_data` (5 to 50 GiB), `grafana_data` (1 to 5 GiB),
`loki_data` and `tempo_data` (2 to 10 GiB each, unflushed data only), and
`acme_lego_state` (100 MiB to 1 GiB).

## Firewall rules that name this node

| Rule | Where |
|---|---|
| Worker base ports from `192.168.0.0/16` | `bootstrap/playbooks/configure_network.yml` |
| `prometheus` 9090 from `.47` and `.30`, `grafana` 3000 from the LAN and the tailnet, `node_exporter_ubuntu` 9100 from `.47` | `deployments/infrastructure/services.tf` |
| `nomad_pack_applications_ubuntu` 8080 from the LAN and the tailnet. No job here listens on 8080 | same |
| `loki` 3100 and Tempo's 4317 and 4318 from all five node addresses, Tempo's 3200 from `.47` and `.30`, `registry` 5000 from `.30` | `deployments/applications/services.tf` |

`192.168.2.47` is also the source address that Prometheus scrapes from, so
rules on the other nodes admit it: node-exporter on all five, postgres_exporter
on firebat, embark on the Jetson, NATS's exporter, OpenViking and driftwatch
on radxa. Moving Prometheus off this node means rewriting each of those.

## What dials it by literal address

- Alloy on every node pushes logs to `192.168.2.47:3100` and traces to
  `192.168.2.47:4317` (`alloy.hcl`).
- OpenViking's `ov.conf.json` exports traces straight to `192.168.2.47:4317`,
  and the OTLP example in
  `deployments/applications/services/dash/tiles.json` does too.
- Grafana's three datasources, Prometheus's own scrape targets, and HAProxy's
  `grafana` and `registry` backends.
- `docs/reference/monitoring.md` and the how-to pages under `docs/how-to/`
  tell users to send telemetry to this address.

## Quirks and traps

- **Two ports collided.** Loki holds gRPC 9095 under `network_mode = "host"`,
  so Tempo's gRPC moved to 9096. Alloy takes OTLP on 4319 and 4320 because
  Tempo holds 4317 and 4318 here, and a system job that claimed them would
  fail to place on this node.
- **Rules outside `user.rules`.** N1 found live ufw rules here, Grafana's
  among them, that were in the chain and not in the file, so any ufw write
  could drop them. See
  [ufw rules outside user.rules](/practices/ufw-rules-outside-user-rules.md).
- **Monitoring does not watch itself.** Grafana's alerts are evaluated here.
  If this node stops, no alert fires about it.

## If ubuntu goes down

- No metrics, logs, traces, dashboards or alerts, and no Telegram message to
  say so.
- The registry stops: embark cannot pull a model on its next start, and
  registry-ui shows nothing.
- Certificate renewal stops. `run --renew-days 30` gives about 30 days
  before the edge certificate expires and every lab name fails together.

Related: [the observability pipeline](/components/observability-pipeline.md),
[host volumes](/components/host-volumes.md),
[the host firewall](/components/host-firewall.md).
