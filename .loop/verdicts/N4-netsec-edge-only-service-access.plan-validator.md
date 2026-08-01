---
verdict: fail
---

# N4-netsec-edge-only-service-access — plan review (pass id: plan-validator)

Plan reviewed: `/home/vscode/workspace/.loop/plans/N4-netsec-edge-only-service-access.md`
Plan content sha256 (computed here, **not supplied by the briefing**):
`87b7afec5b8e56a00920cd8665d4cb73f006ef91970c21a7ec712b18c9d1ce3d`.
On a `fail` the contract omits the `plan:` line, so no authorizing hash is
written. Note the briefing did not carry an explicit fingerprint; had this been
a pass I would have stopped rather than invent one.

All probes below were run live against the cluster from the devcontainer on
2026-07-31, plus read-only `ssh ... sudo ufw status` on firebat, radxa and the
rpi4b. No mutating command was run.

## Premise verdict: PARTIALLY SOUND, with breaks severe enough to reshape the ticket

The plan's headline mechanism is right and I confirmed it on a live host. Its
**inventory of what is exposed and where the rules come from is wrong**, and
the scope, code surface and eval rows all inherit that error. A ticket built to
this plan can pass every scored row while leaving two authenticated services
reachable unauthenticated on the LAN.

## Per assumption

**P1 — the seven measured URLs answer 200 directly today. HOLDS.**
Re-measured: `192.168.2.30:4646` 307 (UI redirect), `:8200/v1/sys/health` 200,
`:8500/v1/status/leader` 200, `192.168.2.29:9001` 200, `:9000/minio/health/live`
200, `192.168.2.30:8404` 200 with no auth, `http://firebat:4646/` 307.
Caveat: `firebat.local:4646` does **not** resolve from the devcontainer (curl
000/timeout), which matters for the eval row that scores it (see D6).

**P2 — "Two provisioners, split by concern". BREAKS.**
There is a **third**: `deployments/applications/services.tf:22-102`, a second
`null_resource.firewall` with its own map and `sudo ufw` remote-exec
(`applications/services.tf:100`). It declares LAN-wide rules for phoenix 6006 +
4317 (`:29-30`), memex 8000 (`:38`), mlflow 5050 (`:71`) and bifrost 8080
(`:79`). The plan's Context, code surface and subticket list never mention it.
`grep -rn ufw` across the repo returns exactly three sources: the Ansible role,
`infrastructure/services.tf:293`, `applications/services.tf:100`.

**P3 — "Default incoming policy is deny, so these explicit allows are the
entire exposure". BREAKS as written.**
Default-deny itself holds: 3100 (loki), 9080 (promtail), 4317, 7777, 9090 are
all filtered from here. But the plan's enumeration of the allows is missing five
services **that have edge routes**, all of which answered me directly:

| Direct | Result | Edge equivalent |
| --- | --- | --- |
| `http://192.168.2.50:5050/` mlflow | **200** | `https://mlflow.lab...` → **401** |
| `http://192.168.2.29:6006/` phoenix | **200** | `https://phoenix.lab...` → **401** |
| `http://192.168.2.50:8080/` bifrost | 200 | `https://bifrost.lab...` 200 |
| `http://192.168.2.46:8000/` memex | 401 | `https://memex.lab...` 401 |
| `http://192.168.2.47:3000/` grafana | 302 | `https://grafana.lab...` 200 |
| `http://192.168.2.50:8642/` hermes | 404 (reachable) | via memex/haproxy only |

mlflow and phoenix are gated at the edge by `http-request auth unless {
http_auth(openfang_users) }` (`haproxy.hcl:143`, `:153`) and are **wide open on
the LAN**. That is not just a plaintext bypass, it is an authentication bypass,
and it is the strongest case for this ticket — and it is absent from the
exposure table, from Requirements, from the code surface and from every scored
row.

