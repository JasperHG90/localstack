---
epic = "netsec"
depends_on = ["N3-netsec-converging-firewall-provisioner"]
priority = 50
summary = "Close direct LAN access to every service that has an edge route, so `*.lab.orangecluster.nl` over TLS is the only way in. Measured today: Nomad, Vault, Consul, MinIO, grafana, bifrost, memex and an unauthenticated haproxy stats page all answer on plaintext to any host on 192.168.0.0/16, and mlflow (192.168.2.50:5050) plus phoenix (192.168.2.29:6006) answer 200 with NO credentials while the edge answers 401, which is a live authentication bypass. Rules come from THREE provisioners, not two. Ships the recovery runbook for the outage this change makes possible."
tags = ["netsec", "ufw", "haproxy", "tls", "runbook"]
---

# N4 — Only `*.lab.orangecluster.nl` reaches a service

## Title

Narrow the firewall so every HTTP service with an edge route is reachable
only through haproxy on 443, move this repo's own tooling onto the edge
hostnames, and write the runbook for recovering when the edge itself is what
broke.

## Size / Effort

**L.** The rule edits are small. The weight is in four places: rules come from
**three** provisioners, none of which removes a rule, so narrowing one leaves
the broad one live (see below, it reshapes the whole ticket); the exposure set
is twelve services across five hosts, not five services on two; several of
those ports have an in-cluster consumer on a *different* node, so the
narrowing target is per-service rather than "the edge"; and the change creates
a new failure mode where the only route to Nomad runs through a job Nomad
schedules.

## Triggered by

Operator finding, 2026-07-31: "the main url for services can be bypassed by
using IP or other addresses (e.g. `http://firebat:4646/ui/` instead of
`https://nomad.lab.orangecluster.nl/ui/`). Only `*.lab.orangecluster.nl`
should be allowed."

Confirmed, and wider than reported. Two of the bypassed services are
**authenticated at the edge and unauthenticated on the LAN**.

## Context (today's state)

### Measured exposure

Every one of these answered from the devcontainer, over plaintext, bypassing
the edge entirely. All verified 2026-07-31, and re-verified by the plan
reviewer the same day:

| Direct URL | Result | Edge route | Edge answers |
| --- | --- | --- | --- |
| `http://192.168.2.30:4646/` Nomad UI + API | 307 to `/ui/`, then 200 | `nomad.` | 200 |
| `http://192.168.2.30:8200/` Vault UI + API | 200 | `vault.` | 200 |
| `http://192.168.2.30:8500/` Consul UI + API | 200 | `consul.` | 200 |
| `http://192.168.2.29:9001/` MinIO console | 200 | `minio.` | 200 |
| `http://192.168.2.29:9000/` MinIO S3 API | 200 | `s3.` | 200 |
| `http://192.168.2.50:5050/` **mlflow** | **200, no auth** | `mlflow.` | **401** |
| `http://192.168.2.29:6006/` **phoenix** | **200, no auth** | `phoenix.` | **401** |
| `http://192.168.2.46:8000/` memex | 401 | `memex.` | 401 |
| `http://192.168.2.50:8080/` bifrost | 200 | `bifrost.` | 200 |
| `http://192.168.2.47:3000/` grafana | 302 | `grafana.` | 302 at `/`, 200 at `/api/health` |
| `http://192.168.2.50:8642/` hermes | 404 (reachable) | none, reached via memex | n/a |
| `http://192.168.2.30:8404/` haproxy stats | **200, no auth** | none | n/a |
| `http://firebat:4646/` via mDNS | 307 | same socket, resolved by name | n/a |

**mlflow and phoenix are an authentication bypass, not merely a plaintext
one.** haproxy gates both with
`http-request auth unless { http_auth(openfang_users) }`
(`deployments/infrastructure/services/haproxy.hcl:143` phoenix,
`:153` mlflow). The direct ports enforce nothing. Anyone on
`192.168.0.0/16` reads both with no credentials while the front door asks for
a password. This is the strongest single reason the ticket exists, and every
scored row must reach it.

**The haproxy stats page is the next worst.** It is unauthenticated, it is on
the tailnet (`deployments/infrastructure/services.tf:191-192`), and it
publishes the whole backend topology: every server IP, every port, every
health state.

**8404 is not the only thing on the tailnet.** `100.64.0.0/10` also reaches
Grafana 3000 (`deployments/infrastructure/services.tf:222`) and port 8080 on
the rpi4b (`:231`, the `nomad_pack_applications_ubuntu` entry). Note that
this 8080 is a *different host and service* from bifrost's 8080 on radxa,
which comes from the applications root. Confirmed on the host: the rpi4b's ufw
table carries `3000/tcp ALLOW 100.64.0.0/10` and `8080/tcp ALLOW
100.64.0.0/10`. R8 covers all three, not just 8404.

