---
type: component
title: The Tailscale subnet router on firebat
description: "Only firebat joins the tailnet, and it advertises 192.168.2.0/24 so remote devices reach the whole LAN, the edge included. Workers have tailscaled stopped. The role applies routes only on first join, and on 2026-08-01 ufw on firebat was measured not filtering tailnet traffic."
tags: [tailscale, ansible, bootstrap, subnet-route, netsec]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: tailscale-role
    resource: git:3ec5d1e:bootstrap/roles/tailscale/tasks/main.yml
  - id: configure-tailscale
    resource: git:3ec5d1e:bootstrap/playbooks/configure_tailscale.yml
  - id: seed-vault
    resource: git:3ec5d1e:bootstrap/playbooks/seed_vault.yml
  - id: bootstrap-justfile
    resource: git:3ec5d1e:bootstrap/justfile
  - id: configure-network
    resource: git:3ec5d1e:bootstrap/playbooks/configure_network.yml
  - id: tailscale-role-apply-routes-when-joined
    resource: loop:tailscale-role-apply-routes-when-joined
  - id: N4-netsec-edge-only-service-access
    resource: git:3ec5d1e:.loop/verdicts/N4-netsec-edge-only-service-access.plan-validator.md
  - id: N1-netsec-restrict-prometheus-loki-to-cluster
    resource: loop:N1-netsec-restrict-prometheus-loki-to-cluster
---

# The Tailscale subnet router on firebat

Remote access to the cluster is one Tailscale node. firebat, the manager,
joins the tailnet and advertises `192.168.2.0/24` as a subnet route. A
laptop on the tailnet then reaches every LAN address through firebat, and
because lab names resolve publicly to `192.168.2.30`
([ADR 0003](/decisions/0003-lab-names-resolve-from-public-dns.md)),
`https://*.lab.orangecluster.nl` works off-site with no extra DNS. No other
node runs Tailscale.

## The pieces

| Piece | Where |
| --- | --- |
| Role: IP forwarding, install, `tailscale up` | `bootstrap/roles/tailscale/tasks/main.yml` |
| Playbook: manager joins with routes, workers stop `tailscaled` | `bootstrap/playbooks/configure_tailscale.yml` |
| Auth key, playbook run before Vault exists | `TAILSCALE_AUTH_KEY` from the environment |
| Auth key, later runs | Vault KV `bootstrap/tailscale`, field `auth_key`, written by `bootstrap/playbooks/seed_vault.yml` |
| Order | `just bootstrap` in `bootstrap/justfile` ([bootstrap](/components/bootstrap.md)) runs `configure_tailscale.yml` and then `configure_network.yml`, which enables ufw |

The playbook reads the key from Vault with the root token in
`/opt/vault/init.json` when that file exists, and from the environment only
when Vault is not initialized yet. Under `just bootstrap`, `seed_vault.yml`
writes the key to Vault first, so the play reads Vault. Once Vault exists a
rotated key must be written there, because the playbook ignores the
environment variable. Rotation is an unbuilt
[proposal](/proposals/bootstrap-credential-rotation.md).

The role runs `tailscale up --advertise-routes=... --accept-routes` and sets
`net.ipv4.ip_forward=1` in `/etc/sysctl.d/99-tailscale.conf`. It supports
userspace networking behind `tailscale_userspace_networking`, but the
playbook does not set it, so firebat uses the kernel `tailscale0` interface.
Route approval is manual in the Tailscale admin console. The repository has
no ACL file and no auto-approvers.

## What the tailnet reaches

- **Everything on firebat, as last measured.** On 2026-08-01 the N4 plan
  review found tailscaled's `ts-input` chain ahead of ufw, accepting all
  traffic on `tailscale0`, and saw a tailnet peer connected to Vault on 8200,
  which ufw opens to `192.168.0.0/16` only. While that chain order holds,
  every firebat port is open to the tailnet whatever the rule set says.
  Nobody has re-measured it.
- **The LAN, through the route.** ufw's forward policy is `ACCEPT`, so
  routed traffic is not filtered on firebat. What reaches a worker depends on
  the worker's own rules and on the source address a packet arrives with.
  Nothing in the repository records that address. Measure it before relying
  on a `192.168.2.30` single-caller rule to keep tailnet clients out.
- **Workers run no Tailscale.** Whether their `100.64.0.0/10` rules, such
  as Grafana's on ubuntu, ever match depends on that same unmeasured source
  address. The role never sets `--snat-subnet-routes`, so it runs on
  Tailscale's default. The documented path to Grafana is the edge, where
  HAProxy dials ubuntu from `.30`.

The [host firewall](/components/host-firewall.md) has the rest of the rule
picture.

## Trap: routes are applied only on first join

`tailscale up` runs only when `tailscale status --json` fails or
`BackendState` is not `Running`. On a node that is already joined, the role
never compares or re-applies `--advertise-routes`, and the play still ends
green. In September 2026 firebat advertised no route, remote clients lost
the LAN and every lab name, and the operator restored it by hand:

```
sudo tailscale set --advertise-routes=192.168.2.0/24
```

followed by approving the route in the admin console. The cause of the loss
is unknown. `--advertise-routes` has been in the role since `a9b2f22`.

Re-running `configure_tailscale.yml` does not fix this, so check the route
from a remote device, not from the play result.

## Planned, not built

`tailscale-role-apply-routes-when-joined` is in planning. Its plan passed
review with required fixes. It would add a `routes.yml` that reads
`tailscale debug prefs`, runs `tailscale set` only when `AdvertiseRoutes` or
`RouteAll` differ, fails the play if that unstable output changes shape, and
warns, without failing, when `.Self.PrimaryRoutes` shows the route
unapproved. It would also be the repository's first Ansible behavior test,
real `ansible-playbook` against a fake `tailscale` on `PATH`. None of this
exists yet.

C1 (blocked) would have CI join the tailnet as `tag:ci` to reach the cluster.
N4 (planning) found that it cannot narrow tailnet access with ufw alone.
