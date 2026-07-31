---
epic = "netsec"
depends_on = ["N3-netsec-converging-firewall-provisioner"]
priority = 50
summary = "Close direct LAN access to every service that has an edge route, so `*.lab.orangecluster.nl` over TLS is the only way in. Measured today: Nomad, Vault, Consul, MinIO and an unauthenticated haproxy stats page all answer 200 on plaintext to any host on 192.168.0.0/16. Ships the recovery runbook for the outage this change makes possible."
tags = ["netsec", "ufw", "haproxy", "tls", "runbook"]
---

# N4 — Only `*.lab.orangecluster.nl` reaches a service

## Title

Narrow the firewall so every HTTP service with an edge route is reachable
only through haproxy on 443, move this repo's own tooling onto the edge
hostnames, and write the runbook for recovering when the edge itself is what
broke.

## Size / Effort

**L.** The rule edits are small. The weight is in three places: neither
provisioner removes a rule today, so narrowing one leaves the broad one live
(see below, it reshapes the whole ticket); every address this repo uses is a
raw IP and has to move in the same change; and the change creates a new
failure mode where the only route to Nomad runs through a job Nomad schedules.

## Triggered by

Operator finding, 2026-07-31: "the main url for services can be bypassed by
using IP or other addresses (e.g. `http://firebat:4646/ui/` instead of
`https://nomad.lab.orangecluster.nl/ui/`). Only `*.lab.orangecluster.nl`
should be allowed."

Confirmed, and wider than reported.

## Context (today's state)

### Measured exposure

Every one of these answered from the devcontainer, over plaintext, bypassing
the edge entirely. All verified 2026-07-31:

| Direct URL | Result | Edge route exists? |
| --- | --- | --- |
| `http://192.168.2.30:4646/` Nomad UI + API | 200 | yes, `nomad.` |
| `http://192.168.2.30:8200/` Vault UI + API | 200 | yes, `vault.` |
| `http://192.168.2.30:8500/` Consul UI + API | 200 | yes, `consul.` |
| `http://192.168.2.29:9001/` MinIO console | 200 | yes, `minio.` |
| `http://192.168.2.29:9000/` MinIO S3 API | 200 | yes, `s3.` |
| `http://192.168.2.30:8404/` haproxy stats | **200, no auth** | no |
| `http://firebat:4646/` via mDNS | 200 | same service, resolved by name |

**The haproxy stats page is the worst of these.** It is unauthenticated, it is
the only thing besides 80/443 reachable from the tailnet
(`100.64.0.0/10`, `services.tf:52-53`), and it publishes the whole backend
topology: every server IP, every port, every health state. It is a map of the
cluster handed to anyone who can reach the tailnet.

### Where the rules come from

Two provisioners, split by concern:

- **Ansible base rules**, `bootstrap/playbooks/configure_network.yml`. Opens
  8500, 8300, 8301, 8600, 8200, 8201, 4646, 4647, 4648 and the Nomad dynamic
  port range `20000:32000` to `192.168.0.0/16` on the manager, and the client
  equivalents on workers. Default incoming policy is `deny`
  (`bootstrap/roles/firewall/tasks/main.yml:7-13`), so these explicit allows
  are the entire exposure.
- **Terraform per-service map**, `deployments/infrastructure/services.tf`,
  `null_resource.firewall`. Opens MinIO 9000/9001, Grafana 3000, haproxy
  80/443/8404, registry 5000/5001, Postgres 5432, and the exporters.

`20000:32000` open to the LAN means **every dynamically-ported Nomad service
is directly reachable**, not just the ones with a named entry.

There is precedent for narrow rules: `prometheus` and the `node_exporter_*`
entries already allow specific host IPs rather than the LAN
(`services.tf:73-74`), from N1.

### The finding that reshapes this ticket

**Neither provisioner removes a rule. Narrowing one leaves the broad one
live.**

The Ansible role loops `ufw allow` over `firewall_ufw_ports`
(`bootstrap/roles/firewall/tasks/main.yml:15-22`) and has no removal step.
Changing a `from_ip` from `192.168.0.0/16` to a node IP **adds a narrower
rule and leaves the wide one in place**. `ufw` then matches the wide one and
the port stays open.

Terraform's half has the identical defect, which is exactly what
`N3-netsec-converging-firewall-provisioner` exists to fix. Quoting its
summary: *"runs `ufw allow` once at create and has no destroy step, so
removed rules stay open on the host and host-side drift is invisible."*

Three consequences:

1. **This ticket depends on N3.** Without it, the Terraform half of the change
   is a no-op on the host.
2. **The Ansible half needs the same treatment** and N3 does not cover it.
   See Q1.
3. **Every check that reads a config file is worthless here.** The config can
   be perfect while the host is untouched. Verification must come from a
   socket, from a host that is not a cluster node.