`firebat.local:4646` does **not** resolve from the devcontainer today
(curl returns 000 / timeout). Only the bare `firebat:4646` form is a live
route, and only that form is worth scoring.

### Where the rules come from

**Three provisioners.** `grep -rn ufw` across the repo returns exactly three
sources.

- **Ansible base rules**, `bootstrap/playbooks/configure_network.yml`. Manager
  block at `:9-25`, worker block at `:34-46`. Opens 8500, 8300, 8301, 8600,
  8200, 8201, 4646, 4647, 4648 and the Nomad dynamic port range
  `20000:32000` to `192.168.0.0/16`, plus port 22. Default incoming policy is
  `deny` (`bootstrap/roles/firewall/tasks/main.yml:7-13`), so the explicit
  allows are the whole exposure.
- **Terraform infrastructure map**, `deployments/infrastructure/services.tf`,
  `local.firewall_rules` at `:163-277` driving `null_resource.firewall`
  (`:279-295`, remote-exec `:286-294`, `sudo ufw` at `:293`). Opens MinIO
  9000/9001 (`:174-182`), haproxy 80/443/8404 (`:183-194`, the 8404 pair at
  `:191-192`), the registry 5000/5001, Prometheus 9090 (`:208-215`, already
  narrow), Grafana 3000 (`:217-224`), 8080 on the rpi4b (`:226-233`),
  Postgres 5432, the node exporters (`:235-259`, already narrow) and NATS.
- **Terraform applications map**, `deployments/applications/services.tf:22-102`
  (map `:23-82`, remote-exec `:93-101`, `sudo ufw` at `:100`). A second
  `null_resource.firewall` with its own map and its own SSH connections.
  It owns phoenix 6006 and 4317 (`:29-30`), memex 8000 (`:38`),
  hermes 8642 (`:46-47`, already narrow), loki 3100 (`:59-63`, already
  narrow), mlflow 5050 (`:71`) and bifrost 8080 (`:79`).

**Every inventory, requirement and subticket in this plan must cover all
three.** The applications map is where mlflow and phoenix, the two bypasses,
actually live. A change that edits only the first two roots closes nothing
that matters.

`20000:32000` open to the LAN is a standing hole rather than a live one: no
running allocation uses a port in that range today and nothing listens there
(checked with `/v1/allocations?resources=true` and `ss -ltn` on firebat and
radxa). Closing it is correct hygiene and it is scored as a rule-set
assertion, not as a socket probe against a port with no listener.

**The precedent for the fix is in the same file as the defect.** The loki
entry in the applications map already states this ticket's principle
(`deployments/applications/services.tf:50-54`): *"The push and query APIs have
no authentication, so the LAN-wide rule is gone."* Phoenix 6006 has no
authentication and is LAN-wide. Prometheus 9090 in the infrastructure map
carries the same reasoning (`:204-207`), as do the `node_exporter_*` entries
(`:235-259`) and hermes (`applications/services.tf:41-48`), all from N1.

### The narrowing target, per service

"Narrow `from_ip`" is meaningless without saying to what. haproxy dials four
non-local backends (`haproxy.hcl:127-157`), Prometheus on `192.168.2.47`
scrapes several of these ports, and **seven jobs dial a service on another
node**. The target set is therefore per service and load-bearing.

The table below was derived by sweeping every jobspec under
`deployments/*/services/` for a service address, not from haproxy's backend
list. That distinction matters: haproxy's backends are the *edge* consumers,
and the misses that break a cluster are the ones haproxy never sees.

