---
epic = "netsec"
depends_on = []
priority = 150
summary = "Prometheus and Loki answer their query APIs to the entire LAN with no credentials. Narrow both firewall rules to the callers that actually need them, leaving Grafana (which authenticates) reachable. The two rules live in different Terraform roots."
tags = ["prometheus", "loki", "firewall", "security", "terraform"]
---

# N1 — Restrict Prometheus and Loki to cluster-internal callers

## Title
Prometheus and Loki serve their query APIs unauthenticated to the entire LAN.
Narrow their firewall rules to the callers that actually need them. Grafana
stays reachable, since it has its own authentication.

## Size / Effort
**Small.** Two `firewall_rules` entries in two Terraform roots. No job change,
no application config. Effort is in getting the allow-list right, since an
over-narrow rule silently breaks log shipping rather than failing loudly.

## Triggered by
Operator request, 2026-07-26, after measuring which services answer without
credentials. These two are reachable from any device on the LAN and need to be
reachable only from inside the cluster.

## Context (today's state)
Measured live 2026-07-26 against the running services, not inferred:

- **Prometheus is unauthenticated.**
  `curl http://192.168.2.47:9090/api/v1/query?query=up` returns
  `{"status":"success",...}` with real metric data and no credentials.
- **Loki is unauthenticated.**
  `curl http://192.168.2.47:3100/loki/api/v1/labels` returns 200.
- Both are open to the whole LAN today:
  - `deployments/infrastructure/services.tf:215-223` — the `prometheus`
    entry allows `192.168.0.0/16` AND `100.64.0.0/10` to port 9090.
  - `deployments/applications/services.tf:50-57` — the `loki` entry allows
    `192.168.0.0/16` to port 3100. **Note the split: Loki's rule lives in the
    applications root, not beside the others**, so a change that edits only
    the infrastructure root fixes half the problem.
- **Who actually needs each:**
  - Prometheus 9090: Grafana's datasource, configured as
    `http://192.168.2.47:9090` (same node), plus browsers arriving through
    HAProxy on `192.168.2.30`. Nothing scrapes Prometheus; it scrapes
    outbound, which no inbound rule affects.
  - Loki 3100: Grafana's datasource `http://192.168.2.47:3100`, promtail
    pushing to `http://192.168.2.47:3100/loki/api/v1/push`, and browsers via
    HAProxy. **promtail is a `system` job** (`services/promtail.hcl:3`), so it
    runs on EVERY node and every node IP must retain access.
- Cluster node addresses: firebat `192.168.2.30`, orangepi4a `192.168.2.29`,
  jetson-orin-nano `192.168.2.46`, ubuntu `192.168.2.47`, radxa-dragon-q6a
  `192.168.2.50`.
- Browser access is unaffected by narrowing, because it arrives via HAProxy
  on `192.168.2.30`, which stays on the allow-list. What is lost is going
  directly to `192.168.2.47:9090`, which is the point.
- **Grafana is NOT unauthenticated**: it 302-redirects to a login. It keeps
  its current LAN and tailnet rules (`services.tf:224-232`) per operator
  instruction.

## Non-goals / out of scope
- **Grafana.** Stays reachable exactly as today. Operator decision.
- **Consul.** Its read endpoints also answer unauthenticated
  (`/v1/agent/members` returns 200), but it is the Terraform state backend
  and the dev container talks to it on every apply from a DHCP-assigned
  address. Locking it down risks locking the operator out of their own
  deployments. Separate ticket, separate decision.
- Adding authentication to Prometheus or Loki. This is a network-reachability
  change only.
- Changing what Prometheus scrapes or what promtail ships.
- Any change to `deployments/infrastructure/services/prometheus.hcl`,
  `promtail.hcl`, or the Loki jobspec.
- The tailnet question for Grafana. Out of scope here.

## Requirements & restrictions
1. After this change, a LAN device that is NOT a cluster node and NOT HAProxy
   cannot reach `192.168.2.47:9090` or `192.168.2.47:3100`.
2. Prometheus 9090 allows: `192.168.2.47` (Grafana, same node) and
   `192.168.2.30` (HAProxy). **Drop the `100.64.0.0/10` tailnet rule** —
   tailnet users reach it through HAProxy, which already admits that range on
   80/443 (`services.tf:196-199`).
3. Loki 3100 allows all five cluster node addresses, because promtail is a
   `system` job and ships from every node. Missing one silently stops log
   shipping from that node without an error at apply.
4. Follow the existing `firewall_rules` shape: a map entry with `host`,
   `ssh_user`, and a list of `ufw` rule strings
   (`services.tf:163-272`). Applied by `null_resource.firewall` over SSH
   (`services.tf:274-290`).
5. **ufw rules are additive and are NOT removed when the Terraform rule
   changes.** The `null_resource` runs `ufw allow ...` and has no destroy
   provisioner, so replacing a broad rule with a narrow one leaves the broad
   one in place on the host. The old rule must be deleted explicitly with
   `ufw delete allow ...`, or the change is cosmetic. This is the single
   likeliest way for this ticket to appear done while changing nothing.
6. Terraform providers pinned at `providers.tf:1-24`. Do not bump.
7. `.claude/rules/adversarial-reviews.md`: adversarial review before done.