### What makes this feasible

- **The edge proxies the full API, not just the UI.** Verified:
  `https://nomad.lab.orangecluster.nl/v1/agent/health`,
  `https://vault.lab.orangecluster.nl/v1/sys/health` and
  `https://consul.lab.orangecluster.nl/v1/status/leader` all return 200. So
  Terraform and the CLI can move to the edge without losing anything.
- **haproxy runs on firebat**, the same host as the Nomad server, Vault and
  the Consul server (alloc `974b69bf` on node `a898783a`). Closing those ports
  to the LAN does not separate haproxy from its own backends.
- **haproxy already returns 503 for an unknown Host**, so there is no default
  backend to fall through to.
- **SSH stays open** to LAN and tailnet on port 22, which is the recovery
  path.

### What this repo points at today

All raw IPs, all plaintext:

- `.devcontainer/.env`: `VAULT_ADDR=http://192.168.2.30:8200`,
  `NOMAD_ADDR=http://192.168.2.30:4646`, `CONSUL_HTTP_ADDR` likewise.
- `deployments/applications/providers.tf:40` hardcodes
  `address = "192.168.2.30:8500"` with the comment that the provider does not
  read the address from an env var.

Moving both to the edge is an upgrade rather than a cost: the Vault listener
is `tls_disable: true`, so every credential this repo sends today crosses the
LAN in the clear.

## Non-goals / out of scope

- **No authentication at the edge.** This ticket funnels traffic; it does not
  gate it. `G2` puts SSO on Nomad, `G1` on Grafana, `L1` on the rest. Reaching
  `https://nomad.lab.orangecluster.nl` still gets you the UI afterwards, and
  that is the intended state at the end of this ticket.
- **No change to Postgres 5432 or the registry.** Neither has an edge route,
  so "use the hostname instead" has no meaning for them. Record them as
  knowingly untouched, and do not quietly widen scope to a database port.
- **No tailnet firewall redesign.** Opening the cluster APIs to
  `100.64.0.0/10` is a separate decision with its own blast radius
  (`D4` Q5 already defers to it). This ticket does not add tailnet access to
  anything; it removes it from 8404.
- **No IPv6 work.** `IPV6=no` in the role today. Leave it.
- **No change to intra-cluster ports** 4647, 4648, 8300, 8301, 8201, 8600.
  Those are cluster-internal protocols, not services with an edge route.

## Requirements & restrictions

- **R1. Verification comes from a socket, never from a config file.** Every
  closure is proven by attempting the connection from a LAN host that is not a
  cluster node and observing a refusal or timeout. A rule present in
  `configure_network.yml` or `services.tf` proves nothing, because neither
  provisioner removes the rule it replaces.
- **R2. Capture the negative control BEFORE changing anything.** Record the
  current 200 for each URL in the table above. A test that only shows "refused
  afterwards" cannot distinguish a working firewall from a typo in the URL.
- **R3. The broad rule is deleted, not shadowed.** After the run,
  `ufw status numbered` on each node shows **no** `192.168.0.0/16` entry for
  the closed ports. An added narrow rule beside a surviving broad one is the
  expected failure mode, not a hypothetical.
- **R4. SSH on 22 stays open to `192.168.0.0/16` and `100.64.0.0/10`.** It is
  the recovery path for the failure this ticket creates. Any change that
  touches port 22 fails the ticket.
- **R5. haproxy keeps reaching its backends.** All ten edge hostnames serve
  after the change. haproxy is on firebat with Nomad, Vault and Consul, so
  loopback and node-local traffic must remain permitted.
- **R6. This repo's own addresses move to the edge in the same change.**
  `.devcontainer/.env`, `.devcontainer/.env.example`, and the hardcoded Consul
  provider address. A change that closes the ports without moving the
  addresses breaks `terraform apply` for everyone including the person
  applying it.
- **R7. Ship the recovery runbook, and pin its facts.** `docs/` gains a
  runbook covering every way this change can strand you, with each command
  verified to work. Follow `D5-cli-breakglass`'s rule: facts in the runbook
  are pinned to the repo file that states them, so drift fails a gate rather
  than going stale silently.
- **R8. 8404 loses its tailnet exposure.** Either close it to everything but
  the LAN monitoring host, or put it behind the edge with auth. It must not
  remain an unauthenticated topology map on `100.64.0.0/10`. See Q2.
- **R9. Bootstrap still works from cold.** `just bootstrap` on a fresh node
  must converge. Ansible talks to services during provisioning, before
  haproxy exists, so anything it does over the network must be node-local or
  explicitly permitted.

## Code surface

- `bootstrap/playbooks/configure_network.yml` — narrow `from_ip` for 4646,
  8200, 8500 on manager and workers, and for `20000:32000`.