| Port and host | Must still admit | Evidence |
| --- | --- | --- |
| nomad 4646, consul 8500 on `.30` | `.30` (edge, node-local), `.47` (Prometheus), **`.50`** (hermes) | `prometheus.hcl:85`, `:92`; `hermes.hcl:205-206`, `:451-452` |
| **vault 8200 on `.30`** | `.30`, **and every Nomad client: `.29`, `.46`, `.47`, `.50`** | `haproxy.hcl:134`; `acme.hcl:163` on `.47`; **and `nomad_client/templates/nomad.hcl.j2:33-36`** — every client carries `vault { enabled = true, address = "http://<server>:8200" }`, and `bootstrap/inventory/cluster.ini` puts all four workers in `[worker]`. Verified live: the `nomad` process on `.50` holds a connection to `192.168.2.30:8200` |
| minio 9000/9001 on `.29` | `.30` (edge), `.47` (Prometheus scrapes 9000, loki stores chunks), **`.46`** (memex file store), **`.50`** (mlflow artifacts, backup-minio) | `haproxy.hcl:128`, `:131`; `prometheus.hcl:105`; `loki.hcl:119`; `memex.hcl:122`; `mlflow.hcl:50`; `backup-minio.hcl:37`, pinned to radxa by `:13-16` |
| **phoenix 6006 on `.29`** | `.30` (edge) **and `.46`** (memex sends traces) | `haproxy.hcl:144`; `memex.hcl:143` |
| phoenix 4317 on `.29` | no edge route and no consumer found in the repo; narrow to `.46` alongside 6006 and confirm phoenix still records traces | `applications/services.tf:30` |
| memex 8000 on `.46` | `.30` (edge) **and `.50`** (hermes dials memex) | `haproxy.hcl:147`; `hermes.hcl:203`, `:449` |
| bifrost 8080 on `.50` | `.30` (edge), **`.46`** (memex dials bifrost), `.47` (Prometheus) | `haproxy.hcl:157`; `memex.hcl:148`, `:155`, `:158`; `prometheus.hcl:119` |
| mlflow 5050 on `.50` | `.30` (edge) only. No in-cluster consumer exists | `haproxy.hcl:154` |
| grafana 3000 on `.47` | `.30` (edge) only | `haproxy.hcl:150` |
| 8404 on `.30` | `.47` (Prometheus) only, per Q2 | `prometheus.hcl:96` |

**Consul authenticates nobody, so closing the port is its only control.**
Measured 2026-08-01: `bootstrap/roles/consul_server/templates/consul.hcl.j2:29-32`
sets `tokens { default = <agent token> }`, and the client role does the same at
`consul_client/templates/consul.hcl.j2:16-19`. Every request arriving without a
token therefore resolves to the agent's identity, which holds `node_prefix`,
`service_prefix`, `agent_prefix` and `session_prefix ""` at write.
Unauthenticated against `192.168.2.30:8500`: 25 services, 5 nodes, 41 health
checks, and a 200 on `/ui/`. `default_policy = "deny"` is set and never
applies.

Two consequences for this ticket. Closing the port is the whole of the control
— there is no second layer behind it. And **after N4 the catalog is still
readable with no credential through the edge**, because the edge forwards to
the same unauthenticated listener. That is not this ticket's job to fix, and it
must not be described as fixed. It is filed separately.

**The cross-node consumers are the trap.** memex runs on jetson_nano
`192.168.2.46` and phoenix on orange_pi_4a `192.168.2.29`, so narrowing
phoenix 6006 to the edge alone silently kills tracing: memex keeps posting to
`http://${phoenix_host}:6006/v1/traces` and the packets are dropped. The same
holds for memex 8000 (hermes on radxa dials it), bifrost 8080 (memex dials
it), minio 9000 (memex, mlflow and the nightly backup dial it from two other
nodes) and nomad/consul (hermes dials both from radxa). The shape to copy is
the existing hermes entry, `applications/services.tf:41-48`, which lists the
edge and the one in-cluster caller and nothing else.

**Vault 8200 is the sharpest of these and it is the one that closes the cert
loop.** acme runs on the rpi4b (`acme.hcl:17-20` pins it to `ubuntu`) and
dials `http://192.168.2.30:8200` directly, and the jobspec says why two lines
above the address (`acme.hcl:158-161`): *"VAULT_ADDR is the direct listener,
not the edge: routing this through the proxy would make certificate renewal
depend on the certificate it renews."* Narrow 8200 to the edge alone and TLS
renewal dies quietly, roughly 60 days later, taking the edge with it. This is
the same loop R7's runbook covers, arriving through a third door.

### The finding that reshapes this ticket

**No provisioner removes a rule. Narrowing one leaves the broad one live.**

The Ansible role loops `ufw allow` over `firewall_ufw_ports`
(`bootstrap/roles/firewall/tasks/main.yml:15-22`) with no removal step. Both
Terraform maps are create-only (`infrastructure/services.tf:286-294`,
`applications/services.tf:93-101`). Changing a `from_ip` from
`192.168.0.0/16` to a node IP **adds a narrower rule and leaves the wide one
in place**. `ufw` then matches the wide one and the port stays open.

**This is not a prediction. It is already live on a host.** `sudo ufw status
numbered` on radxa shows `[10] 8642/tcp ALLOW IN 192.168.0.0/16` surviving
beside `[12] 8642/tcp ALLOW IN 192.168.2.30` and `[14] ... 192.168.2.46`,
while the repo declares **only** the two narrow rules
(`applications/services.tf:46-47`). Hermes is LAN-reachable today despite a
repo that says it is not. The exact failure this ticket must avoid has already
happened once, to the entry this plan holds up as the good pattern.