## Code surface
- `deployments/infrastructure/services.tf:215-223` — narrow the `prometheus`
  entry to the two required sources, dropping the LAN-wide and tailnet rules.
- `deployments/applications/services.tf:50-57` — narrow the `loki` entry to
  the five node addresses.
- Removal of the superseded broad rules on `192.168.2.47`. Per requirement 5
  this needs an explicit `ufw delete`; whether that is a documented runbook
  step or added to the provisioner is Q1.
- `docs/monitoring.md` — if it documents reaching Prometheus or Loki directly
  by address, correct it to the edge hostname.

## Tests & validation gates
No unit-test harness for infra HCL, no CI. Repo gate plus live evals.

### Repo gate
- **Command:** `just pre_commit` -> all Passed.
- **Worktree prerequisite:** `just worktree_setup <path>` (`justfile:30-32`).
- **Command:** `terraform plan` in BOTH roots, since the two rules live in
  different ones. Expect the two `null_resource.firewall` instances to be
  replaced (their `triggers.rules` change) and nothing else.

### Evals — the authoritative set is
`.loop/evals/N1-netsec-restrict-prometheus-loki-to-cluster.md`.

## Risk assessment
- **The dangerous failure is silent.** Miss a node in Loki's allow-list and
  that node's promtail stops shipping logs. Nothing errors; logs simply stop
  arriving, and it looks like a quiet cluster. Verify per node, not in
  aggregate.
- **Grafana dashboards break** if `192.168.2.47` is omitted from Prometheus's
  list, since the datasource dials the node address rather than loopback.
- **The change can be a no-op** if the superseded ufw rules are not deleted
  (requirement 5). The eval must prove denial from a non-cluster host, not
  just that the new rule exists.
- **Applied over SSH by a provisioner**, not by an API, so it is not visible
  in `terraform plan` output beyond the trigger change and cannot be dry-run.
- **Locking yourself out is not a risk here**: neither service carries state
  and both are reachable via HAProxy afterwards.
- **Reversibility: high.** Restore the broad rule and re-apply, or
  `ufw allow` by hand on the node.

## Subtickets (ordered)
1. Narrow the `prometheus` entry in the infrastructure root.
2. Narrow the `loki` entry in the applications root.
3. Delete the superseded broad rules on `192.168.2.47` (Q1 decides how).
4. Apply both roots; run the evals, including a per-node promtail check.
5. Docs, if `monitoring.md` points at the addresses directly.
6. Adversarial review.

## Open questions
- **Q1 — How are the superseded ufw rules removed?** The provisioner only
  adds. *Recommendation:* a documented one-time `ufw delete allow ...` on
  `192.168.2.47`, recorded in the ticket's runbook, rather than teaching the
  provisioner to delete. Adding deletion logic to a `null_resource` that runs
  on every apply is a larger and riskier change than this ticket warrants.
- **Q2 — Does anything else on the LAN scrape or query these directly?** The
  known consumers are Grafana and promtail. *Recommendation:* before applying,
  check for other callers, since a forgotten integration fails silently.
- **Q3 — Grafana's own authentication is not owned by any ticket.** The
  operator notes Grafana supports native generic OAuth
  (https://grafana.com/docs/grafana/latest/setup-grafana/configure-access/configure-authentication/generic-oauth/),
  so it does NOT need oauth2-proxy and would talk to Vault's OIDC provider
  directly. No ticket currently covers this: the rollout epic covers MLflow
  (R1), Phoenix (R4), NATS (R2) and Postgres (R3), and L1 is the landing page.
  Such a ticket would depend on **F2** (the OIDC provider), not L1.
  *Recommendation:* author it separately. It is not a prerequisite for this
  ticket, since Grafana already requires a login, but the gap should not stay
  implicit.

---

## Follow-on, 2026-07-26: the edge routes were removed too

N1 as scoped narrowed the firewall, which closed the direct path and left the
proxied one. That was recorded honestly at the time as "one exposure of two":
HAProxy has to sit on the allow-list for any hostname it proxies, so
`prometheus.lab.orangecluster.nl` still served every metric to anyone who
asked, over a trusted certificate, with no password. The `prometheus` and
`loki` backends carried no `http-request auth`, unlike `phoenix`, `mlflow`
and `bifrost` in the same file.

The operator asked why those hostnames are routed at all, given Grafana is
the only thing anyone reads them through. Measured answer: nothing used them.
Grafana's datasources dial `192.168.2.47` directly from the same node,
promtail pushes directly to Loki, and the only reference to either hostname
anywhere in the repo was HAProxy's own ACL defining it. The sole consumer was
a human typing a URL.

So the two ACLs, two `use_backend` lines and two backend blocks were deleted
rather than given a password, which is the simpler and stricter answer. After
this, Prometheus and Loki are reachable only from cluster nodes.

Done directly on `main` at the operator's explicit instruction rather than
through a new ticket. Validated the same way T3 was: config rendered, real
HAProxy `-c` check green, negative control red, `terraform plan` confined to
`nomad_job.haproxy` in place.

**Cost accepted:** Prometheus's own web UI is gone from the browser. Its
Targets page shows real scrape error text where Grafana shows only `up == 0`,
so for debugging use a port-forward: `ssh -L 9090:192.168.2.47:9090
raspberry@192.168.2.47`.