**P4 — neither provisioner removes a rule, so narrowing shadows. HOLDS, and I
found it live.**
Role code confirmed: `bootstrap/roles/firewall/tasks/main.yml:15-22` is a bare
`rule: allow` loop with no `delete`; default deny at `:7-13`. Terraform is
create-only (`infrastructure/services.tf:279-295`). The predicted failure is
already on a host: `sudo ufw status numbered` on radxa shows
`[10] 8642/tcp ALLOW IN 192.168.0.0/16` still live beside
`[12] 8642/tcp ALLOW IN 192.168.2.30` and `[14] ... 192.168.2.46`, while the
repo declares **only** the two narrow rules (`applications/services.tf:46-47`).
Hermes is therefore LAN-reachable despite a repo that says otherwise. This is
the plan's best claim and it is fully vindicated.

**P5 — the edge proxies the full API, not just the UI. HOLDS.**
`https://nomad.lab.orangecluster.nl/v1/agent/health` 200,
`https://vault.lab.orangecluster.nl/v1/sys/health` 200,
`https://consul.lab.orangecluster.nl/v1/status/leader` 200. Also
`s3.../minio/health/live` 200 and `grafana.../api/health` 200.

**P6 — haproxy runs on firebat with the Nomad server, Vault and Consul.
HOLDS; the inference drawn from it is too broad.**
`nomad job status haproxy` → alloc `974b69bf` on node `a898783a`;
`nomad node status` → `a898783a` is firebat; `nomad server members` → single
server `firebat.global` 192.168.2.30, leader; `vault status` unsealed at
`192.168.2.30:8200`. But haproxy's backends are **not** all node-local:
`haproxy.hcl:127-157` dials 192.168.2.29 (minio, s3, phoenix), 192.168.2.46
(memex), 192.168.2.47 (grafana) and 192.168.2.50 (mlflow, bifrost). Any
narrowing on those four hosts must retain `192.168.2.30`. The plan states the
node-local case as if it covered the whole edge.

**P7 — unknown Host returns 503, no default backend. HOLDS.**
`curl -k -H 'Host: bogus.example.com' https://192.168.2.30/` → 503. No
`default_backend` in `haproxy.hcl`. Note port 80 answers 301 (redirect to
https) for an unknown Host, so the 503 guarantee is 443-only; the eval row
should say so.

**P8 — "SSH stays open to LAN and tailnet on port 22, which is the recovery
path". BREAKS for four of five nodes.**
firebat has both (`ufw status numbered` rules `[1] 22 ALLOW 192.168.0.0/16`,
`[2] 22 ALLOW 100.64.0.0/10`). radxa and the rpi4b have **LAN only**, and
`tailscale ip -4` on the rpi4b returns nothing — tailscale is installed on the
manager alone (`bootstrap/playbooks/configure_tailscale.yml:3`, `hosts:
manager`). The worker playbook grants 22 to `192.168.0.0/16` only
(`configure_network.yml:33`). R4 and the SSH eval row assert a state that does
not exist and cannot be reached without widening scope onto tailscale rollout.

**P9 — "8404 is the only thing besides 80/443 reachable from the tailnet".
BREAKS.**
`infrastructure/services.tf:222` allows Grafana 3000 from `100.64.0.0/10` and
`:231` allows 8080 from `100.64.0.0/10`. Confirmed on the host: rpi4b's ufw
table carries `3000/tcp ALLOW 100.64.0.0/10` and `8080/tcp ALLOW
100.64.0.0/10`. The tailnet already reaches Grafana and 8080 directly.

**P10 — `20000:32000` means every dynamically-ported job is directly
reachable. VACUOUS today.**
Zero of the 24 running allocations use a port in that range: every allocated
host port is static (`/v1/allocations?resources=true` → jq filter for
20000..32000 returns 0). `ss -ltn` on firebat and radxa shows no listener in
the range. Closing it is still correct hygiene, but the plan presents it as a
live exposure driver and the eval hangs a 100% row on probing a port that does
not exist (see D5).

