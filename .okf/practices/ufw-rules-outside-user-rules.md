---
type: practice
title: ufw rules outside user.rules
description: "Any ufw write rebuilds the ufw-user-input chain from /etc/ufw/user.rules, so a live rule missing from that file vanishes on the next write, and narrowing a rule through Terraform never removes the old one. Measured on 2026-07-26 while narrowing the Prometheus and Loki rules."
tags: [ufw, firewall, terraform, monitoring]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-26
sources:
  - id: monitoring
    resource: git:3ec5d1e:docs/monitoring.md
    last_modified: 2026-09-09
---

# ufw rules outside user.rules

The steps that act on these lessons, with the commands and the measured
detail, are in `docs/how-to/narrow-the-monitoring-firewall-rules.md`. This
page records what was learned so the next firewall change starts from it.

## Every ufw write can drop a rule

`ufw allow` and `ufw delete` both rebuild `ufw-user-input` from
`/etc/ufw/user.rules`. A rule that is live in the chain but absent from that
file is gone after the next write of any kind, with no error. A plain
`terraform apply` of a neighboring rule is enough.

On 2026-07-26, `192.168.2.47` held two such rules (Grafana on 3000,
node-exporter on 9100) and `192.168.2.30` held one (9187 from
`192.168.2.47`). Losing the Grafana rule would have taken Grafana down by
every route, tailnet included. Losing the 9100 rule breaks nothing, because
`.47` to `.47` traffic goes over `lo`, which ufw accepts before the user
chain.

Check first: compare `iptables -S ufw-user-input` against the `### tuple ###`
lines in `user.rules`, and use `ufw --dry-run` to see the chain the next write
would leave. Re-assert a missing rule in the same apply that makes the change.

## Terraform never removes an old rule

`null_resource.firewall` runs `ufw allow` and has no destroy provisioner. A
narrowed rule is added beside the broad one, and the broad one stays until
someone deletes it by hand. Until then the change is cosmetic while looking
applied. Delete by rule spec, because `ufw status numbered` renumbers after
every deletion.

## Concurrent writes lose rules

ufw takes `/run/ufw.lock` only after it reads the rule set, so two overlapping
writes can each start from the same state and the second drops the first's
rule. Run applies that touch several rules on one host with
`-parallelism=1`.

## Confirm from outside

A rule still listed in `ufw status` is the failure itself, so confirm a
narrowing from a non-cluster LAN device, not from the host.