`N3-netsec-converging-firewall-provisioner` exists to fix this on the
Terraform side, and its Context names **both** Terraform roots
(`deployments/infrastructure/services.tf:279-295` and
`deployments/applications/services.tf:85-101`), so it converges the
applications map too. Quoting its summary: *"runs `ufw allow` once at create
and has no destroy step, so removed rules stay open on the host and host-side
drift is invisible."*

Five consequences:

0. **N3 is `blocked`, not `ready`.** It was blocked on 2026-08-01 because no
   `plan-validator` verdict has ever run against it — its premise has never
   been attacked. Subticket 1 is therefore *"get N3 reviewed, unblocked and
   landed"*, not *"land N3"*. **N4 cannot be judged final until N3's premise
   has been attacked**, because Q1's scope bound rests on N3's mirror
   constraint holding.

1. **N3 is not merely a dependency; it is the only thing that makes the
   Terraform half take effect.** Do it first — after clearing item 0.
2. **The Ansible half needs the same treatment** and N3 does not cover it.
   See Q1.
3. **This ticket must then narrow both Terraform maps**, including the
   applications one N3 will have taught to converge.
4. **Every check that reads a config file is worthless here.** The config can
   be perfect while the host is untouched. Verification comes from a socket,
   from a host that is not a cluster node.

### What makes this feasible

- **The edge proxies the full API, not just the UI.** Verified:
  `https://nomad.lab.orangecluster.nl/v1/agent/health`,
  `https://vault.lab.orangecluster.nl/v1/sys/health`,
  `https://consul.lab.orangecluster.nl/v1/status/leader`,
  `https://s3.lab.orangecluster.nl/minio/health/live` and
  `https://grafana.lab.orangecluster.nl/api/health` all return 200. So
  Terraform and the CLI can move to the edge without losing anything.
- **haproxy runs on firebat**, the same host as the Nomad server, Vault and
  the Consul server (alloc `974b69bf` on node `a898783a`, single server
  `firebat.global` at 192.168.2.30). Closing 4646, 8200 and 8500 to the LAN
  does not separate haproxy from those three backends. It does **not** follow
  that every backend is node-local: haproxy dials `.29`, `.46`, `.47` and
  `.50` as well, which is what the per-service target table above is for.
- **haproxy already returns 503 for an unknown Host on 443**, so there is no
  default backend to fall through to. Port 80 answers 301 to https for an
  unknown Host, so the 503 guarantee is a 443 guarantee.
- **SSH stays open** on port 22 and is the recovery path, with the limit
  recorded in R4: LAN on every node, tailnet on firebat only.

### What this repo points at today

- `.devcontainer/.env.example` uses **mDNS names**, not IPs:
  `NOMAD_ADDR=http://localstack.local:4646` (`:3`),
  `CONSUL_HTTP_ADDR=http://localstack.local:8500` (`:7`),
  `VAULT_ADDR=http://localstack.local:8200` (`:11`),
  `MINIO_ENDPOINT=http://orangepirv2.local:9000` (`:23`). Those names resolve
  to the same sockets this ticket closes, so the template breaks for the next
  person unless it moves to the edge with everything else.
- The operator's real `.devcontainer/.env` does use raw IPs: `NOMAD_ADDR`
  (`:3`), `CONSUL_HTTP_ADDR` (`:6`), `VAULT_ADDR` (`:9`) and
  `AWS_ENDPOINT_URL_S3=http://192.168.2.29:9000` (`:18`).
- `deployments/applications/providers.tf:40` hardcodes
  `address = "192.168.2.30:8500"` for Consul, with the comment that the
  provider does not read the address from an env var.
- `deployments/applications/providers.tf:45` builds the MinIO provider address
  as `"${data.consul_service.minio.service[0].node_address}:9000"`, so a plan
  or refresh from the devcontainer dials MinIO 9000 directly.
  `minio_iam_user` and `minio_accesskey` resources exist
  (`deployments/applications/storage.tf:46`, `:51`), so this is exercised on
  every plan. Closing 9000 to non-cluster hosts breaks the applications root
  unless this moves too.
- `deployments/applications/providers.tf:51` builds the Postgres provider host
  the same way, but 5432 is a declared non-goal and is not being closed.

Moving these to the edge is an upgrade rather than a cost: the Vault listener
is `tls_disable: true`, so every credential this repo sends today crosses the
LAN in the clear.

## Non-goals / out of scope