- `bootstrap/roles/firewall/tasks/main.yml` — gains removal, per Q1.
- `deployments/infrastructure/services.tf` — the `null_resource.firewall`
  map: `minio`, `grafana`, `haproxy` (8404), `nomad_pack_applications_ubuntu`.
- `deployments/applications/providers.tf:38-42` — Consul provider address.
- `.devcontainer/.env.example` and the operator's `.devcontainer/.env`.
- **NEW** `docs/edge-and-recovery.md` — the runbook from R7.
- Possibly `deployments/infrastructure/services/haproxy.hcl` for 8404.

## Tests & validation gates

Repo gate: `just pre_commit`. The eval marker
`.loop/evals/N4-netsec-edge-only-service-access.md` carries the scored rows,
and its verification is deliberately socket-level for the reason in R1.

## Risk assessment

- **High: locking yourself out.** ufw is applied over SSH. A rule ordering
  mistake that drops 22 ends the session and the recovery is physical access.
  Mitigated by R4 and by applying to one worker first, per the subticket
  order.
- **High: the circular dependency this creates.** After the change, the only
  route to Nomad's API is haproxy, and haproxy is a job Nomad schedules. If
  haproxy dies you need Nomad to restart it and Nomad is behind haproxy. The
  escape is SSH to firebat and `NOMAD_ADDR=http://127.0.0.1:4646`. This is
  precisely what R7's runbook exists for; it must be written before the change
  is applied, not after.
- **Medium: silently changing nothing.** Covered by R1 and R3. The most
  likely bad outcome is a green ticket over an unchanged host.
- **Medium: breaking the deployer.** Terraform runs from the devcontainer,
  which is on the LAN and therefore loses direct access. Covered by R6.
- **Low: intra-cluster breakage.** Nomad client to server, Vault to Consul,
  and Prometheus scraping all stay on ports this ticket does not touch, but
  they are asserted anyway.

## Subtickets (ordered)

1. **Record the negative controls** (R2). Every URL in the exposure table,
   with its current response, from the devcontainer and from a non-cluster
   LAN host.
2. **Write `docs/edge-and-recovery.md` first** (R7). It is the thing you will
   need if step 5 goes wrong.
3. **Ansible rule removal** (Q1) plus the narrowed base rules, applied to a
   single worker first and verified before the manager.
4. **Move this repo's addresses to the edge** (R6) and prove both Terraform
   roots still plan clean.
5. **Apply to the manager.** The dangerous step. Keep an open SSH session to
   firebat throughout.
6. **Terraform map narrowing**, which needs N3 landed.
7. **8404** per Q2.
8. Full verification sweep.

## Open questions (operator must settle)

**Q1 — how does the Ansible half remove a rule?**
The role only adds. Options: (a) teach the role to reconcile, deleting ufw
rules it no longer declares, mirroring what N3 does for Terraform; (b) a
one-off `ufw delete` task listing exactly the rules this ticket retires;
(c) `ufw --force reset` then re-apply the full set.
*Recommendation:* (a). It is the same defect N3 fixes on the Terraform side
and leaving one provisioner converging while the other only accumulates
guarantees this recurs. (c) is rejected outright: a reset drops port 22 for
the window between reset and re-apply, over the SSH connection doing the
work.

**Q2 — 8404: close it, or move it behind the edge?**
Today it is unauthenticated on LAN and tailnet, and it leaks the backend map.
Options: (a) restrict to the Prometheus host only, since
`http-request use-service prometheus-exporter if { path /metrics }`
(`haproxy.hcl:129`) means scraping is its real job; (b) route it through the
edge as `haproxy.lab.orangecluster.nl` behind the existing `openfang_users`
basic-auth userlist; (c) both.
*Recommendation:* (a), and drop the human stats UI entirely. Prometheus
already scrapes it, Grafana already renders it, and a second unauthenticated
view of the same data is not worth an exposure. If the operator wants the
stats page for debugging, (c).

**Q3 — does the devcontainer keep any direct access?**
It is on the LAN, so R6 moves it to the edge like everything else. But the
devcontainer is also where recovery happens.
*Recommendation:* no exception. Direct access is what the runbook's SSH path
is for, and an allowance for "the developer's machine" is not expressible in
ufw without pinning a DHCP address that will change.

**Q4 — one hostname per service, or a wildcard ACL in haproxy?**
haproxy currently lists ten explicit `hdr(host)` ACLs. Every new service edits
that file.
*Recommendation:* keep the explicit list. It is the allowlist, and a wildcard
`hdr(host) -m end .lab.orangecluster.nl` with a default backend would route
unknown names somewhere rather than 503-ing them, which is the opposite of
what this ticket is for.
