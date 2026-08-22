---
epic = "landing"
depends_on = ["L1-landing-oauth2-proxy", "A1-audit-plan-premise-sweep"]
priority = 5
summary = "Deploy gethomepage as a Nomad job in deployments/applications with static tile config, then wire its address into L1's already-deployed oauth2-proxy as the reverse-proxy upstream (replacing the static://200 placeholder), so an authenticated operator gets one themed landing page instead of memorizing hostnames."
tags = ["homepage", "nomad", "haproxy", "oauth2-proxy"]
---

# Ticket: L2-landing-homepage

## 1. Title

Deploy Homepage (gethomepage) as its own Nomad job under
`deployments/applications/`, and wire its address into L1's already-deployed
oauth2-proxy as the reverse-proxy upstream (replacing the `static://200`
placeholder), so an authenticated operator reaches a themed landing page with
tiles for the cluster's still-live services at `dash.lab.orangecluster.nl`.

## 2. Size / Effort

**M (medium).** Smaller than the original plan: there is no HAProxy edit at
all now (L1 owns the `dash` route end-to-end). The effort drivers are the
static config surface (a `services.yaml`/`settings.yaml`/`widgets.yaml` set
for the eight services that still exist — not nine, see Context), a
cross-root Terraform change (new job + firewall rule in
`deployments/applications`, an optional host volume in
`deployments/infrastructure`), and one cross-ticket edit to L1's
already-deployed `oauth2-proxy.hcl`/`deployments/infrastructure/services.tf` (a single template-var
change, but one that touches the live auth gate for `dash`).

## 3. Triggered by

Auth epic, stage L2. L1 (oauth2-proxy reverse-proxy gate) is `done` and
already routes `dash.lab.orangecluster.nl` to itself, deliberately serving a
`static://200` placeholder so L2 could land the real upstream without
reopening L1's HAProxy wiring. L2 builds the landing-page content and
completes that handoff. Flat access: everyone who passes Vault login sees the
same tiles, no per-user RBAC.

## 4. Context

Today the cluster has an OAuth-gated route to nothing: `dash.lab.orangecluster.nl`
is wired end-to-end by L1 but serves a bare placeholder, not a landing page.

- **Edge.** HAProxy (`deployments/infrastructure/services/haproxy.hcl`) runs
  pinned to `firebat` (`haproxy.hcl:6-9`) with two frontends: `http_in`
  (`haproxy.hcl:91-93`) only 301-redirects to HTTPS; `https_in`
  (`haproxy.hcl:95-96`) terminates TLS with a Let's Encrypt wildcard rendered
  from Vault KV2 by a *separate* template (`haproxy.hcl:62-72`) — the config
  itself is a second template (`haproxy.hcl:74-159`). Two inline templates,
  not the "single inline template" the pre-rework version of this ticket
  claimed. Every hostname ACL (`haproxy.hcl:98-107`) and `use_backend`
  (`:109-118`) lives on `https_in`; static backends are at `haproxy.hcl:127-156`.
- **`dash` already exists and is L1's.** `acl is_dash` (`haproxy.hcl:107`),
  `use_backend dash if is_dash` (`:118`), and `backend dash` → `server dash1
  192.168.2.50:4180 check` (`:155-156`) route straight to oauth2-proxy on
  `radxa-dragon-q6a`. **L2 must not add, edit, or duplicate any of this.**
- **oauth2-proxy is live but points at a placeholder.**
  `deployments/infrastructure/services/oauth2-proxy.hcl:54` hardcodes
  `OAUTH2_PROXY_UPSTREAMS="static://200"` — L1's deliberate stand-in, chosen
  so L2 could fill in the real address without reopening L1's HAProxy wiring
  (`.loop/plans/L1-landing-oauth2-proxy.md:529-553`, "The L1/L2 upstream").
  Confirmed live 2026-08-22: `curl -sI https://dash.lab.orangecluster.nl/` →
  `HTTP/2 503`; `curl -sI http://dash.lab.orangecluster.nl/` → `301` to the
  same host over HTTPS (`haproxy.hcl:91-93`).
- **Basic auth survives on one backend only.** `userlist openfang_users`
  (`haproxy.hcl:88-89`); only `backend phoenix` (`haproxy.hcl:142-144`) still
  carries `http-request auth unless { http_auth(openfang_users) }`. `backend
  bifrost` (`:152-153`) has no auth line (native auth, commit ac3267b).
  There is no `backend mlflow` anywhere in the file — the mlflow ACL/backend
  and the mlflow service itself were removed together by commit fab7e53
  (`deployments/applications/storage.tf:23-26` records the artifact bucket
  kept behind on request); `R1-rollout-mlflow-oauth2-proxy` is `blocked` in
  the ledger for the same reason (the service is gone).