- **The openfang basic-auth password in the haproxy jobspec is a separate
  ticket.** `random_password.openfang_basic_auth.result` is interpolated into
  the jobspec at `deployments/infrastructure/services.tf:322`, and the running
  job carries it as a **literal**: `nomad job inspect haproxy` returns one
  `insecure-password` with a real value (`haproxy.hcl:89`), not a template
  reference. Both Nomad policies grant `read-job`: `deploy` at
  `deployments/infrastructure/nomad_deploy_role.tf:21`, and `developer` at
  `bootstrap/roles/nomad_server/files/nomad_developer_policy.hcl:8`, applied
  by `bootstrap/roles/nomad_server/tasks/main.yml:184`. So the credential that
  protects mlflow and phoenix at the edge is
  readable by anyone who can read a Nomad job. **Closing the firewall does not
  fix this**, and fixing it here would mean redeploying the edge in the middle
  of a ticket that removes every other way in. It needs its own ticket:
  render the password from Vault through a `template` stanza the way the TLS
  cert already is (`haproxy.hcl:62-72`), so it never enters the jobspec.
  Raise that ticket before this one closes and reference it here.
- **No authentication at the edge.** This ticket funnels traffic; it does not
  gate it. `G2` puts SSO on Nomad, `G1` on Grafana, `L1` on the rest. Reaching
  `https://nomad.lab.orangecluster.nl` still gets you the UI afterwards, and
  that is the intended state at the end of this ticket. mlflow and phoenix
  keep the basic-auth they already have at the edge, which is exactly the gate
  the direct ports bypass today.
- **No change to Postgres 5432, the registry, loki 3100, NATS or the
  exporters.** None has an edge route, so "use the hostname instead" has no
  meaning for them, and loki, Prometheus and the exporters are already narrow.
  Record them as knowingly untouched, and do not quietly widen scope to a
  database port.
- **hermes 8642 is in scope, but only as cleanup.** The repo already declares
  it narrow (`applications/services.tf:46-47`) and this ticket adds no rule
  for it. What it must do is confirm the stale `192.168.0.0/16` entry on radxa
  is gone once N3's convergence runs, because that stale entry is this plan's
  proof that shadowing is real. `http://192.168.2.50:8642/` answers today. If
  it still answers from a non-cluster LAN host after the change, N3 did not
  converge and every other closure in this ticket is suspect. R8 and the
  broad-rule eval row therefore include 8642, even though no rule text
  changes.
- **No tailscale rollout to the workers.** Only firebat has tailscale
  (`bootstrap/playbooks/configure_tailscale.yml:3`, `hosts: manager`).
  Installing it on four more nodes to widen the recovery path is a separate
  decision with its own blast radius. R4 states the recovery path that exists
  rather than the one this plan would like.
- **No tailnet firewall redesign.** Opening the cluster APIs to
  `100.64.0.0/10` is a separate decision (`D4` Q5 already defers to it). This
  ticket adds tailnet access to nothing; it removes it from 8404, 3000 and the
  rpi4b's 8080.
- **No IPv6 work.** `IPV6=no` in the role today. Leave it.
- **No change to intra-cluster ports** 4647, 4648, 8300, 8301, 8201, 8600.
  Those are cluster-internal protocols, not services with an edge route.

## Requirements & restrictions

- **R1. Verification comes from a socket, never from a config file.** Every
  closure is proven by attempting the connection from a LAN host that is not a
  cluster node and observing a refusal or timeout. A rule present in
  `configure_network.yml` or either `services.tf` proves nothing, because no
  provisioner removes the rule it replaces, and radxa's surviving 8642 rule is
  the live proof.
- **R2. Capture the negative control BEFORE changing anything.** Record the
  current response for each row in the exposure table. A test that only shows
  "refused afterwards" cannot distinguish a working firewall from a typo in
  the URL.
- **R3. The broad rule is deleted, not shadowed.** After the run,
  `ufw status numbered` on each node shows **no** `192.168.0.0/16` entry for
  any closed port, on any of the three provisioners' rules. An added narrow
  rule beside a surviving broad one is the expected failure mode, not a
  hypothetical.
- **R4. SSH on 22 is untouched, and the recovery path is what exists, not
  what we wish existed.** firebat keeps 22 from `192.168.0.0/16` **and**
  `100.64.0.0/10` (`configure_network.yml:10-11`). The four workers keep 22
  from `192.168.0.0/16` only (`:35`) and have no tailscale at all
  (`configure_tailscale.yml:3` targets `manager`). Any change that touches
  port 22 fails the ticket. The runbook (R7) must say plainly that off-LAN
  recovery reaches firebat over the tailnet and reaches a worker only by
  hopping through firebat.
