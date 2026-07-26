---
epic = "landing"
depends_on = ["L1-landing-oauth2-proxy", "A1-audit-plan-premise-sweep"]
priority = 5
summary = "Deploy gethomepage as a Nomad job with static config on a dynamic host volume, routed through HAProxy behind L1's forward-auth, so an authenticated operator gets one themed landing page with tiles and live-status widgets instead of memorizing hostnames."
tags = ["homepage", "nomad", "haproxy", "oauth2-proxy"]
---

# L2: OAuth-gated Homepage (gethomepage) landing page at dash.localstack

## 1. Title

Deploy Homepage (gethomepage) as a Nomad job with static file config on a
dynamic host volume, and route it behind HAProxy at `dash.localstack`
gated by the L1 oauth2-proxy forward-auth, so an authenticated operator
sees a themed landing page with tiles and live-status widgets for the
cluster services.

## 2. Size / Effort

**M (medium).** The build is one new Nomad job HCL, one new
`nomad_dynamic_host_volume`, one `nomad_job` resource in `services.tf`, and
one new HAProxy frontend ACL + backend. The effort driver is not the job
itself (it mirrors existing patterns) but the config surface: a static
`services.yaml` / `settings.yaml` / `widgets.yaml` set enumerating nine
services plus per-service status widgets, and the HAProxy wiring that must
consume L1's forward-auth (which does not exist in the repo yet — see
Dependencies and Open Questions Q1).

## 3. Triggered by

Auth epic, stage L2. The operator wants a single pretty, themeable
landing page for the cluster, reachable only after OAuth login. Flat
access: everyone who passes login sees the same tiles, no per-user RBAC.
This is the human-facing capstone that L1 (oauth2-proxy forward-auth,
which depends on F2+F3) makes gate-able.

## 4. Context

Today the cluster has a hostname-routing browser front door but no
landing page: an operator must know each `*.localstack` hostname by hand.

- **Front door.** HAProxy runs as a Nomad job pinned to `firebat`
  (`deployments/infrastructure/services/haproxy.hcl:6-9`), binds plain
  HTTP on `*:80` (`haproxy.hcl:48-49`, `frontend http_in`), and routes
  host-header ACLs (`haproxy.hcl:51-62`) to static `use_backend` rules
  (`haproxy.hcl:64-75`) and static `backend` blocks
  (`haproxy.hcl:84-121`). There is no `dash` ACL or backend today. The
  config is a single inline `template` rendered to `local/haproxy.cfg`
  (`haproxy.hcl:31-124`), and the job is templated from Terraform with the
  `openfang_password` var (`services.tf:308-316`).
- **Existing auth mechanism in HAProxy is HTTP basic auth**, not
  forward-auth: `userlist openfang_users` (`haproxy.hcl:45-46`) plus
  `http-request auth unless { http_auth(openfang_users) }` on the phoenix,
  mlflow, and bifrost backends (`haproxy.hcl:100,116,120`). L1 replaces
  this class of gate with oauth2-proxy forward-auth; L2 consumes whatever
  L1 exposes (see Q1). L2 must NOT invent its own basic-auth gate.
- **Host-volume pattern.** Dynamic host volumes are declared in
  `deployments/infrastructure/services.tf:2-160` (e.g. `grafana_data` at
  `services.tf:102-120`: `plugin_id = "mkdir"`, `node_pool = "default"`,
  a `constraint` pinning the node by `unique.hostname`, and a
  `single-node-writer` / `file-system` capability). The job consumes it
  with a `volume` stanza in the group and a `volume_mount` in the task:
  see `grafana.hcl:18-23` (`type = "host"`, `source = "grafana_data"`) and
  `grafana.hcl:62-65`. The `nomad_job` resource then declares
  `depends_on = [nomad_dynamic_host_volume.grafana_data]`
  (`services.tf:333-355`).
