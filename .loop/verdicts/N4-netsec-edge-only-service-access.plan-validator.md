---
verdict: fail
---

# N4-netsec-edge-only-service-access — plan review (pass id: plan-validator)

Plan: `/home/vscode/workspace/.loop/plans/N4-netsec-edge-only-service-access.md`
Fingerprint supplied by the briefing:
`074c2e431c623c0efc3fbe22adda39959b2e334ffef8df6e501be2c5aec12d1f`.
This is a `fail`, so the contract omits the `plan:` line and no authorizing
hash is written.

**What I re-ran vs only read.** Re-ran live, read-only, 2026-08-01: every URL
in the exposure table from the devcontainer; the edge equivalents; the unknown
Host 503; Consul catalog/nodes/KV unauthenticated; `sudo ufw status numbered`
on firebat, radxa and the rpi4b; `sudo iptables -S INPUT` and `-S ts-input` on
firebat and radxa; `ss -ltn` and `ss -tn state established` on firebat and all
four workers; `sudo ss -tnp` on radxa to name the process holding a Vault
connection; `curl http://127.0.0.1:4646/v1/agent/health` and `/v1/jobs` on
firebat; `hostname` on all four workers; the `.loop` ledger. Only read: the
plan, the eval marker, the prior verdict, and the repo files cited below. No
mutating command was run, no firewall rule touched, nothing restarted.

## Prior verdict (2026-07-31): its ten fixes did land

I checked each. Fix 1 (third provisioner) landed and the anchors resolve.
Fix 2 (exposure table widened, mlflow/phoenix named as an auth bypass) landed
and I re-measured every row: `192.168.2.50:5050` 200 vs edge 401,
`192.168.2.29:6006` 200 vs edge 401, memex 401, bifrost 200, grafana 302,
hermes 404, 8404 200 unauthenticated, `firebat:4646` 307. Fix 3 (grafana 3000
and 8080 already on the tailnet) landed; confirmed on the rpi4b's live table
(`[12] 3000/tcp ALLOW 100.64.0.0/10`, `[14] 8080/tcp ALLOW 100.64.0.0/10`).
Fix 4 (R4 restated to firebat-only tailnet) landed; radxa and the rpi4b have no
`tailscale` binary. Fix 5 (three anchors) landed: `infrastructure/services.tf`
`:191-192`, `:222`, `:231`, and `haproxy.hcl:122` all resolve exactly. Fix 6
(MinIO provider) landed. Fix 7 (per-service target table) landed. Fix 8 (eval
rows D5, D6, D63) landed. Fix 9 (second circular dependency) landed. Fix 10
(`.env.example` is mDNS) landed.

That work was real. The plan is now the most carefully evidenced one on this
board. It also still rests on four assumptions that are false against the live
cluster, and two of them are the kind that take the cluster down.

## Premise verdict: BROKEN

Not because the ticket is wrong to exist — it is right, and the mlflow/phoenix
bypass re-measured today justifies it on its own. It is broken because the
plan's own contract (R5's target table, R8's tailnet clause, subticket 1's
ordering, and R7's recovery escape) contains four statements that the cluster
contradicts, and the eval marker scores each of them green anyway.

## Per assumption

**P1 — the measured exposure table is accurate. HOLDS.**
Re-measured all thirteen rows today from the devcontainer; every one matches,
including the two 200/401 pairs. `curl -H 'Host: bogus.example.com'` on 443
returns 503. `firebat:4646` 307.

**P2 — rules come from exactly three provisioners. HOLDS.**
`grep -rn ufw` returns the Ansible role
(`bootstrap/roles/firewall/tasks/main.yml:15-22`, no delete step; default deny
at `:7-13`), `deployments/infrastructure/services.tf:293`, and
`deployments/applications/services.tf:100`. The applications map's anchors are
exact: map at `:23-82`, phoenix `:29-30`, memex `:38`, hermes `:46-47`, loki
`:50-63`, mlflow `:71`, bifrost `:79`, `null_resource.firewall` at `:85`,
remote-exec `:93`, `sudo ufw` at `:100`.

**P3 — no provisioner removes a rule, so narrowing shadows. HOLDS, and is live
today.** radxa's table still shows `[10] 8642/tcp ALLOW IN 192.168.0.0/16`
beside `[12] 192.168.2.30` and `[14] 192.168.2.46`, exactly as the plan says.