- **R5. haproxy keeps reaching its backends, and the backends keep reaching
  each other.** All ten edge hostnames serve after the change. Every
  destination in the per-service target table above still admits every source
  listed beside it: acme on `.47` to vault 8200, hermes on `.50` to nomad 4646
  and consul 8500, memex on `.46` to phoenix 6006 and bifrost 8080, hermes to
  memex 8000, memex/mlflow/backup-minio to minio 9000 from `.46` and `.50`,
  loki on `.47` to minio 9000, and Prometheus on `.47` to 4646, 8500, 9000,
  8080, 8404 and the exporters. **The target table is the contract here, and
  it was built by sweeping the jobspecs, not by reading haproxy's backends.**
  Any new consumer found during implementation joins the table before the rule
  is narrowed.
- **R6. This repo's own addresses move to the edge in the same change.**
  `.devcontainer/.env` (all four of `:3`, `:6`, `:9`, `:18`),
  `.devcontainer/.env.example` (all four entries, which
  are mDNS names today, not IPs), the hardcoded Consul provider address
  (`applications/providers.tf:40`), the MinIO provider address
  (`applications/providers.tf:45`, which dials
  `<consul node address>:9000` from the devcontainer) **and both Terraform
  state backends** (`deployments/infrastructure/vars/backend-config.hcl:1-3`
  and `deployments/applications/vars/backend-config.hcl:1-3`, each
  `address = "192.168.2.30:8500"` with `scheme = "http"`). The state backend
  is dialed by `just init` before any provider runs, so missing it fails both
  roots one step earlier than the provider addresses do. A change that closes
  the ports without moving all of them breaks `terraform plan` for everyone
  including the person applying it.
- **R7. Ship the recovery runbook, and pin its facts.** `docs/` gains a
  runbook covering every way this change can strand you, with each command
  verified to work. It must name **both** circular dependencies: haproxy is a
  Nomad job behind haproxy, and haproxy's TLS PEM is rendered from Vault
  (`haproxy.hcl:39`, `:62-72`) while `just unseal_vault` runs
  `scripts/unseal_vault.sh` against `$VAULT_ADDR` from the devcontainer, so a
  sealed Vault plus a haproxy restart leaves no edge to unseal through.
  Follow `D5-cli-breakglass`'s rule: facts in the runbook are pinned to the
  repo file that states them, so drift fails a gate rather than going stale
  silently.
- **R8. Every service with an edge route loses its LAN-wide rule, and the
  tailnet loses everything but 80/443 and SSH to firebat.** Named:
  nomad 4646, vault 8200, consul 8500, minio 9000/9001, phoenix 6006 (+4317),
  memex 8000, bifrost 8080, mlflow 5050, grafana 3000, plus hermes 8642 as
  cleanup of the stale rule (see non-goals). Tailnet entries to
  remove: 8404 (`infrastructure/services.tf:192`), grafana 3000 (`:222`) and
  the rpi4b's 8080 (`:231`). 8404 additionally goes to the Prometheus host
  only, per Q2. **mlflow 5050 and phoenix 6006 are the priority rows**: they
  are the two where the direct port defeats an authentication check the edge
  performs.
- **R9. Bootstrap still works from cold.** `just bootstrap` on a fresh node
  must converge. Ansible talks to services during provisioning, before
  haproxy exists, so anything it does over the network must be node-local or
  explicitly permitted.

## Code surface

- `bootstrap/playbooks/configure_network.yml:9-25` (manager) and `:34-46`
  (worker) — narrow `from_ip` for 4646, 8500 and `20000:32000` in both blocks,
  and for 8200 in the manager block only (the worker block has no 8200 entry;
  Vault is manager-only). Leave port 22 and the intra-cluster ports alone.
- `bootstrap/roles/firewall/tasks/main.yml` — gains removal, per Q1. Default
  deny at `:7-13` stays; the allow loop is `:15-22`.
- `deployments/infrastructure/services.tf` — the `local.firewall_rules` map
  (`:163-277`): `minio` (`:174-182`), `haproxy` (`:183-194`, the 8404 pair at
  `:191-192`), `grafana` (`:217-224`), `nomad_pack_applications_ubuntu`
  (`:226-233`). Provisioner at `:286-294`.
- `deployments/applications/services.tf:22-102` — the **third** map:
  `phoenix` (`:25-32`), `memex` (`:34-40`), `mlflow` (`:67-73`),
  `bifrost` (`:75-81`). `hermes` (`:41-48`) and `loki` (`:50-65`) are already
  narrow and are the pattern to copy.
- `deployments/applications/providers.tf:38-42` — Consul provider address.
- `deployments/applications/providers.tf:44-48` — MinIO provider address.
- `deployments/infrastructure/vars/backend-config.hcl:1-3` and
  `deployments/applications/vars/backend-config.hcl:1-3` — the Consul state
  backend, dialed by `just init` on plaintext 8500.