- **Prometheus and Loki have no edge route, on purpose.** No `is_prometheus`/
  `is_loki` ACL exists in `haproxy.hcl` (grep confirms). N1's follow-on
  (commit fe681b4) deleted both to stop leaking every metric and log line
  to anyone who reaches the edge (`docs/haproxy_reverse_proxy.md:32-38`). The
  firewall backs this up: `deployments/infrastructure/services.tf:204-215` restricts Prometheus's 9090
  to `192.168.2.47` (its own host) and `192.168.2.30` (HAProxy's host) only.
- **DNS needs nothing.** `getent hosts dash.lab.orangecluster.nl` resolves to
  `192.168.2.30` today (public wildcard A record; probed 2026-08-22), same as
  any other `*.lab.orangecluster.nl` name — no F4/dnsmasq dependency
  (`docs/haproxy_reverse_proxy.md:49-54`).
- **Two Terraform roots, not one.** `deployments/infrastructure/` holds core
  platform services — HAProxy, Postgres, MinIO, Prometheus, Grafana,
  oauth2-proxy, NATS, Redis (`deployments/infrastructure/services.tf`).
  `deployments/applications/` is a separate root (its own `backend.tf`,
  `providers.tf`, `justfile`) holding user/agent-facing apps: Phoenix, Memex,
  Hermes, Bifrost, Loki (`deployments/applications/services.tf`). Homepage is
  application content, not core infrastructure — it belongs in
  `deployments/applications/`, alongside Phoenix/Memex/Bifrost.
- **Cross-root host volumes are an established pattern.**
  `nomad_dynamic_host_volume` resources for jobs that live in `applications`
  are still declared in `deployments/infrastructure/services.tf` — e.g. `memex_data`
  (`deployments/infrastructure/services.tf:42-60`) is mounted by
  `deployments/applications/services/memex.hcl`; `loki_data`
  (`deployments/infrastructure/services.tf:122-140`) is mounted by
  `deployments/applications/services/loki.hcl:21-26`. Neither `applications`
  `nomad_job` resource carries a `depends_on` on the volume (no cross-root
  `depends_on` exists in Terraform) — apply order is operator-managed today,
  the same way it would be for Homepage.
- **`ubuntu` (192.168.2.47) is already a busy node.** Grafana
  (`deployments/infrastructure/services.tf:216-224` firewall; `grafana.hcl:9,14`: port 3000), Prometheus
  (`prometheus.hcl:9,14`: port 9090), and Loki
  (`deployments/applications/services/loki.hcl:9,14,17`: ports 3100/9095) all
  run there. The operator's resolved placement for Homepage (Q3, below) is
  also `ubuntu`, so its static port must avoid 3000/3100/9095/9090.
- **Config-as-files pattern to copy.** Grafana mounts rendered `local/...`
  files read-only via `config.volumes` (`grafana.hcl:51-59`), written by
  `template` stanzas (`grafana.hcl:77-84,86-227`), with a host volume for its
  writable data dir (`grafana.hcl:18-23,62-65`, backed by
  `deployments/infrastructure/services.tf:102-120`). Homepage's YAML config follows the same shape,
  starting static.
- **NATS monitoring target.** `192.168.2.50:8222/healthz`
  (`nats.hcl:17-19,56-65`), already open to the LAN (`deployments/infrastructure/services.tf:275-284`).

What is missing: no Homepage job, no `deployments/applications/services/homepage.hcl`,
no tile config, and oauth2-proxy's upstream still points at its own
placeholder instead of Homepage.

## 5. Non-goals / out of scope

- **No per-user RBAC / no per-tile access control.** Flat access is
  explicit: all authenticated users see the same tiles.
- **No consul-template auto-population in this ticket.** Start with static
  `services.yaml`. Optional/later, out of scope here.
- **Do not touch `haproxy.hcl` at all.** The `dash` ACL/backend
  (`haproxy.hcl:107,118,155-156`) already exists and is L1's. Zero edits to
  this file.
- **Do not implement or redesign L1** (done). The only permitted
  cross-ticket edit is the single `OAUTH2_PROXY_UPSTREAMS` value described in
  Requirement 4 — nothing else about L1's OIDC client, Vault config, or
  jobspec changes.
- **Do not implement the rejected alternatives** (Homer, Consul built-in
  UI). Context only.
- **No TLS work.** HAProxy already terminates TLS (`haproxy.hcl:95-96`);
  this ticket makes no `haproxy.hcl` edit of any kind.
- **No re-adding an edge route for Prometheus or Loki**, directly or
  indirectly (e.g. a new firewall opening toward the edge). N1's fe681b4
  removed both deliberately; both are informational-only tiles here — no
  URL, no widget.
- **No MLflow tile.** The service — job, secrets, database, and its HAProxy
  route — was fully removed by commit fab7e53
  (`deployments/applications/storage.tf:23-26`). If MLflow returns, its tile
  is a follow-up ticket's problem, not this one's.
- **No removal of the existing openfang basic-auth** (phoenix only,
  `haproxy.hcl:142-144`) — moot, since L2 touches no HAProxy config.
- **No Zitadel.** Any reference is a factual error.

## 6. Requirements & restrictions

The change MUST:

1. **Add a Homepage Nomad job** at
   `deployments/applications/services/homepage.hcl`, driver `podman`,
   arm64-compatible image pinned to a specific tag (never `latest`),
   constrained to `ubuntu` (Q3, resolved), `network_mode = "host"` (the
   common pattern in this repo — most podman tasks use it; `minio.hcl`
   and `redis.hcl` are the counterexamples, both static-ported without
   it, so "host" here is a deliberate choice matching the majority
   convention, not an unconditional repo rule), a static port
   that avoids `ubuntu`'s existing 3000/3100/9095/9090 (recommend `3001`;
   confirm free before committing, see Open Questions Q3). Set
   `HOMEPAGE_ALLOWED_HOSTS=dash.lab.orangecluster.nl` (verify the exact
   env-var name against the pinned image's docs — recent gethomepage
   releases refuse requests without it). oauth2-proxy forwards the original
   `Host:` header by default (`--pass-host-header` defaults `true` and is not
   overridden in `oauth2-proxy.hcl`), so the value seen by Homepage stays
   `dash.lab.orangecluster.nl`.