**P4 — the per-service target table is the contract, and it is complete.
BREAKS. This is the one that sinks the ticket.**
The table gives vault 8200 on `.30` two admitted sources: `.30` (node-local)
and `.47` (acme). That is wrong. Every Nomad **client** dials Vault on
`192.168.2.30:8200`:
`bootstrap/roles/nomad_client/templates/nomad.hcl.j2:33-36` sets
`vault { address = "http://{{ nomad_client_server_address }}:8200" }`, and
`bootstrap/playbooks/configure_hashistack_clients.yml:17` sets
`nomad_client_server_address: "192.168.2.30"`. I confirmed the rendered file on
all four workers carries `address = "http://192.168.2.30:8200"`, and I caught
the traffic:

    ESTAB 192.168.2.50:41900  192.168.2.30:8200  users:(("nomad",pid=2369993,fd=9))

That is the Nomad client agent on radxa, not an application. I also observed
`192.168.2.29:36428 -> 192.168.2.30:8200` established on orange_pi_4a. The
connections are transient because they are template renewals.

Fourteen jobspecs carry a `vault {}` stanza and render `{{ with secret }}`
(`grep -rln "vault {" deployments/*/services/*.hcl`), including memex on `.46`
(`memex.hcl:44`, `:114`, `:124`, `:132`, `:139`), phoenix on `.29`, and
mlflow, bifrost, hermes and loki on `.50`. Narrow 8200 to `{.30, .47}` as the
table instructs and the Nomad clients on `.29`, `.46` and `.50` lose Vault.
Nothing errors at apply time. Secrets stop renewing on three of five nodes and
the cluster degrades over hours to days.

This is precisely the failure the plan's own risk section calls "High: killing
a cross-node consumer silently", arriving through the one door the table
forgot. And the eval's positive-control row probes 8200 **only from
`192.168.2.47`**, so the marker goes green over it.

**P5 — R8's tailnet clause is achievable by editing ufw rules. BREAKS.**
On firebat, tailscale's netfilter chain runs before ufw and accepts everything
on the tunnel:

    -P INPUT DROP
    -A INPUT -j ts-input          <- first
    -A INPUT -j ufw-before-input
    ...
    -A ts-input -i tailscale0 -j ACCEPT

Live proof rather than inference: firebat's ufw table grants 8200 to
`192.168.0.0/16` only (`[7] 8200/tcp ALLOW IN 192.168.0.0/16`, no tailnet
entry), yet `ss` on firebat shows
`100.117.172.3:8200 <- 100.64.146.75:65166` established. A tailnet peer is
talking to Vault through a port ufw never allowed it. **ufw does not gate
tailscale0 on firebat at all.** Every port on firebat — 4646, 8200, 8500,
5432, 5000/5001, 20000:32000, 8404, 9100 — is open to the tailnet regardless
of what the rule set says.

Three consequences. R8's "the tailnet loses everything but 80/443 and SSH to
firebat" cannot be delivered by this ticket's mechanism. The eval row "The
tailnet keeps 80, 443 and SSH-to-firebat, and nothing else" cannot pass for
its 8404 probe. And the plan's Context paragraph "8404 is not the only thing
on the tailnet ... R8 covers all three, not just 8404" understates the
exposure by an order of magnitude: it is not three ports, it is every port on
the manager. The rpi4b half is fine — no tailscale there
(`which tailscale` returns nothing), so its `100.64.0.0/10` rules for 3000 and
8080 are real and removable.

The plan also declares "No tailnet firewall redesign" a non-goal while R8
requires a tailnet outcome. Those two cannot both hold once you know ufw is
bypassed.

**P6 — "N3 is `ready` and needs no gate. Do it first." BREAKS.**
`.loop/ledger.json` gives N3 `"stage": "blocked"` with
`"code": "unresolved-design-fork"` and the reason *"No plan-validator verdict
has ever run ... treat never-reviewed as weaker than reviewed, not stronger."*
`ls .loop/verdicts/ | grep N3` returns nothing. The plan asserts N3's readiness
twice (consequence 1 under "The finding that reshapes this ticket", and
subticket 1). Both are false as of today.

