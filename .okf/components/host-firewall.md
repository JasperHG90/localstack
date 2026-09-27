---
type: component
title: The host firewall (ufw) and the three things that write it
description: "Each node runs ufw with default-deny inbound. Ansible opens the platform ports, and a null_resource in each Terraform root opens service ports over SSH. Neither Terraform half can remove a rule, the two roots re-run on different triggers, and on 2026-08-01 ufw was measured not filtering the tailnet on firebat."
tags: [ufw, firewall, terraform, ansible, netsec, tailscale]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: firewall-role
    resource: git:3ec5d1e:bootstrap/roles/firewall/tasks/main.yml
  - id: configure-network
    resource: git:3ec5d1e:bootstrap/playbooks/configure_network.yml
  - id: infra-services
    resource: git:3ec5d1e:deployments/infrastructure/services.tf
  - id: apps-services
    resource: git:3ec5d1e:deployments/applications/services.tf
  - id: always-run-trigger
    resource: git:fef7eee:deployments/infrastructure/services.tf
  - id: N1-netsec-restrict-prometheus-loki-to-cluster
    resource: loop:N1-netsec-restrict-prometheus-loki-to-cluster
  - id: N2-netsec-remove-dnsmasq-for-public-dns
    resource: loop:N2-netsec-remove-dnsmasq-for-public-dns
  - id: N3-netsec-converging-firewall-provisioner
    resource: git:3ec5d1e:.loop/verdicts/N3-netsec-converging-firewall-provisioner.plan-validator.md
  - id: N4-netsec-edge-only-service-access
    resource: git:3ec5d1e:.loop/verdicts/N4-netsec-edge-only-service-access.plan-validator.md
---

# The host firewall (ufw) and the three things that write it

Every node runs ufw, and three writers share its rule database,
`/etc/ufw/user.rules`. Ansible writes the platform ports once at bootstrap.
Each Terraform root writes the ports of the services it deploys, by running
`sudo ufw allow ...` over SSH. None of the three removes a rule it no longer
declares, so the rule map in a `.tf` file records what was added. A host
can have more open than any map says. The lessons behind this page, measured
on the live hosts, are [ufw rules outside user.rules](/practices/ufw-rules-outside-user-rules.md).

## The three writers

| Writer | File | Owns | Runs |
| --- | --- | --- | --- |
| Ansible `firewall` role | `bootstrap/roles/firewall/tasks/main.yml`, ports in `bootstrap/playbooks/configure_network.yml` | SSH, Consul, Vault, Nomad, the Nomad dynamic range `20000:32000` | `configure_network.yml`, the last step of `just bootstrap` |
| `null_resource.firewall`, infrastructure root | `local.firewall_rules` in `deployments/infrastructure/services.tf` | Postgres, postgres_exporter, MinIO, HAProxy, Prometheus, Grafana, node-exporter, Redis, NATS, oauth2-proxy, and 8080 on ubuntu open to the LAN and tailnet (`nomad_pack_applications_ubuntu`) | every `terraform apply` |
| `null_resource.firewall`, applications root | `local.firewall_rules` in `deployments/applications/services.tf` | ov-dash, Hermes, Loki, Tempo, embark, registry, Bifrost, dash, OpenViking, driftwatch | only when an entry's `rules` or `host` change |

The Ansible role also sets default deny inbound, allow outbound,
`DEFAULT_FORWARD_POLICY="ACCEPT"`, which leaves forwarded traffic such as
firebat's subnet route unfiltered by ufw, and `IPV6=no`. It uses
`community.general.ufw`, which is idempotent and also never deletes.

Each Terraform map entry is keyed by service, carries the host and the SSH
user, and becomes one `null_resource` whose `remote-exec` runs one
`sudo ufw` line per rule. The SSH key is `.ssh/id_rsa` at the repo root,
which is gitignored, so a fresh git worktree cannot plan either root until it
is linked in (F3 reflection). A service's rule goes in the root that deploys
the service, per `.claude/rules/terraform-file-layout.md` and
[Terraform roots](/components/terraform-roots.md). The registry's rule
moved to the applications root for that reason.