- **Config-as-files pattern.** Grafana is the closest model for a job that
  ships static config files: it mounts rendered `local/...` files into the
  container via `config.volumes` (`grafana.hcl:51-59`) and writes them with
  `template` stanzas (`grafana.hcl:86-125`). Homepage's YAML config should
  follow this exact pattern (inline `template` -> `local/...` -> mounted
  read-only), starting static.
- **Service placement / DNS.** All `*.localstack` names resolve to firebat
  (`192.168.2.30`), the HAProxy host, per
  `docs/haproxy_reverse_proxy.md:1-3,20-27`. The nine services to tile are
  already reachable through HAProxy backends: minio/s3
  (`haproxy.hcl:84-88`), grafana (`haproxy.hcl:109-110`), prometheus
  (`haproxy.hcl:106-107`), loki (`haproxy.hcl:112-113`), phoenix
  (`haproxy.hcl:99-101`), memex (`haproxy.hcl:103-104`), mlflow
  (`haproxy.hcl:115-117`); Postgres is reached directly on firebat:5432,
  not via HAProxy (`docs/haproxy_reverse_proxy.md:38-45`); NATS monitoring
  is on radxa `192.168.2.50:8222` (`services.tf:262-269`, nats firewall).

What is missing: no landing page, no `dash` route, no Homepage job, no
host volume for its config.

## 5. Non-goals / out of scope

- **No per-user RBAC / no per-tile access control.** Flat access is
  explicit: all authenticated users see the same tiles.
- **No consul-template auto-population in this ticket.** Start with static
  `services.yaml`. The consul-template bridge (Homer being the natural
  target for that, per the rejected-alternatives note) is optional/later
  and out of scope here.
- **Do not implement or redesign L1.** L2 consumes L1's forward-auth
  contract; it does not build oauth2-proxy, the Vault OIDC client, or the
  forward-auth ACL machinery. If L1 is not yet merged, see Q1 for how to
  proceed without silently inventing the gate.
- **Do not implement the rejected alternatives** (Homer, Consul built-in
  UI). They are context only.
- **No TLS work.** The front door is plain HTTP:80 today
  (`haproxy.hcl:48-49`); L2 does not change that.
- **No removal of the existing openfang basic-auth** on other backends.
  Touch only what `dash` needs.
- **No Zitadel.** It was dropped from the auth design; any reference is a
  factual error.

## 6. Requirements & restrictions

The change MUST:

1. **Add a Homepage Nomad job** at
   `deployments/infrastructure/services/homepage.hcl`, driver `podman`,
   arm64-compatible image pinned to a specific tag (not `latest`),
   modeled structurally on an existing service job (grafana/nats). Set
   `HOMEPAGE_ALLOWED_HOSTS` to `dash.localstack` — recent gethomepage
   releases refuse requests otherwise, which would surface as a blank/403
   page behind the proxy. (Verify the exact env-var name against the
   pinned image's docs during implementation.)
2. **Provision a dynamic host volume** for Homepage config in
   `services.tf`, following the `grafana_data` shape
   (`services.tf:102-120`): `mkdir` plugin, `default` node_pool, a
   `constraint` pinning the chosen node (see Q3), small capacity,
   `single-node-writer` / `file-system`. Mount it in the job via `volume`
   + `volume_mount` (model: `grafana.hcl:18-23,62-65`). Config files
   themselves start static via `template` stanzas (model:
   `grafana.hcl:86-125`); the host volume backs Homepage's mutable state
   (e.g. its data dir), not the read-only config.
3. **Register the job** with a `nomad_job "homepage"` resource in
   `services.tf` using `templatefile(...)` (model: `services.tf:333-355`),
   with `depends_on` on the new host volume.
4. **Add the `dash` route to HAProxy** in `haproxy.hcl`: a
   `hdr(host) -i dash.localstack` ACL (model: `haproxy.hcl:51-62`), a
   matching `use_backend` (model: `haproxy.hcl:64-75`), and a `backend`
   block pointing at the Homepage host:port. The backend MUST be gated by
   L1's forward-auth, not by `http_auth(openfang_users)` (see Q1).
5. **Populate tiles for all nine services** — MinIO, Postgres, Grafana,
   Prometheus, Loki, Phoenix, Memex, MLflow, NATS — pointing at their
   real reachable URLs (the `*.localstack` HAProxy hostnames where routed;
   direct host:port for Postgres and NATS monitoring per Context).
6. **Add live-status widgets** for the services that support them
   (Homepage `siteMonitor`/service widgets), so tiles show up/down.
7. **Success criterion:** browsing `http://dash.localstack` after passing
   L1 OAuth login renders the themed Homepage with working tiles;
   unauthenticated access is blocked by L1's forward-auth. Confirm the
   config renders (nomad job runs healthy) and the HAProxy config is
   syntactically valid.

Restrictions the repo enforces (each cited):

- **Simplicity / surgical changes / no speculative build**
  (`CLAUDE.md` sections 1-3): start static, add only the nine tiles and
  their widgets, touch only what `dash` needs in `haproxy.hcl`. No
  consul-template, no RBAC, no config framework.
- **Secrets in Vault, never hardcoded** (`CLAUDE.md` Key Conventions):
  any widget that needs a credential to read status (e.g. an API key) must
  pull it from Vault KV2 via a `template`/`vault {}` stanza (model:
  `grafana.hcl:29,77-84`), not inline. Prefer unauthenticated
  health/`siteMonitor` widgets where possible to avoid new secrets.
- **Nomad HCL formatting** (`.pre-commit-config.yaml` `nomad-fmt` hook,
  `justfile` `format:` = `nomad fmt -recursive`): new `.hcl` must pass
  `nomad fmt`.
- **Pin the container image** (project convention: every other job pins a
  tag, e.g. `grafana.hcl:48`, `haproxy.hcl:25`). No `:latest`.
- **No Zitadel** anywhere in config, comments, or tiles.

## 7. Code surface

- **CREATE** `deployments/infrastructure/services/homepage.hcl` — new
  Nomad job: podman task, pinned arm64 gethomepage image, host `network`
  with a static port, `volume` + `volume_mount` for the config/data host
  volume, `template` stanzas rendering `settings.yaml`, `services.yaml`,
  `widgets.yaml` into `local/...` and mounting them read-only via
  `config.volumes`, `HOMEPAGE_ALLOWED_HOSTS` env, and a `service` +
  health `check`. Models: `grafana.hcl:1-75,86-125`, `nats.hcl:1-60`.
- **EDIT** `deployments/infrastructure/services.tf` — add
  `resource "nomad_dynamic_host_volume" "homepage_data"` (model
  `services.tf:102-120`) and `resource "nomad_job" "homepage"` with
  `templatefile(...)` + `depends_on` (model `services.tf:333-355`). If the
  chosen node needs a firewall rule for the Homepage port, add it to
  `local.firewall_rules` (`services.tf:163-272`) — see Q3.
- **EDIT** `deployments/infrastructure/services/haproxy.hcl` — inside the
  inline `template` (`haproxy.hcl:31-124`): add `acl is_dash`
  (near `haproxy.hcl:51-62`), `use_backend dash if is_dash`
  (near `haproxy.hcl:64-75`), and a `backend dash` block
  (near `haproxy.hcl:84-121`) gated by L1 forward-auth pointing at the
  Homepage host:port.
- Read-only anchors to cite/consume, not edit: `grafana.hcl:18-23,51-65`
  (host-volume + file-mount pattern), `docs/haproxy_reverse_proxy.md:1-45`
  (DNS + service URLs for tiles), the nine backends in `haproxy.hcl:84-117`
  and `services.tf:262-269` (tile targets).

## 8. Tests & validation gates

This repo has **no unit-test suite for infrastructure** (the
`.claude/rules/python-testing.md` all-code-needs-tests rule targets Python
code; there is none here). Validation is the terraform-aware pre-commit
gate, plus live evals run against the reachable cluster.

- **Repo gate:** `just pre_commit` (= `pre-commit run --all-files`, root
  `justfile:17-18`). The gate now validates Terraform, not just Nomad HCL.
  Configured hooks (`.pre-commit-config.yaml`): check-json, check-ast,
  check-merge-conflict, check-yaml `--unsafe`, debug-statements,
  detect-private-key, end-of-file-fixer; the local `nomad-fmt` hook
  (`nomad fmt -recursive` on `*.hcl`, `.pre-commit-config.yaml:16-21`);
  and the two local Terraform hooks `terraform-fmt`
  (`terraform fmt -check -recursive`, `.pre-commit-config.yaml:22-27`) and
  `terraform-validate` (`entry: scripts/tf_validate.sh`,
  `.pre-commit-config.yaml:28-33`). `scripts/tf_validate.sh` runs
  `terraform validate` offline (`init -backend=false`, no Consul backend,
  no credentials) over three roots including `deployments/infrastructure`,
  so the new `nomad_dynamic_host_volume "homepage_data"` and `nomad_job
  "homepage"` in `services.tf` are schema-checked by the gate. Required to
  pass: `homepage.hcl` and the `haproxy.hcl` edit through `nomad-fmt`; the
  `services.tf` edit through `terraform-fmt` and `terraform-validate`; all
  new/edited files through end-of-file-fixer without tripping
  detect-private-key. `.pre-commit-config.yaml:1` excludes
  `^\.(claude|loop)/`, so this ticket file is not linted, but the new
  job/tf files ARE.
- **HAProxy config validity (no repo gate covers this):** the `dash`
  ACL/backend edit lives inside a heredoc string in `haproxy.hcl:31-124`,
  so neither `nomad-fmt` (formats HCL, not the embedded string) nor
  `terraform-validate` (does not parse rendered HAProxy config) catches an
  HAProxy syntax error — a malformed directive passes the repo gate and
  then breaks routing for every service at deploy. Validate the rendered
  config before declaring done: render the template and run
  `haproxy -c -f <rendered.cfg>` (config check), or apply and confirm the
  `haproxy` allocation restarts healthy with no existing route regressed.

- **Evals (live) — acceptance:** the cluster is reachable from this
  environment (`VAULT_ADDR`, `VAULT_TOKEN`, `NOMAD_ADDR`, `NOMAD_TOKEN`,
  `CONSUL_HTTP_ADDR` are set), so this acceptance is runnable, not
  aspirational. Every authenticated/unauthenticated check depends on L1's
  forward-auth being merged and wired (Q1; L1 depends on F2, F3). Until L1
  is live the block/render checks cannot pass and the `dash` route must
  not ship (Risk 1, Q1) — do not weaken the eval to make it green. Each
  check is marked **[pre-apply]** (runnable before this ticket's
  `terraform apply`, to baseline) or **[close-out]** (only after apply).

  1. **[pre-apply] No `dash` route yet (baseline).**
     `curl -sI http://dash.localstack/` — expect NOT a Homepage 200
     (HAProxy has no `dash` backend today: a 503/no-backend or connection
     refusal), confirming the route is introduced by this ticket.
  2. **[pre-apply] Reference route baseline for regression.**
     `curl -sI http://grafana.localstack/` — record the returned status
     line; check 7 compares against it.
  3. **[close-out] Homepage alloc healthy.**
     `nomad job status homepage` — expect the `homepage` group `Running`
     with `Healthy` equal to `Desired`/`Placed` and 0 restarts;
     `nomad alloc status <alloc-id>` shows the task's health `check`
     passing.
  4. **[close-out] Unauthenticated request is blocked by L1.**
     `curl -sI http://dash.localstack/` — expect a `302` redirect to the
     Vault/oauth2-proxy login (`Location:` header pointing at the L1
     auth endpoint), NOT `HTTP/1.1 200`. A 200 here means the Homepage is
     served without auth and FAILS acceptance (Risk 1).
  5. **[close-out] Authenticated request renders the Homepage.** With a
     valid L1 session cookie (from a completed OAuth login), e.g.
     `curl -s --cookie "<oauth2-proxy session cookie>"
     http://dash.localstack/` — expect `200` and the Homepage HTML body.
  6. **[close-out] The nine service tiles are present.** Pipe the
     authenticated body through grep:
     `curl -s --cookie "<cookie>" http://dash.localstack/ | grep -Eio
     'minio|postgres|grafana|prometheus|loki|phoenix|memex|mlflow|nats'`
     — expect all nine names to match. Then confirm each tile's
     `siteMonitor`/service widget resolves (status shown, not error) in
     the rendered page or Homepage's service-status API, with each tile
     pointing at a reachable URL per Section 6 req 5 (HAProxy
     `*.localstack` hostnames, Postgres on firebat:5432, NATS monitoring
     on radxa:8222).
  7. **[close-out] No existing route regressed.**
     `curl -sI http://grafana.localstack/` — expect the same status line
     recorded in check 2, confirming the heredoc `haproxy.hcl` edit did
     not break shared routing.

- **Adversarial review** (`.claude/rules/adversarial-reviews.md`): before
  reporting done, hand the diff to a review sub-agent to confirm the
  `dash` backend is gated by L1 forward-auth (not left open or on stale
  basic-auth), the image is pinned/arm64, no secret is hardcoded, and no
  existing route regressed.
- **Eval marker (loop-harness acceptance):** the live evals above are
  encoded as the five-column scorer table at
  `.loop/evals/L2-landing-homepage.md` (validated by `loopctl eval`).

## 9. Risk assessment

- **Blast radius:** the `haproxy.hcl` edit is the only shared-surface
  change; a malformed ACL/backend inside the heredoc can break routing for
  *all* services, not just `dash`. The Homepage job and its host volume are
  additive and isolated.
- **Reversibility:** high. Revert the three files and destroy the
  `homepage` job + volume. The HAProxy revert restores the prior config
  exactly (one job, re-rendered).
- **Likeliest failure modes:**
  1. **Ungated `dash` backend** — Homepage ships without L1's forward-auth
     wired, exposing the landing page (and its outbound tile links)
     unauthenticated. This is the headline risk; the review gate checks
     it explicitly. If L1 is not merged, do not ship an open route — see
     Q1.
  2. **`HOMEPAGE_ALLOWED_HOSTS` unset/wrong** — page returns blank/403
     behind the proxy host header. Set it to `dash.localstack`.
  3. **HAProxy heredoc syntax error** — breaks all routing; mitigated by
     the config-validity check.
  4. **Node/port collision** — Homepage default port (3000) collides with
     Grafana if colocated on the same node; pick the node/port to avoid a
     clash (Q3) and add any needed firewall rule.
  5. **Widget needing a secret** — a status widget that needs an API key
     tempts an inline credential; route through Vault or use an
     unauthenticated health check instead.

## 10. Subtickets

Ordered, dependency-aware.

1. **Resolve the L1 forward-auth contract (Q1).** Confirm how L1 exposes
   forward-auth to HAProxy (backend name, ACL snippet, or config include).
   Blocks the `dash` backend. Depends on: nothing. Gate: operator answer
   or merged L1.
2. **Provision the host volume.** Add `nomad_dynamic_host_volume
   "homepage_data"` in `services.tf` (model `services.tf:102-120`), node
   per Q3. Depends on: Q3.
3. **Write `homepage.hcl`.** Job with pinned arm64 image, static config
   `template`s, host-volume mount, `HOMEPAGE_ALLOWED_HOSTS`, health check.
   Depends on: 2.
4. **Populate tiles + status widgets.** The nine services with real URLs
   and `siteMonitor`/service widgets; secrets (if any) via Vault. Depends
   on: 3.
5. **Register the job.** `nomad_job "homepage"` + `depends_on` in
   `services.tf` (model `services.tf:333-355`); firewall rule if needed.
   Depends on: 3.
6. **Wire the `dash` HAProxy route.** ACL + `use_backend` + gated
   `backend` in `haproxy.hcl`. Depends on: 1, 5.
7. **Validate + adversarial review.** `just pre_commit`, HAProxy config
   check, deploy acceptance, review sub-agent. Depends on: 1-6.

## 11. Open questions

Forks the request/repo do not settle. Operator should settle Q1 and Q3
before the loop runs; Q2 and Q4 are lower-stakes with a recommended
default.

- **Q1 — What is L1's forward-auth integration contract, and is L1
  merged?** L1 (oauth2-proxy forward-auth) does not exist in the repo yet
  (only `S1` is in `.loop/plans/`; no oauth2-proxy job or ACL anywhere).
  The `dash` backend cannot be correctly gated without knowing how L1
  exposes forward-auth in `haproxy.hcl` (a shared `http-request`
  auth-request snippet, a dedicated oauth2-proxy backend to `use_backend`
  on failure, or a config include). *Recommendation:* treat merged-L1 as a
  hard prerequisite for subticket 6. If the operator wants L2 to land
  first, ship everything except the route, and leave the `dash` backend
  behind a placeholder that the loop must NOT resolve as "open" — surface
  it rather than shipping an unauthenticated page. Do not invent a
  basic-auth gate as a stand-in.
- **Q2 — Which gethomepage image tag?** The upstream is
  `ghcr.io/gethomepage/homepage` (multi-arch, arm64-capable).
  *Recommendation:* pin a specific released tag (verify arm64 in the
  manifest during implementation), never `latest`, matching the repo's
  pin-everything convention (`grafana.hcl:48`).
- **Q3 — Which node hosts Homepage, and what port?** Colocating on
  `firebat` with HAProxy keeps the `dash` backend a localhost hop, but
  firebat also runs Postgres/Vault/Consul/Nomad-server. `ubuntu`
  (192.168.2.47) already hosts Grafana/Prometheus/Loki and has spare
  monitoring role. *Recommendation:* firebat, on a non-conflicting port
  (avoid 80/3000/4646/5432/8200/8404/8500), to keep the proxy hop local
  and the firewall rule minimal; confirm with operator. Whichever node,
  add the matching `local.firewall_rules` entry (`services.tf:163-272`) if
  the port must be reachable from HAProxy across hosts.
- **Q4 — Where does the host volume mount, and does Homepage need one at
  all?** Homepage is largely stateless when config is file-mounted; the
  host volume mainly backs its writable data dir. *Recommendation:* keep a
  small host volume for parity with the repo pattern and for any future
  config-on-disk, but if implementation shows Homepage needs no writable
  state, drop the volume and mount config read-only only — surface the
  simplification rather than carrying an unused volume.

## Resolved forks (operator, 2026-07-23)

- **Q1 → Hard-block on merged L1.** L2's gated route waits until L1
  exists. Integration is **reverse-proxy**, not forward-auth (per L1-Q2):
  HAProxy routes `dash.localstack` → oauth2-proxy (L1) →
  `--upstream` Homepage (L2). **Reconcile all "forward-auth" wording in
  this ticket to reverse-proxy.** Never ship an unauthenticated page or a
  basic-auth stand-in.
- **Q2 → Pin a specific released `ghcr.io/gethomepage/homepage` tag**
  (verify arm64 in the manifest during implementation); never `latest`.
- **Q3 → ubuntu (192.168.2.47).** Place Homepage on ubuntu, which has
  spare capacity, to relieve firebat (flagged as compute-constrained).
  Consequence: the `dash` backend is a cross-host hop — add the matching
  `local.firewall_rules` entry (`services.tf:163-272`) so HAProxy on
  firebat can reach Homepage on ubuntu. Pick a non-conflicting port.
- **Q4 → Small host volume for parity (default).** Keep a small writable
  host volume; if implementation shows Homepage needs no writable state,
  drop it and mount config read-only — surface the simplification rather
  than carrying an unused volume.

**Dependencies:** L2 depends on **L1** (which depends on F2 + F3) and on
**F4** (network-wide `.localstack` DNS) — L2 must not be marked done until
F4 lands, so `dash.localstack` resolves from non-Mac LAN devices, not just
via the operator's `/etc/hosts`.