- `.devcontainer/.env.example` (`:3`, `:7`, `:11`, `:23`) and the operator's
  `.devcontainer/.env`.
- **NEW** `docs/edge-and-recovery.md` — the runbook from R7.
- Read-only, as the consumer evidence behind the target table:
  `deployments/applications/services/memex.hcl:122`, `:143`, `:148`, `:155`,
  `:158`; `deployments/applications/services/hermes.hcl:203`, `:205-206`,
  `:449`, `:451-452`; `deployments/applications/services/mlflow.hcl:50`;
  `deployments/applications/services/loki.hcl:119`;
  `deployments/infrastructure/services/acme.hcl:17-20`, `:158-163`;
  `deployments/infrastructure/services/backup-minio.hcl:13-16`, `:37`;
  `deployments/infrastructure/services/prometheus.hcl:85`, `:92`, `:96`,
  `:105`, `:119`.
- Possibly `deployments/infrastructure/services/haproxy.hcl` for 8404
  (`:120-125`).

## Tests & validation gates

Repo gate: `just pre_commit`. The eval marker
`.loop/evals/N4-netsec-edge-only-service-access.md` carries the scored rows,
and its verification is deliberately socket-level for the reason in R1.

## Risk assessment

- **High: locking yourself out.** ufw is applied over SSH. A rule ordering
  mistake that drops 22 ends the session and the recovery is physical access,
  and for the four workers there is no tailnet fallback at all (R4).
  Mitigated by R4 and by applying to one worker first, per the subticket
  order.
- **High: the circular dependencies this creates.** Two of them. First, the
  only route to Nomad's API becomes haproxy, and haproxy is a job Nomad
  schedules; the escape is SSH to firebat and
  `NOMAD_ADDR=http://127.0.0.1:4646`. Second, haproxy's TLS PEM comes from
  Vault (`haproxy.hcl:39`, `:62-72`) and `just unseal_vault` drives
  `$VAULT_ADDR` from the devcontainer, so a sealed Vault plus a haproxy
  restart means no edge and no way to unseal except SSH. Both belong in R7's
  runbook, written before the change is applied.
- **High: killing a cross-node consumer silently.** vault 8200, nomad 4646,
  consul 8500, minio 9000, phoenix 6006, memex 8000 and bifrost 8080 each have
  an in-cluster consumer on a different node. Narrow any of them to the edge
  alone and nothing errors loudly: traces stop arriving, memex's model calls
  and file store fail, hermes loses Nomad and Consul, mlflow loses its artifact
  store, the nightly GCS backup stops, and **acme stops renewing the edge's own
  certificate**, which surfaces about 60 days later as an expired edge.
  Covered by R5 and the target table, and the table must be re-derived from the
  jobspecs rather than from haproxy's backend list.
- **Medium: silently changing nothing.** Covered by R1 and R3, and already
  observed on radxa's 8642 rule. The most likely bad outcome is a green ticket
  over an unchanged host.
- **Medium: breaking the deployer.** Terraform runs from the devcontainer,
  which is on the LAN and therefore loses direct access, including the MinIO
  provider's 9000 dial. Covered by R6.
- **Low: intra-cluster breakage.** Nomad client to server, Vault to Consul,
  and Prometheus scraping all stay on ports this ticket does not touch or on
  rules the target table preserves, but they are asserted anyway.

## Subtickets (ordered)

1. **Land N3 first.** Without a converging Terraform provisioner, steps 6 and
   7 are no-ops on the host. It is `ready` and needs no gate.
2. **Record the negative controls** (R2). Every URL in the exposure table,
   with its current response, from the devcontainer and from a non-cluster
   LAN host. Include the mlflow and phoenix unauthenticated 200s, which are
   the pair the ticket is judged on.
3. **Raise the openfang credential ticket** (see non-goals) so the exposure
   is tracked rather than absorbed here.
4. **Write `docs/edge-and-recovery.md` first** (R7), covering both circular
   dependencies and the manager-only tailnet path. It is the thing you will
   need if step 7 goes wrong.
5. **Ansible rule removal** (Q1) plus the narrowed base rules, applied to a
   single worker first and verified before the manager.
6. **Move this repo's addresses to the edge** (R6, including
   `providers.tf:45` and both `vars/backend-config.hcl`) and prove both
   Terraform roots still `init` and plan clean.
7. **Apply to the manager.** The dangerous step. Keep an open SSH session to
   firebat throughout.
8. **Narrow the infrastructure map**: 8404, grafana 3000, the rpi4b 8080,
   minio 9000/9001.
9. **Narrow the applications map**: phoenix 6006 and 4317, memex 8000,
   mlflow 5050, bifrost 8080, each to the source set in the target table,
   copying the shape of the existing `hermes` entry.