## The two roots re-run differently

The infrastructure root has `always_run = timestamp()` in `triggers`, added in
`fef7eee` so that every apply re-asserts every rule and repairs a rule lost
from the live chain. Two costs follow. Every plan in that root lists all
entries for replacement, so "0 to change" is never the clean result there.
And every apply is a burst of concurrent ufw writes, four of them on firebat
alone. ufw takes its lock only after reading the rule set, so overlapping
writes on one host can drop each other's rule. `just apply` does not pass
`-parallelism=1`.

The applications root triggers on `rules` and `host` only, so an entry runs
once at create and again only when it is edited. A rule lost from the live
chain there stays lost until someone notices.

The N3 plan describes the infrastructure root as `rules`-only. That was true
when it was written and is not now.

## Traps

- **Removing an entry removes nothing on the host.** Neither root has a
  destroy provisioner. `terraform plan` reporting a destroy says nothing about
  the host. N2 destroyed the dnsmasq entry and ports 53/udp and 53/tcp stayed
  open. N1 narrowed Prometheus and Loki and the broad rules stayed live, which
  made the change look done while changing nothing. Finish every narrowing on
  the host, and delete by rule spec, not by number, because
  `ufw status numbered` renumbers after each delete. The comment above
  `null_resource.firewall` in the applications root says to delete by number,
  highest first, which is also safe if followed exactly. Several comments in
  both
  maps carry the exact `ufw delete` line owed for a past edit.
- **A broad rule outranks every narrow one.** A rule for
  `192.168.0.0/16` on a port admits everything the single-caller rules beside
  it were meant to keep out. memex left one on port 8000 on the Jetson that
  outlived the job and covered embark's narrow rules.
- **Any ufw write can drop a rule missing from `user.rules`.** `ufw allow`
  rebuilds the `ufw-user-input` chain from the file. N1 found live rules on
  ubuntu that were in the chain and not in the file, Grafana's among them.
  Compare `iptables -S ufw-user-input` with `user.rules` before a change.
- **Loopback skips the user chain.** ufw accepts `-i lo` in
  `ufw-before-input`, so a host reaching itself on its own LAN address never
  meets these rules. Several entries admit their own host anyway, as a guard
  in case a caller moves.
- **ufw did not gate the tailnet on firebat when measured.** On
  2026-08-01 the N4 plan review found tailscaled's `ts-input` chain ahead of
  ufw's, accepting everything on `tailscale0`, and a tailnet peer holding a
  connection to Vault on 8200, a port ufw opens to the LAN only. While that
  chain order holds, the `100.64.0.0/10` rules on firebat add nothing.
  Whether the same rules on workers ever match depends on the source address
  routed packets carry, which nobody has measured. See the
  [Tailscale subnet router](/components/tailscale-subnet-router.md).

## The single-caller shape

Rules added since N1 admit named callers only. A service behind the
edge admits `192.168.2.30`, HAProxy's node. A service scraped by Prometheus
also admits `192.168.2.47`. A service called by another job admits that job's
node. The comment above each entry names each caller and why, and that list
is the only record of who is expected to connect. Adding a caller means
adding a rule, or its connection times out with no error at the service.

Loki and Tempo list every node on purpose. Alloy pushes logs to Loki from
every node, and a workload on any node may export traces to Tempo, so
dropping one address silently stops that node's data.

## Planned, not built

- N3 (blocked) would make the Terraform half reconcile: add what is missing
  and delete rules the map owns and no longer declares. Its plan review
  (`.loop/verdicts/N3-netsec-converging-firewall-provisioner.plan-validator.md`)
  failed it on premise: the reconcile would not run on a plain apply, the
  first-apply migration errors, and the prune scope deletes nothing. The
  ledger's blocker text, which says no review ever ran, is stale. The ufw lock
  race above is from that same review.
  `docs/how-to/narrow-the-monitoring-firewall-rules.md` is the manual version
  today.
- N4 (planning) would close direct LAN access to every service with an edge
  route. Its review found the tailnet bypass above, which the plan's
  mechanism cannot close.