**P11 — the dependency on N3 is correct. HOLDS, and it is sufficient for the
Terraform mechanism.**
N3's own Context names both roots: `deployments/infrastructure/services.tf:279-295`
and `deployments/applications/services.tf:85-101`
(`.loop/plans/N3-netsec-converging-firewall-provisioner.md`, Context). So N3
will make the applications root converge too. The gap is on N4's side: it must
then narrow that map, and it never says so.

**P12 — cited anchors resolve. BREAKS (three of them).**
- `services.tf:52-53` (claimed: the tailnet exposure of 8404) is
  `nomad_dynamic_host_volume "memex_data"`'s constraint block. Real location:
  `infrastructure/services.tf:188-192`. Cited in the plan's Context and in eval
  row 6.
- `services.tf:73-74` (claimed: prometheus / node_exporter narrow rules) is
  `nomad_dynamic_host_volume "hermes_data"`. Real: `:212-213` (prometheus) and
  `:235-258` (node exporters).
- `haproxy.hcl:129` (claimed: `http-request use-service prometheus-exporter`)
  is `server s3_1 192.168.2.29:9000 check`. Real: `haproxy.hcl:122`. Cited
  three times (plan Q2, plan Forks-resolved, eval row 7).
Anchors that do resolve: `bootstrap/roles/firewall/tasks/main.yml:7-13` and
`:15-22`; `applications/providers.tf:38-42` and `:40`.

**P13 — `.devcontainer/.env.example` points at raw IPs. BREAKS in detail.**
`.env.example` uses mDNS names (`NOMAD_ADDR=http://localstack.local:4646`,
`VAULT_ADDR=http://localstack.local:8200`,
`MINIO_ENDPOINT=http://orangepirv2.local:9000`). The operator's real
`.devcontainer/.env` does use IPs (`:3`, `:6`, `:9`). The eval row that says the
template is "on `http://192.168.2.30:8200`" describes a file that does not say
that. The requirement survives; the rationale is wrong.

**P14 — R6's list of addresses to move is complete. BREAKS.**
`applications/providers.tf:45` builds the MinIO provider address as
`"${data.consul_service.minio.service[0].node_address}:9000"`, and `:51` does
the same for Postgres. `minio_iam_user` / `minio_accesskey` resources exist
(`applications/storage.tf:46,51`), so a plan/refresh from the devcontainer dials
MinIO on 9000 directly. Closing 9000/9001 to non-cluster hosts breaks
`terraform plan` in the applications root, and neither R6 nor the code surface
mentions this file. The "both roots plan clean" eval row would catch it, but at
implementation time, as a surprise.

**P15 — the runbook covers every way this change can strand you.
UNCERTAIN → incomplete.**
The plan names one loop (haproxy is a Nomad job; Nomad is behind haproxy). There
is a second: haproxy's TLS PEM is rendered from Vault
(`haproxy.hcl:39`, `:62-72`), and `just unseal_vault` runs
`scripts/unseal_vault.sh` against `$VAULT_ADDR` from the devcontainer
(`.devcontainer/.env:9`). After the migration, a sealed Vault plus a haproxy
restart means no edge, and no edge means no way to unseal except SSH. That is
the same trap in a second shape and the runbook rows do not name it.

## Most dangerous assumption

**P2/P3 — the plan's inventory of rule sources and of what is exposed.**
Everything downstream inherits it: the seven-URL exposure table, R6, the code
surface, and the eval's `Direct access is refused` row, which scores exactly
those seven URLs. Implement this plan to the letter and
`http://192.168.2.50:5050/` (mlflow) and `http://192.168.2.29:6006/` (phoenix)
still answer **200 with no credentials**, while the edge answers 401 — and every
row in the marker is green. The eval's own Definition of Done ("every service
with an edge route is reachable only through `https://<name>...`") is not
enforced by any row it carries.

## Eval marker: rows that cannot fail, or cannot pass

- **D5 (unscorable).** Row 5, "Pick a live allocation's dynamic port from
  `nomad alloc status`, then connect to it directly ... Refused." No running
  allocation uses 20000:32000 and nothing listens in the range on firebat or
  radxa. There is no subject to probe; the row is unexecutable as written.
  Rewrite it to schedule a throwaway job with a dynamic port, or to assert the
  absence of the ufw range rule plus a refusal on an arbitrary in-range port.