10. **8404** per Q2.
11. Full verification sweep, including the cross-node consumer probes from R5.

## Open questions (operator must settle)

> **All four questions were resolved on 2026-07-31 in
> `## Forks resolved, 2026-07-31` at the end of this plan.** Each followed the
> recommendation recorded below, so these read as history rather than as
> pending decisions.


**Q1 — how does the Ansible half remove a rule?**
The role only adds. Options: (a) teach the role to reconcile, deleting ufw
rules it no longer declares, mirroring what N3 does for Terraform; (b) a
one-off `ufw delete` task listing exactly the rules this ticket retires;
(c) `ufw --force reset` then re-apply the full set.
*Recommendation:* (a), **scoped to the ports the Ansible role itself
declares**. It is the same defect N3 fixes on the Terraform side and leaving
one provisioner converging while the other only accumulates guarantees this
recurs. The scope bound is not optional: a role that prunes everything not in
`firewall_ufw_ports` deletes every Terraform-owned rule on the next
`just bootstrap`, taking minio 9000/9001, haproxy 80/443, grafana 3000 and the
exporters with it. N3 carries the mirror-image constraint on its side ("the
prune is deliberately scoped so it cannot touch the Ansible half",
`.loop/evals/N3-netsec-converging-firewall-provisioner.md`), and the two
halves only compose if both hold. (c) is rejected outright: a reset drops port
22 for the window between reset and re-apply, over the SSH connection doing
the work.

**Q2 — 8404: close it, or move it behind the edge?**
Today it is unauthenticated on LAN and tailnet, and it leaks the backend map.
Options: (a) restrict to the Prometheus host only, since
`http-request use-service prometheus-exporter if { path /metrics }`
(`haproxy.hcl:122`) means scraping is its real job; (b) route it through the
edge as `haproxy.lab.orangecluster.nl` behind the existing `openfang_users`
basic-auth userlist; (c) both.
*Recommendation:* (a), and drop the human stats UI entirely. Prometheus
already scrapes it (`prometheus.hcl:96`), Grafana already renders it, and a
second unauthenticated view of the same data is not worth an exposure. (b) is
additionally weak while the `openfang_users` password is readable from the
running jobspec (see non-goals).

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

## Forks resolved, 2026-07-31

All four settled on their recorded recommendations.

- **Q1 → (a), teach the Ansible firewall role to reconcile, scoped to the
  ports it declares.** It deletes the ufw rules it no longer declares,
  mirroring what N3 does on the Terraform side, and it touches nothing else.
  **The scope bound is part of the decision**, not a refinement: an unbounded
  prune wipes every Terraform-owned rule on the next `just bootstrap`, and the
  eval row below scores both halves. Rejected (b), a one-off `ufw delete`
  list, because it fixes this ticket's rules and leaves the next narrowing to
  hit the same bug; the accumulate-only role is the defect, not these
  particular rules. Rejected (c) outright: `ufw --force reset` drops port 22
  for the window between reset and re-apply, over the SSH connection doing the
  work.
  **This is now scored on its own.** The eval previously checked only that the
  broad rule was gone, which a manual `ufw delete` satisfies while leaving the
  role unchanged. A row now requires the role itself to reconcile, and to
  leave the Terraform-owned rules standing.
- **Q2 → (a), restrict 8404 to the Prometheus host and drop the human stats
  UI.** Scraping is its real job: `haproxy.hcl:122` already serves
  `/metrics` via `http-request use-service prometheus-exporter`, and
  `prometheus.hcl:96` scrapes it. Grafana renders it, so a second
  unauthenticated view of the same data is not worth an exposure, least of all
  one on the tailnet.
  **Note the positive control this creates:** 8404 must remain reachable
  **from the Prometheus host** `192.168.2.47`, or scraping breaks silently and
  the only symptom is an empty dashboard days later. Closing it to everything
  is a failure, not an over-achievement.
- **Q3 → no devcontainer exception.** It moves to the edge like everything
  else. Direct access is what the runbook's SSH path is for, and an allowance
  for "the developer's machine" is not expressible in ufw without pinning a
  DHCP address that will change. A guardrail row now checks no rule is keyed
  to a non-cluster host.
- **Q4 → keep the ten explicit `hdr(host)` ACLs, add no wildcard and no
  default backend.** That list is the allowlist. A wildcard
  `hdr(host) -m end .lab.orangecluster.nl` plus a default backend would route
  unknown names somewhere instead of refusing them, which inverts the point of
  the ticket. Verified today that an unknown Host returns 503 on 443 (port 80
  answers 301 to https); that behavior is now a scored row so a later
  convenience edit cannot quietly remove it.