This matters beyond bookkeeping. The plan says N3 "is the only thing that makes
the Terraform half take effect", so N4's steps 6 through 9 are no-ops on the
host without it. N4's premise therefore rests on an unreviewed prerequisite,
and N4's most dangerous mechanism (does a narrowed rule actually replace the
broad one?) is entirely N3's to deliver. **No, N4 cannot be sound while N3 is
unreviewed** — not because dependencies must always be reviewed first, but
because this specific dependency owns the mechanism on which N4's central claim
depends, and N4 cites N3's scope bound
(`.loop/evals/N3-netsec-converging-firewall-provisioner.md`, "the prune is
deliberately scoped so it cannot touch the Ansible half") as load-bearing in
Q1's resolution. If N3's scope bound is wrong, Q1's answer is wrong too.

**P7 — the recovery escape works: SSH to firebat plus
`NOMAD_ADDR=http://127.0.0.1:4646`. PARTIALLY BREAKS.**
The address half holds. `ss -ltn` on firebat shows `*:4646` (Nomad binds
`0.0.0.0`, `nomad_server/templates/nomad.hcl.j2:9`), and
`curl http://127.0.0.1:4646/v1/agent/health` from firebat returns 200. Consul
and Vault are reachable on loopback too (`client_addr = "0.0.0.0"` at
`consul_server/templates/consul.hcl.j2:7`; `*:8200` in `ss -ltn`), which the
runbook will need for the state backend and the unseal path.

The authorization half fails. Nomad ACLs are on
(`nomad_server/templates/nomad.hcl.j2:34-36`) and bootstrapped:
`curl http://127.0.0.1:4646/v1/jobs` from firebat with no token returns **403**.
So the escape the plan mandates —
`NOMAD_ADDR=http://127.0.0.1:4646 nomad job restart haproxy` — does not work as
written. I found no `NOMAD_TOKEN` on firebat (`grep -rl NOMAD_TOKEN` over
`/etc`, `/root/.bashrc`, `/home/firebat` returns nothing). The operator's token
lives in `.devcontainer/.env:2`, on the machine that just lost every other
route in.

The eval row "The runbook answers BOTH circular dependencies by name" scores
the runbook for *stating that exact command*. So a row certifies an escape that
403s. Only the last row ("kill the edge and recover") would expose it, and only
during the maintenance window.

**P8 — R6 lists every address this repo dials from outside the cluster.
BREAKS, three more.**
- `deployments/applications/services.tf:231` hardcodes
  `endpoint = "http://192.168.2.50:8080"` in `null_resource.bifrost_ready`,
  whose `local-exec` at `:235-249` curls `${self.triggers.endpoint}/health`
  from wherever Terraform runs, and `deployments/applications/providers.tf:67`
  wires that same trigger into the **bifrost provider**. R8 narrows bifrost 8080
  to `{.30, .46, .47}`. The devcontainer is not on that list, so the provider
  cannot configure and `bifrost_virtual_key` refresh (`services.tf:266`, `:280`)
  fails. This is the MinIO-provider defect the last verdict caught, repeated in
  a second file that neither R6 nor the code surface names.
- `.devcontainer/.env:27` `MEMEX_SERVER_URL=http://192.168.2.46…`. R8 narrows
  memex 8000 to `{.30, .50}`.
- `deployments/infrastructure/services.tf:364`
  `grafana_external_url = "http://192.168.2.47:3000"`, rendered into the
  Telegram alert body at `grafana.hcl:300`
  (`<a href="${grafana_external_url}/alerting/list">`), plus the hardcoded
  `GF_SERVER_ROOT_URL = "http://192.168.2.47:3000"` at `grafana.hcl:70`. After
  this ticket every alert link points at a closed port. (I checked the
  browser-visible case: `https://grafana.lab.orangecluster.nl/` returns 302 with
  `location: /login`, relative, so login is unaffected.)

The eval's grep guardrail cannot catch any of the three. Its pattern is
`192\.168\.2\.(29|30|46|47|50):(4646|8200|8500|9000|9001)` scoped to
`.devcontainer/`, `deployments/*/providers.tf`, `deployments/*/vars/`. Ports
8080, 8000 and 3000 are absent from the alternation, and `services.tf` is
outside the searched paths.

**P9 — the exposure inventory is complete. BREAKS, one class missing.**
Consul and Nomad answer on **every** node, not just `.30`. Measured today:
`192.168.2.29:8500` 200, `.46:8500` 200, `.47:8500` 200, `.50:8500` 200,
`.29:4646` 200, `.50:4646` 200. The Consul client config sets
`client_addr = "0.0.0.0"` (`consul_client/templates/consul.hcl.j2:5`) and the
Nomad client binds `0.0.0.0` (`nomad_client/templates/nomad.hcl.j2:4`); the
worker Ansible block opens both to `192.168.0.0/16`
(`configure_network.yml:37`, `:39`). The plan's code surface does say "narrow
`from_ip` for 4646, 8500 ... in both blocks", so the rule edit is in scope —
but the target table gives no source set for the worker copies, the exposure
table and R2's negative control never record them, and the eval's refusal row
scores exactly the ten haproxy backends, so eight live, ungated endpoints are
outside every measurement in the ticket.

**P10 — Consul's own controls are irrelevant because the port is being closed.
UNCERTAIN, and the plan should say it out loud.**
Confirmed the briefing's measurement: with no token,
`http://192.168.2.30:8500/v1/catalog/services` returns the full service list
and `/v1/catalog/nodes` the full node list, because
`bootstrap/roles/consul_server/templates/consul.hcl.j2:29-32` sets
`tokens { agent = …, default = … }`, so an unauthenticated request runs as the
agent. `default_policy = "deny"` at `:27` never applies to it. The same pattern
is in `consul_client/templates/consul.hcl.j2:16-19`, which is why all four
worker agents answered above. KV *is* gated: `/v1/kv/terraform/infrastructure`
returns 403, so the Terraform state is not exposed.

The plan's remedy is right — closing the port is the only control Consul has
here. What the plan never states is the consequence: after N4, Consul's full
catalog is still readable **with no credential by anyone who reaches the edge
on 443**, which is the whole LAN and (per P5) the whole tailnet. The same holds
for the Nomad UI, the Vault UI, the MinIO console and bifrost. The non-goal "No
authentication at the edge" covers the intent, but a reader of the Context will
conclude that closing 8500 protects Consul, and it does not. Add one sentence.

**P11 — R3's port enumeration covers the broad rules that must die. BREAKS,
minor.** Two live broad rules are not in the plan's or the marker's list:
radxa `[11] 9119/tcp ALLOW IN 192.168.0.0/16` (with a narrow `[13] … .30`
beside it — the same shadowing shape as 8642, and 9119 appears **nowhere** in
the repo), and the rpi4b's `[10]/[11] 50051/tcp` from `.30` and `.46`, also
undeclared. `grep -rn 9119` and `grep -rn 50051` across `*.tf` and `*.hcl`
return nothing. A marker that enumerates ports by name will score green over
both.

**P12 — anchors resolve. HOLDS.** I opened every `path:line` the plan cites.
All resolve, including the three the last verdict rejected. `haproxy.hcl`
`:122`, `:127-157`, `:143`, `:153`, `:39`, `:62-72`, `:89`; `prometheus.hcl`
`:85`, `:92`, `:96`, `:105`, `:119`; `acme.hcl:17-20` and `:158-163`;
`backup-minio.hcl:13-16`, `:37`; `memex.hcl:122`, `:143`, `:148`, `:155`,
`:158`; `hermes.hcl:203`, `:205-206`, `:449`, `:451-452`; `mlflow.hcl:50`;
`loki.hcl:119`; `.devcontainer/.env` `:3`, `:6`, `:9`, `:18`; `.env.example`
`:3`, `:7`, `:11`, `:23`; both `vars/backend-config.hcl:1-3`. Node placements
check out by `hostname`: `.47` = `ubuntu` (acme), `.50` = `radxa-dragon-q6a`
(backup-minio), `.46` = `jetson-orin-nano` (memex). The only nit is
`infrastructure/services.tf:174-182` for the minio block, which ends at `:181`;
`:182` is the next comment.

**P13 — `20000:32000` is a standing hole, not a live one. HOLDS.**
`ss -ltn` on firebat returns no listener in the range.

**P14 — closures are provable from a socket, as R1 claims. HOLDS for the
marker's closure rows.** I checked each row. Every row asserting unreachability
probes a socket or enumerates the live `ufw status numbered` table, which is
host state, not config. The rows that read config are labelled guardrails
(no-non-cluster-host, intra-cluster-ports, `.env.example`), which the marker's
own doctrine permits. One row is a config read scoring an *edit* rather than a
closure — "The third provisioner was actually edited" — and that is honest,
because the refusal rows carry the closure. So the answer to the brief's
question is: no closure row in this marker scores by reading a config file.

## Most dangerous assumption

**P4 — the vault 8200 line of the per-service target table.** R5 says "The
target table is the contract here." Implement the contract as written and the
Nomad clients on `.29`, `.46` and `.50` lose Vault, so every
`template { with secret }` on three of five nodes stops renewing. Nothing
fails loudly, the eval's cross-node positive control probes 8200 only from
`.47`, and every row in the marker is green while the cluster quietly loses its
secrets. It is the same shape of miss the last verdict caught in the exposure
table, one layer deeper.

## Eval marker: rows that cannot fail, cannot pass, or certify a broken thing

- **Cannot pass — "The tailnet keeps 80, 443 and SSH-to-firebat, and nothing
  else."** Its 8404 probe targets firebat, where `ts-input` ACCEPTs before ufw
  (P5). No ufw edit closes it. The 3000 and 8080 halves on the rpi4b are
  achievable.
- **Certifies a broken command — "The runbook answers BOTH circular
  dependencies by name."** It scores the runbook for stating
  `NOMAD_ADDR=http://127.0.0.1:4646 nomad job restart haproxy`, which returns
  403 (P7). The row must also require the token-acquisition step.
- **Misses the break it exists to catch — "Every cross-node consumer still
  reaches its target."** Twelve probes, none of them 8200 from `.29`, `.46` or
  `.50` (P4).
- **Blind guardrail — "No raw service address survives in the repo's own client
  config."** Pattern and path scope both miss the three addresses in P8.
- **Under-enumerated — "The broad rule is DELETED, not shadowed."** Names
  8642 but not 9119 on radxa or 50051 on the rpi4b (P11), and cannot see the
  tailnet at all.
- **Under-scoped — "Direct access is refused for EVERY edge-routed service."**
  Ten addresses, so the eight worker Consul/Nomad endpoints in P9 are outside
  it. The row is consistent with the marker's Definition of Done; the
  Definition of Done is what is too narrow for a ticket titled "only
  `*.lab.orangecluster.nl` reaches a service".
- **Probably unexecutable — "A fresh bootstrap still converges."** It needs "a
  scratch or re-imaged node". Five nodes are in production and none is spare.
  Say how it will be run, or make it a deferred assertion with an owner.
- **Brittle — "The cluster is unchanged underneath"** pins literal counts
  (5 nodes, 19 jobs, 24 allocations). It is a pre/post comparison; hardcoding
  the numbers makes it red for reasons unrelated to this change.
- **Self-certifying, acceptable — "applied to a worker before the manager"**
  and **"The negative control is captured before the change"** are scored from
  the implementer's own record. Both are the right shape for what they check;
  flagging them so nobody mistakes them for measurements.
- **Rows that are genuinely strong**: the two-auth-bypass priority row, the
  RST-to-timeout transition for `20000:32000` (the direction is the signal, and
  it is right — ufw's default deny DROPs, so the probe hangs), the 8404
  positive control, the Ansible-reconciles-in-its-own-lane row, and above all
  "kill the edge and recover", which is the only row that would catch P7.

## Required fixes before this plan leaves PLANNING

1. **Fix the vault 8200 target set.** It must admit every Nomad client:
   `.29`, `.46`, `.47`, `.50` and `.30`. Evidence:
   `nomad_client/templates/nomad.hcl.j2:33-36`,
   `configure_hashistack_clients.yml:17`, and the live
   `nomad` process holding `192.168.2.50 -> 192.168.2.30:8200`. Add 8200 probes
   from `.29`, `.46` and `.50` to the cross-node positive-control row.
2. **Resolve the tailnet contradiction.** ufw does not gate `tailscale0` on
   firebat (`iptables -S INPUT` puts `-A INPUT -j ts-input` first;
   `-A ts-input -i tailscale0 -j ACCEPT`). Either scope in the mechanism that
   can gate it (tailscale ACLs, `--netfilter-mode=off` plus explicit rules, or
   `tailscale serve`), or drop the firebat half of R8 and rewrite the eval row
   to score only the rpi4b's 3000 and 8080. State plainly in the Context that
   after this ticket every port on the manager remains open to the tailnet.
3. **Correct the N3 statement.** N3 is `stage: blocked`
   (`.loop/ledger.json`, blocker `unresolved-design-fork`), not `ready`, and no
   `.loop/verdicts/N3-*.plan-validator.md` exists. Subticket 1 becomes "get N3
   reviewed and unblocked, then land it". Say explicitly that Q1's scope bound
   depends on N3's mirror constraint holding, so N4 cannot be judged final until
   N3's premise has been attacked.
4. **Fix the recovery escape.** `curl http://127.0.0.1:4646/v1/jobs` on firebat
   returns 403; Nomad ACLs are on (`nomad_server/templates/nomad.hcl.j2:34-36`).
   R7 and its eval row must carry the full sequence: where `NOMAD_TOKEN` comes
   from during an outage (Vault on `127.0.0.1:8200` is reachable, which is the
   natural source), and the same question for `CONSUL_HTTP_TOKEN` if the runbook
   touches the state backend.
5. **Add the three missing addresses to R6 and the code surface**:
   `deployments/applications/services.tf:231` with its `local-exec` at
   `:235-249` and the provider wiring at `providers.tf:67`;
   `.devcontainer/.env:27`; and `infrastructure/services.tf:364` with
   `grafana.hcl:70`, `:300`. Widen the eval's grep guardrail to cover ports
   8080, 8000 and 3000 and to search `deployments/*/services.tf`.
6. **Inventory the worker Consul and Nomad agents.** `.29`, `.46`, `.47`,
   `.50` all answer 8500, and at least `.29` and `.50` answer 4646 (measured).
   Give them a source set in the target table, put them in R2's negative
   control, and either add them to the refusal row or record in the non-goals
   that they stay open and why.
7. **Add 9119 (radxa) and 50051 (rpi4b) to R3's enumeration**, or record them
   as knowingly untouched. Both are live broad or narrow rules with no
   declaration anywhere in the repo.
8. **State the Consul ACL fact in the Context**
   (`consul_server/templates/consul.hcl.j2:29-32`,
   `consul_client/templates/consul.hcl.j2:16-19`): the default token is the
   agent token, so unauthenticated reads return the full catalog, and closing
   the port is the only control Consul has. Then state the consequence: after
   N4 the catalog is still readable with no credential through the edge.
9. **Make "A fresh bootstrap still converges" executable** — name the node or
   defer it with an owner — and change "The cluster is unchanged underneath" to
   compare against row 1's capture instead of pinning 5/19/24.
10. **Small one:** the code surface hedges "Possibly
    `haproxy.hcl` for 8404 (`:120-125`)" on a fork that Q2 already decided.
    Q2 resolved to drop the human stats UI, so that edit is required, not
    possible. `haproxy.hcl:123-125` is `stats enable` / `stats uri /` /
    `stats refresh 10s`, and `:122` is the `/metrics` line that must survive.

## Contract hygiene (checked, secondary)

Non-goals are explicit and specific. Forks are surfaced with recommendations
and recorded as resolved with reasoning. The gate command `just pre_commit`
matches the root `justfile`, and `just worktree_setup <path>` exists at
`justfile:30-32` as the marker's last row assumes. Tests are homed in the eval
marker rather than test files, which is right for an infrastructure ticket.
Anchors resolve (P12). The code surface is real but incomplete per fix 5.

## Bottom line

The rewrite fixed all ten of the last verdict's findings and its Context now
re-measures true in every particular I could check. The plan fails on four
newer facts: the target table omits the Nomad clients' dial to Vault, ufw
cannot gate the tailnet on the one node that has tailscale, N3 is blocked
rather than ready, and the recovery escape 403s. Two of those produce an
outage, one invalidates a requirement, and one breaks the runbook this ticket
exists to ship. Stays at `PLANNING` until fixes 1 through 10 land.