- **D6 (half vacuous).** Row 4 requires both `firebat:4646` and
  `firebat.local:4646` to be refused. `firebat.local` already fails to resolve
  from the devcontainer today, so that half passes before any change. Only the
  bare `firebat` form is a real measurement.
- **D63 (unsatisfiable).** The SSH row requires 22 open from `192.168.0.0/16`
  **and** `100.64.0.0/10` on all five nodes with both connections succeeding.
  Four nodes have no tailnet rule and no tailscale (see P8). As written the row
  forces a scope expansion the plan lists nowhere.
- **D2 (under-scoped).** The refusal row covers seven URLs and misses 5050,
  6006, 8000, 8080, 8642 and 3000 — the six that matter most.
- **D46/D50 anchors.** Rows 6 and 7 cite `services.tf:52-53` and
  `haproxy.hcl:129`; both are wrong (P12).

## Required fixes before this plan leaves PLANNING

1. **Add the third provisioner.** `deployments/applications/services.tf:22-102`
   joins the Context, the code surface and the subticket order.
2. **Extend the exposure table and R-list to every service with an edge
   route**: mlflow 5050, phoenix 6006, memex 8000, bifrost 8080, grafana 3000,
   hermes 8642 (and 4317, 9119 as their siblings). Call out that mlflow and
   phoenix are an **auth** bypass, not merely a plaintext one
   (`haproxy.hcl:143`, `:153`).
3. **Fix P9's claim and R8.** Grafana 3000 and 8080 are already on the tailnet
   (`services.tf:222`, `:231`); 8404 is not the only one. Decide explicitly
   whether they stay.
4. **Restate R4 and the SSH eval row** to what is true: firebat has LAN +
   tailnet 22, workers have LAN only and no tailscale
   (`configure_tailscale.yml:3`). Either scope the tailnet rollout in or drop
   the tailnet half of the assertion for workers.
5. **Repair the three anchors** (`services.tf:52-53` → `:188-192`;
   `services.tf:73-74` → `:212-213` / `:235-258`; `haproxy.hcl:129` → `:122`),
   in the plan and in the eval rows that repeat them.
6. **Add `applications/providers.tf:45` (MinIO) to R6**, or state explicitly
   that MinIO 9000 stays open to cluster nodes and that the devcontainer is not
   one — and say which.
7. **State the narrowing target.** "Narrow `from_ip`" never says to what. If it
   is the five node IPs, say so; Prometheus scrapes `192.168.2.30:4646` and
   `:8500` from `192.168.2.47` (`prometheus.hcl:85`, `:92`), and haproxy dials
   four non-local backends, so the target set is load-bearing.
8. **Fix eval rows D5, D6, D63 and widen D2** per the section above.
9. **Add the second circular dependency to R7's runbook**: sealed Vault plus a
   haproxy restart leaves no edge to unseal through
   (`haproxy.hcl:39`, `:62-72`; `scripts/unseal_vault.sh`).
10. **Correct the `.env.example` claim** (it is on `localstack.local`, not an
    IP) so the eval row's rationale matches the file.

## Contract hygiene (checked, secondary)

Non-goals are explicit and specific. Forks are surfaced with recommendations
and recorded as resolved. The gate command `just pre_commit` matches the root
`justfile`, and `just worktree_setup <path>` exists as the eval's final row
assumes. The code surface is real but incomplete (fix 1, 6). Anchors fail
(fix 5). Tests are homed in the eval marker rather than test files, which is
right for an infrastructure ticket.

## Bottom line

The plan is well argued and its central mechanism is confirmed on a live host.
It is wrong about how much is exposed and about how many places the rules come
from, and that error propagates into a marker whose Definition of Done no row
enforces. Two of its rows cannot be executed at all. This stays at `PLANNING`
until fixes 1 through 10 land.