2. **(Conditional on Q4) Provision a dynamic host volume** for Homepage's
   writable state in `deployments/infrastructure/services.tf` — the same
   root as every other dynamic host volume, *not* `deployments/applications`
   — following the `grafana_data` (`deployments/infrastructure/services.tf:102-120`) /
   `loki_data` (`deployments/infrastructure/services.tf:122-140`) shape:
   `mkdir` plugin, `default` node_pool, a `constraint` pinning `ubuntu`,
   small capacity, `single-node-writer`/`file-system`. Mount it from
   `homepage.hcl` the same cross-root way
   `deployments/applications/services/loki.hcl:21-26` mounts `loki_data`. If
   implementation shows Homepage needs no writable state, drop the volume
   and mount config read-only only.
3. **Register the job** with a `nomad_job "homepage"` resource in
   `deployments/applications/services.tf` using `templatefile(...)` (model:
   `nomad_job "loki"`, `deployments/applications/services.tf:164-169`, same file, no
   `depends_on` needed there either).
4. **Wire Homepage into L1's already-deployed oauth2-proxy as its
   reverse-proxy upstream. Do not touch `haproxy.hcl`.** L1 owns the `dash`
   route end-to-end (`haproxy.hcl:107,118,155-156`). The only integration
   edit is inside oauth2-proxy's own already-deployed files:
   - `deployments/infrastructure/services/oauth2-proxy.hcl:54` — change the
     hardcoded `OAUTH2_PROXY_UPSTREAMS="static://200"` to a template var,
     e.g. `OAUTH2_PROXY_UPSTREAMS="${homepage_upstream}"`.
   - `deployments/infrastructure/services.tf:400-409`
     (`resource "nomad_job" "oauth2_proxy"`) — add
     `homepage_upstream = "http://<homepage-host>:<homepage-port>"` to the
     `templatefile(...)` vars map.
   This is a cross-ticket edit to L1's landed files — unusual, and worth
   flagging explicitly in the PR description — but it is exactly the seam
   L1's placeholder was built for
   (`.loop/plans/L1-landing-oauth2-proxy.md:536-546`: "L2 then changes one
   flag to point at Homepage and owns the check").
5. **Add a firewall rule** in `deployments/applications/services.tf`'s
   `local.firewall_rules` opening Homepage's chosen port to `192.168.2.50`
   (oauth2-proxy) ONLY — model the single-caller shape of the infrastructure
   root's `oauth2_proxy` rule (`deployments/infrastructure/services.tf:285-292`). A LAN-wide rule would
   let anyone reach Homepage directly and skip the auth gate entirely — the
   same class of mistake N1's follow-on fixed for Prometheus and Loki.
6. **Populate tiles for the eight services that still exist on this
   cluster** (not nine — MLflow is gone, see Context): MinIO, Grafana,
   Phoenix, and Memex as clickable tiles pointing at their
   `*.lab.orangecluster.nl` HAProxy hostnames; NATS as a clickable tile
   pointing at its direct monitoring endpoint (`192.168.2.50:8222`);
   Postgres as a direct host:port reference tile (not browsable — no widget
   required); Prometheus and Loki as informational-only tiles — no URL, no
   widget (Non-goals; re-adding their edge route is forbidden).
7. **Add live-status widgets** (Homepage `siteMonitor`/service widgets) for
   the five checked-and-reachable services named in Requirement 6 (MinIO,
   Grafana, Phoenix, Memex, NATS); none for Prometheus/Loki (forbidden) and
   none for MLflow (dropped entirely).
8. **Success criterion:** browsing `https://dash.lab.orangecluster.nl/`
   after completing L1's Vault login renders the themed Homepage with
   working tiles for the eight current services; unauthenticated access is
   still blocked by oauth2-proxy exactly as it is today (L2 changes nothing
   about that gate); oauth2-proxy's allocation stays healthy after the
   upstream edit; the rendered oauth2-proxy env shows the real Homepage
   address, not `static://200`.

Restrictions the repo enforces (each cited):

- **Simplicity / surgical changes / no speculative build** (`CLAUDE.md`
  §§1-3): start static, eight tiles only, zero `haproxy.hcl` edits, one
  template-var edit in L1's already-deployed files.
- **Secrets in Vault, never hardcoded** (`README.md:36`: "everything lives
  in Vault KV2. Nothing in this repo should contain a real credential"): any
  widget that needs a credential to read status pulls it from Vault KV2 via
  a `template`/`vault {}` stanza (model: `grafana.hcl:29,77-84`), not
  inline. Prefer unauthenticated health/`siteMonitor` widgets where
  possible to avoid new secrets.
- **Nomad HCL formatting** (`.pre-commit-config.yaml` `nomad-fmt` hook,
  `justfile:9-11` `format: nomad fmt -recursive`): new/edited `.hcl` must
  pass `nomad fmt`.
- **Terraform formatting/validation for both roots**
  (`.pre-commit-config.yaml` `terraform-fmt`/`terraform-validate`,
  `scripts/tf_validate.sh` iterating `deployments/infrastructure` and
  `deployments/applications`): edits in either root are gated by the same
  single `just pre_commit` run.
- **Pin the container image** (repo convention, e.g. `grafana.hcl:48`,
  `deployments/applications/services/bifrost.hcl:40`). No `:latest`.
- **No Zitadel** anywhere in config, comments, or tiles.

## 7. Code surface

- **CREATE** `deployments/applications/services/homepage.hcl` — new Nomad
  job: podman task constrained to `ubuntu`, pinned arm64 gethomepage image,
  host network with a static port (recommend 3001), `template` stanzas
  rendering `settings.yaml`/`services.yaml`/`widgets.yaml` into `local/...`
  and mounting them read-only via `config.volumes`,
  `HOMEPAGE_ALLOWED_HOSTS` env, a `service` + health `check`, and an
  optional `volume`/`volume_mount` for `homepage_data` (Q4). Models:
  `grafana.hcl:1-75,86-227` (config-as-files pattern),
  `deployments/applications/services/loki.hcl:1-27` (applications-root job
  on the same node, cross-root host-volume reference),
  `deployments/applications/services/bifrost.hcl:1-58`
  (applications-root podman/vault/template shape).
- **EDIT** `deployments/applications/services.tf` — add
  `resource "nomad_job" "homepage"` using `templatefile(...)` (model:
  `nomad_job "loki"`, `:164-169`); add a `homepage` entry to
  `local.firewall_rules` (`:42-95`) opening the chosen port from
  `192.168.2.50` only (model: the `loki` entry, `:75-85`, same host/ssh_user
  since Homepage and Loki share `ubuntu`).
- **EDIT (conditional on Q4)** `deployments/infrastructure/services.tf` —
  add `resource "nomad_dynamic_host_volume" "homepage_data"` (model
  `grafana_data`, `:102-120`; or `loki_data`, `:122-140`).
- **EDIT** `deployments/infrastructure/services/oauth2-proxy.hcl:54` —
  replace the hardcoded `OAUTH2_PROXY_UPSTREAMS="static://200"` with
  `OAUTH2_PROXY_UPSTREAMS="${homepage_upstream}"`. Cross-ticket edit to L1's
  file (Requirement 4).
- **EDIT** `deployments/infrastructure/services.tf:400-409`
  (`resource "nomad_job" "oauth2_proxy"`) — add
  `homepage_upstream = "http://<homepage-host>:<homepage-port>"` to the
  `templatefile(...)` vars map. Cross-ticket edit to L1's file
  (Requirement 4).
- Read-only anchors to consume, not edit: `haproxy.hcl:98-107,109-118,127-156`
  (existing routes — tile targets and the `dash` route L2 must not touch);
  `deployments/infrastructure/services.tf:204-215,216-224,275-284,285-292` (firewall rules for tile
  targets and the oauth2-proxy single-caller pattern to model);
  `deployments/applications/storage.tf:23-26` (MLflow removal);
  `docs/haproxy_reverse_proxy.md:1-30,32-38` (current service map,
  Prometheus/Loki policy); `.loop/plans/L1-landing-oauth2-proxy.md:529-553`
  (the placeholder-handoff design L2 completes).

## 8. Tests & validation gates

This repo has **no unit-test suite for infrastructure**
(`.claude/rules/python-testing.md`'s all-code-needs-tests rule targets
`cli/`'s Python code; there is none here). Validation is the
Terraform-aware pre-commit gate, plus live evals against the reachable
cluster.

- **Repo gate:** `just pre_commit` (= `pre-commit run --all-files`, root
  `justfile:17-19`). `scripts/tf_validate.sh` runs `terraform validate`
  offline over three roots, including both `deployments/infrastructure` and
  `deployments/applications` — so this ticket's new `applications` job/
  firewall entry AND its cross-ticket edit to `infrastructure`'s
  `oauth2-proxy.hcl`/`deployments/infrastructure/services.tf` are both schema-checked by the same
  command. Required to pass: `homepage.hcl` through `nomad fmt`
  (`justfile:9-11`, `.pre-commit-config.yaml` `nomad-fmt`); both `.tf` edits
  through `terraform fmt -check -recursive` and `terraform-validate`; all
  touched files through `end-of-file-fixer` without tripping
  `detect-private-key`.
- **No HAProxy config-validity gap this time.** The pre-rework version of
  this ticket needed a manual `haproxy -c` check because it edited the
  config heredoc directly. L2 no longer touches `haproxy.hcl` at all, so
  that gap does not apply here.
- **The oauth2-proxy edit is a plain Terraform interpolation, not a foreign
  DSL.** `${homepage_upstream}` is resolved by `templatefile()` before
  Nomad ever sees the job, so the rendered value is visible directly via
  `nomad job inspect oauth2-proxy` — checked by the eval guardrail row
  below, not by a repo gate (no gate parses rendered Nomad job output).
- **Evals (live) — acceptance:** the cluster is reachable from this
  environment (`VAULT_ADDR`, `VAULT_TOKEN`, `NOMAD_ADDR`, `NOMAD_TOKEN`,
  `CONSUL_HTTP_ADDR` are set — confirmed reachable during this rework via
  `curl`/`getent hosts` probes, Context above). Every row targets
  `https://`, never the port-80 redirect. Full rows:
  `.loop/evals/L2-landing-homepage.md`.
- **Adversarial review** (`.claude/rules/adversarial-reviews.md`): before
  reporting done, hand the diff to a review sub-agent to confirm: no
  `haproxy.hcl` edit exists anywhere in the diff; the oauth2-proxy upstream
  edit is the only change to L1's files; the image is pinned/arm64; no
  secret is hardcoded; Homepage's firewall rule admits only `192.168.2.50`;
  there is no MLflow tile; Prometheus/Loki carry no URL and no widget.
- **Eval marker (loop-harness acceptance):** the live evals above are
  encoded as the five-column scorer table at
  `.loop/evals/L2-landing-homepage.md` (validated by `loopctl eval`).

## 9. Risk assessment

**Precondition, checked before trusting any gate-dependent row in §8.**
*(Added 2026-08-23, second plan review.)* As of this writing,
oauth2-proxy's `dash` HAProxy backend is DOWN (`check_status=L4TOUT`)
even though the job itself is healthy — see Premise P2. This is a
pre-existing condition unrelated to this ticket's own changes, most
likely the firewall rule in `local.firewall_rules["oauth2_proxy"]`
having fallen out of effect on the live host. Before running any §8
eval row that depends on `dash` actually routing traffic (the
unauthenticated-block row, the post-login tile-view row), confirm
`http://192.168.2.30:8404/;csv` shows `dash` as `UP`. If it does not,
this is an operator fix outside L2's scope (most likely: re-run
`terraform apply` in `deployments/infrastructure/`, which
unconditionally re-executes every `local.firewall_rules` entry via its
`timestamp()` trigger) before continuing.

- **Blast radius:** two distinct surfaces. (a) The new Homepage job, its
  optional host volume, and its firewall rule are additive and isolated to
  `deployments/applications/`. (b) The cross-ticket edit to L1's
  already-deployed `oauth2-proxy.hcl`/`deployments/infrastructure/services.tf` is small (one
  interpolated value) but touches the live auth gate for the whole `dash`
  route — a malformed render could break the currently-working login flow
  for the landing page (though not any other service, since oauth2-proxy
  gates only `dash`).
- **Reversibility:** high for (a) — destroy the job, volume, and firewall
  rule. For (b), revert is a one-line diff back to `static://200`;
  redeploying restores exactly L1's prior, already-verified state.
- **Likeliest failure modes:**
  1. **Homepage upstream value wrong or malformed** (typo in host:port,
     missing scheme) — oauth2-proxy proxies to a broken address. Symptom is
     a 502/timeout *after* a successful login, not a crash: oauth2-proxy
     itself stays healthy. Caught by the eval guardrail row reading the
     rendered `OAUTH2_PROXY_UPSTREAMS` value.
  2. **`HOMEPAGE_ALLOWED_HOSTS` unset/wrong** — page returns blank/403
     behind the proxy host header. Set it to `dash.lab.orangecluster.nl`.
  3. **Port collision on `ubuntu`.** Homepage's default port (often 3000)
     collides with Grafana, which runs on `ubuntu`
     (`deployments/infrastructure/services.tf:216-224`, `grafana.hcl:9,14`) — not firebat. Loki
     (3100/9095) and Prometheus (9090) are also there. Pick a free port
     (recommend 3001) and update the firewall rule and the
     `homepage_upstream` value together if a different one is chosen.
  4. **Missing or too-wide firewall rule** — too narrow: oauth2-proxy's
     reverse-proxy call times out even though both jobs are individually
     healthy; too wide (LAN-wide instead of `192.168.2.50`-only): anyone on
     the LAN can reach Homepage directly and skip the auth gate, the same
     class of mistake N1's follow-on fixed for Prometheus/Loki.
  5. **Cross-root apply ordering.** If Q4 provisions a host volume in
     `infrastructure` and the `applications` root applies first,
     `nomad_job.homepage` fails to place for a missing volume. No
     Terraform-enforced `depends_on` across roots is possible — this
     mirrors the pre-existing `loki_data`/`memex_data` pattern, not a new
     class of risk, but still worth applying `infrastructure` first.
  6. **A widget needing a secret** tempts an inline credential; route
     through Vault or use an unauthenticated health check instead.

## 10. Subtickets

Ordered, dependency-aware.

1. **Confirm the free port on `ubuntu`** given the now-known collision with
   Grafana (3000)/Loki (3100, 9095)/Prometheus (9090). Recommend 3001.
   Depends on: nothing.
2. **(If Q4 keeps a volume) Provision the host volume** in
   `deployments/infrastructure/services.tf` (model `grafana_data`/
   `loki_data`). Depends on: nothing.
3. **Write `deployments/applications/services/homepage.hcl`.** Job with
   pinned arm64 image, static config `template`s, optional host-volume
   mount, `HOMEPAGE_ALLOWED_HOSTS`, health check. Depends on: 1, 2.
4. **Populate tiles + status widgets.** The eight services from
   Requirement 6, with real URLs where applicable; secrets (if any) via
   Vault. Depends on: 3.
5. **Register the job + firewall rule.** `nomad_job "homepage"` and the
   `local.firewall_rules` entry in `deployments/applications/services.tf`.
   Depends on: 3.
6. **Wire Homepage as oauth2-proxy's upstream.** Edit
   `oauth2-proxy.hcl:54` and `deployments/infrastructure/services.tf:400-409` in
   `deployments/infrastructure/` — L1's already-deployed files. Depends on:
   5 (need Homepage's real host:port first).
7. **Validate + adversarial review.** `just pre_commit`, deploy acceptance,
   review sub-agent. Depends on: 1-6.

## 11. Open questions

- **Q1 — SUPERSEDED. L1 is done; no forward-auth question remains.** L1
  shipped reverse-proxy exactly as resolved 2026-07-23: HAProxy routes
  `dash.lab.orangecluster.nl` to oauth2-proxy
  (`haproxy.hcl:107,118,155-156`); oauth2-proxy reverse-proxies to Homepage
  via `--upstream`/`OAUTH2_PROXY_UPSTREAMS`. L2's job is only to fill in
  that upstream (Requirement 4). Nothing left to decide.
- **Q2 — Which gethomepage image tag?** The upstream is
  `ghcr.io/gethomepage/homepage` (multi-arch, arm64-capable).
  *Recommendation:* pin a specific released tag (verify arm64 in the
  manifest during implementation), never `latest`, matching the repo's
  pin-everything convention (`grafana.hcl:48`).
- **Q3 — Node/port, REFINED.** `ubuntu` (192.168.2.47) was already resolved
  2026-07-23. New finding this rework: `ubuntu` already holds 3000
  (Grafana), 3100/9095 (Loki), and 9090 (Prometheus).
  *Recommendation:* port 3001; confirm free at implementation time (e.g. a
  live port check on `ubuntu`) before committing. Update the firewall rule
  and `homepage_upstream` together if a different port is picked.
- **Q4 — Does Homepage need a host volume at all, and if so, where?**
  Homepage is largely stateless when config is file-mounted; a host volume
  mainly backs its writable data dir. If kept, it is declared in
  `deployments/infrastructure/services.tf` (the same root as every other
  dynamic host volume, including ones mounted by applications-root jobs —
  model `loki_data`/`memex_data`), not in `deployments/applications`.
  *Recommendation:* keep a small host volume for parity with the repo
  pattern; if implementation shows Homepage needs no writable state, drop
  it and mount config read-only only — surface the simplification rather
  than carrying an unused volume.
- **Q5 — Proceed with the cross-ticket edit to L1's landed files without a
  fresh operator sign-off, or block until confirmed?** Editing a `done`
  ticket's files from a different ticket is unusual. L1's own plan text
  pre-approves exactly this handoff
  (`.loop/plans/L1-landing-oauth2-proxy.md:536-546`: "L2 then changes one
  flag to point at Homepage and owns the check").
  *Recommendation:* proceed — this is what the placeholder was built for —
  but call it out explicitly in the PR description so a reviewer sees it
  was deliberate, not accidental scope creep into another ticket's files.

## Premises / assumptions

- **P1.** HAProxy's `dash` ACL/backend already exists and is owned by L1;
  L2 must not duplicate or edit it.
  `Evidence:` `haproxy.hcl:107` (`acl is_dash`), `:118`
  (`use_backend dash if is_dash`), `:155-156` (`backend dash` →
  `server dash1 192.168.2.50:4180 check`); L1's own Requirement 6 and Code
  surface (`.loop/plans/L1-landing-oauth2-proxy.md:179-183,386-394`).
- **P2.** oauth2-proxy's job is deployed and healthy at the application
  layer (Nomad/Consul), configured to proxy to a hardcoded placeholder,
  not to Homepage — but its HAProxy backend is DOWN as of this writing.
  *(Corrected 2026-08-23, second plan review: an earlier version of
  this premise called oauth2-proxy "live," which conflated "the job
  exists and works" with "the edge can currently reach it." Those are
  different facts, and the second one is false right now.)*
  `Evidence:` `oauth2-proxy.hcl:54` (`OAUTH2_PROXY_UPSTREAMS="static://200"`);
  ledger `L1-landing-oauth2-proxy` stage `done`.
  `probe, 2026-08-23:` Consul's own health check (which runs locally on
  oauth2-proxy's node) reports `passing` — `HTTP GET
  http://192.168.2.50:4180/ping: 200 OK`. HAProxy's stats page
  (`http://192.168.2.30:8404/;csv`) reports the `dash` backend `DOWN`,
  `check_status=L4TOUT` (a Layer-4/TCP timeout from HAProxy's own
  health check, run cross-host from `firebat`), with `bifrost` on the
  SAME node (`192.168.2.50`) reporting `UP` at the same moment — ruling
  out a network-path or node-down explanation and pointing at a
  firewall rule (`local.firewall_rules["oauth2_proxy"]`,
  `services.tf`) that exists in Terraform but is not currently in
  effect on the live host. `curl -sI https://dash.lab.orangecluster.nl/`
  → `HTTP/2 503` matches this: it is HAProxy's own "no server
  available" response, not a response from oauth2-proxy. See §9's new
  precondition — this must be confirmed healthy again before trusting
  any of §8's gate-dependent eval rows.
- **P3.** HAProxy terminates TLS on `*:443`; `*:80` only redirects; L2 makes
  zero edits to `haproxy.hcl`.
  `Evidence:` `haproxy.hcl:91-96`.
  `probe:` `curl -sI http://dash.lab.orangecluster.nl/` → `301` to
  `https://dash.lab.orangecluster.nl/`, captured 2026-08-22.
- **P4.** Public wildcard DNS already resolves `dash.lab.orangecluster.nl`;
  no F4/dnsmasq dependency.
  `probe:` `getent hosts dash.lab.orangecluster.nl` → `192.168.2.30`,
  captured 2026-08-22. Ledger: `F4-foundation-dnsmasq-localstack-dns`
  `dropped: true`; `N2-netsec-remove-dnsmasq-for-public-dns` `done`.
- **P5.** Prometheus and Loki have no edge route and must not get one; both
  are firewall-restricted to two cluster-internal hosts.
  `Evidence:` `grep -n "prometheus\|loki" haproxy.hcl` matches nothing
  routing-related; `deployments/infrastructure/services.tf:204-215`; commit fe681b4
  ("N1 follow-on: stop routing Prometheus and Loki through the edge");
  `docs/haproxy_reverse_proxy.md:32-38`.
- **P6.** MLflow no longer exists on this cluster; no tile can point at it.
  `Evidence:` `deployments/applications/storage.tf:23-26`; commit fab7e53
  ("feat: redis" — also removed the mlflow job, secrets, database, and
  HAProxy route together, confirmed via `git show fab7e53` diffing
  `haproxy.hcl`); ledger `R1-rollout-mlflow-oauth2-proxy` stage `blocked`,
  citing the same closure.
- **P7.** Only `phoenix` carries HAProxy basic-auth today; bifrost carries
  none and mlflow's backend does not exist.
  `Evidence:` `haproxy.hcl:142-144` (phoenix, only `http-request auth` line
  in the file); `haproxy.hcl:152-153` (bifrost, no auth line, commit
  ac3267b); no `backend mlflow` anywhere in `haproxy.hcl` (commit
  fab7e53).
- **P8.** Grafana, Prometheus, and Loki all run on `ubuntu`
  (192.168.2.47), not firebat; their ports (3000, 9090, 3100/9095) are the
  ones Homepage's chosen port must avoid.
  `Evidence:` `deployments/infrastructure/services.tf:111-114` (`grafana_data` constraint,
  `value = "ubuntu"`), `grafana.hcl:9,14`; `prometheus.hcl:9,14`;
  `deployments/applications/services/loki.hcl:9,14,17`.
- **P9.** `deployments/applications/` is the correct root for Homepage,
  matching precedent for comparable jobs; `deployments/infrastructure/`
  hosts core platform services.
  `Evidence:` directory contents of both roots (`deployments/applications/services/`:
  bifrost.hcl, hermes.hcl, loki.hcl, memex.hcl, phoenix.hcl;
  `deployments/infrastructure/services/`: acme.hcl, grafana.hcl, haproxy.hcl,
  minio.hcl, nats.hcl, oauth2-proxy.hcl, postgres.hcl, prometheus.hcl,
  promtail.hcl, redis.hcl); `deployments/applications/backend.tf` (separate
  Consul backend) and `deployments/applications/justfile` (separate `just
  apply`); `scripts/tf_validate.sh` treats both as distinct validated roots.
- **P10.** Cross-root host volumes are an established pattern: a
  `nomad_dynamic_host_volume` declared in `infrastructure` can be mounted by
  a job registered in `applications`, with no Terraform `depends_on` across
  roots.
  `Evidence:` `deployments/infrastructure/services.tf:42-60` (`memex_data`, infra) +
  `deployments/applications/services/memex.hcl` (volume reference, no
  `depends_on` in `deployments/applications/services.tf` on that resource);
  `deployments/infrastructure/services.tf:122-140` (`loki_data`, infra) +
  `deployments/applications/services/loki.hcl:21-26` (volume reference,
  same absence of cross-root `depends_on`).
- **P11.** L1 is `done` and its own plan text explicitly anticipated this
  exact cross-ticket edit.
  `Evidence:` ledger `L1-landing-oauth2-proxy` stage `done`;
  `.loop/plans/L1-landing-oauth2-proxy.md:529-553` ("The L1/L2 upstream, and
  the cycle it used to create": "L1 ships with a self-contained upstream...
  L2 then changes one flag to point at Homepage and owns the check").

## Resolved forks (operator, 2026-07-23; Q1 discharged 2026-08-23 now that L1 is done)

- **Q1 → DISCHARGED.** L1 shipped reverse-proxy exactly as resolved:
  HAProxy routes `dash.lab.orangecluster.nl` to oauth2-proxy
  (`haproxy.hcl:107,118,155-156`); oauth2-proxy reverse-proxies to Homepage
  via `--upstream`/`OAUTH2_PROXY_UPSTREAMS`. L2's job is now only to fill in
  that upstream (Requirement 4) — there is no forward-auth anywhere in this
  design and no HAProxy edit left for L2 to make.
- **Q2 → Pin a specific released `ghcr.io/gethomepage/homepage` tag**
  (verify arm64 in the manifest during implementation); never `latest`.
- **Q3 → `ubuntu` (192.168.2.47), REFINED 2026-08-23.** Avoid ports already
  used there — 3000 (Grafana), 3100/9095 (Loki), 9090 (Prometheus).
  Recommend 3001; confirm free before committing. Homepage's firewall rule
  needs to admit only oauth2-proxy's host, `192.168.2.50` (Requirement 5) —
  not HAProxy's, since HAProxy never talks to Homepage directly.
- **Q4 → Small host volume for parity (default).** If kept, it is declared
  in `deployments/infrastructure/services.tf` (the same root as every other
  dynamic host volume, including ones mounted by applications-root jobs —
  model `loki_data`/`memex_data`), not in `deployments/applications`. If
  implementation shows Homepage needs no writable state, drop the volume
  and mount config read-only only.

**Dependencies:** L2 depends on **L1** (done) and **A1** (done). No F4
dependency — public wildcard DNS already resolves
`dash.lab.orangecluster.nl` (see Premise P4). Front-matter `depends_on` is
unchanged and correct.

## Plan review, 2026-07-30 (A1 premise sweep)

**Premise: BROKEN. Gate verdict: `fail`.** Reviewed by the loop's
`loop-plan-reviewer` against the repo AND the live cluster, as part of
`A1-audit-plan-premise-sweep`. Thirteen plans were reviewed; none passed clean.

**Read `.loop/verdicts/L2-landing-homepage.plan-validator.md` before touching this plan.**
It carries the per-assumption findings with evidence anchors and the full
required-fix list. This section is a pointer, not a summary of record.

Headline defect: The body, code surface and subticket 6 mandate a `dash`
backend pointing straight at Homepage, contradicting the plan's own resolved
fork. Its security eval row passes today against a cluster with no Homepage
at all.

This ticket was **`blocked`** (`unresolved-design-fork`). A1 applied no
structural fix here: the required fixes reversed design decisions or needed
an operator call. See the rework section below for what changed.

## Plan rework, 2026-08-23 (required fixes applied)

Reworked in place after the 2026-07-30 `fail` verdict
(`.loop/verdicts/L2-landing-homepage.plan-validator.md`). All eight required
fixes applied, plus findings from a fresh skeptical pass over the whole
rewritten plan that the fix list did not name:

1. Requirement 4, Code surface, and Subticket 6 no longer build a `dash`
   HAProxy backend. L1 (done, `haproxy.hcl:107,118,155-156`) already owns
   that route. L2's only integration edit is now the single
   `OAUTH2_PROXY_UPSTREAMS` value inside L1's already-deployed
   `oauth2-proxy.hcl`/`deployments/infrastructure/services.tf` (Requirement 4) — a cross-ticket edit,
   called out explicitly as such. All "forward-auth" occurrences (including
   the front-matter summary) are gone.
2. Context rewritten against the current edge: two frontends
   (`haproxy.hcl:91-93,95-96`), two templates (`:62-72,74-159`), fresh
   ACL/`use_backend`/backend anchors (`:98-107,109-118,127-156`).
3. Prometheus and Loki are informational-only tiles now — no URL, no
   widget; re-adding an edge route is a Non-goal. **Not named by the
   verdict, found in this rework: MLflow has no tile at all.** The service
   itself — job, secrets, database, and its HAProxy route — was fully
   removed by commit fab7e53 (`deployments/applications/storage.tf:23-26`);
   `R1-rollout-mlflow-oauth2-proxy` is `blocked` for the same reason. The
   tile count drops from nine to eight.
4. `.loop/evals/L2-landing-homepage.md` rewritten against HTTPS throughout.
   The unauthenticated-block row now copies L1's own 40x-or-Vault-302
   pattern instead of accepting any redirect. The old port-80
   "no regression" row is retired — L2 makes zero `haproxy.hcl` edits now,
   so it was protecting against a risk this ticket no longer carries — and
   replaced with a guardrail on the one shared-blast-radius file L2 does
   edit: oauth2-proxy's own already-deployed job.
5. The F4 completion-block paragraph is deleted outright (not just
   footnoted) — see the Resolved forks section and Premise P4 for the DNS
   fact it was trying to state.
6. Bifrost has no basic-auth line at all (native auth, ac3267b); mlflow's
   basic-auth line does not exist either, because the mlflow backend itself
   is gone (fab7e53) — a second, independent reason beyond B1 alone. Only
   phoenix (`haproxy.hcl:142-144`) still carries `http_auth`.
7. Every `deployments/infrastructure/services.tf` anchor re-read fresh and re-cited (the file has
   grown further since the verdict was written — the haproxy `nomad_job`
   resource is now at `:340-348`, not `:318-326`; the nats firewall rule is
   at `:275-284`, not `:266-275`).
8. Risk correctly names `ubuntu`, not firebat, as Grafana's host — and,
   since Homepage's resolved placement (Q3) is also `ubuntu`, the collision
   is real, not hypothetical: Requirement 1 and the Resolved forks Q3 entry
   now name the ports to avoid and a concrete recommended port.
9. **Not asked for, found in this rework: Homepage's placement moves from
   `deployments/infrastructure/` to `deployments/applications/`.** Every
   comparable job (Phoenix, Memex, Bifrost, Hermes, Loki) lives in
   `applications`; `infrastructure` holds core platform services. Code
   surface, Subtickets, and the eval all follow that split. Any host volume
   Homepage needs still lives in `infrastructure` (the established
   cross-root pattern `loki_data`/`memex_data` already use).
10. **Not asked for, found in this rework: Homepage's firewall rule must
    admit oauth2-proxy's host (192.168.2.50) only, never the LAN**, or the
    new job becomes a second, unauthenticated way to reach the landing
    page — the same class of mistake N1's follow-on fixed for Prometheus
    and Loki. Now Requirement 5 and a named Risk.
11. `CLAUDE.md`'s "Key Conventions" section (cited by the pre-rework plan
    for the Vault-secrets rule) no longer exists in this repo's
    `CLAUDE.md` (the file is `aim`-regenerated and was restructured).
    Re-cited to `README.md:36`, which states the same rule today.

`loopctl verify-plan L2-landing-homepage` run clean after these edits.
