---
epic = "landing"
depends_on = ["L1-landing-oauth2-proxy"]
priority = 10
summary = "Build and deploy a custom 'dash' Nomad job as the cluster homepage: config-driven (JSON) service tiles (dashboards row + backend-service connect-info-modal row), live per-service health computed by reusing cli/'s existing judge_all()/join() logic via a path dependency, fronted by L1's already-deployed oauth2-proxy, built and pushed as a container image following the Hermes recipe. Supersedes L2-landing-homepage, which the operator has resolved to drop."
tags = ["dash", "homepage", "nomad", "vault", "cli", "oauth2-proxy"]
---

# Ticket: L3-landing-dash-app

> **Reworked 2026-08-23.** The operator resolved all four forks in the
> original §11 (Open questions). See "Plan rework, 2026-08-23" at the end
> of this file for the changelog, and §11 (now "Resolved forks") for each
> decision. One action from that rework — dropping
> `L2-landing-homepage` in the ledger — has since been **executed**:
> `loopctl ledger` shows `L2-landing-homepage: dropped` with the reason
> text this plan recommended. See §11 Q1 and the closing changelog for
> the history.
>
> **Plan-reviewed 2026-08-23** (`pass-with-required-fixes`, see
> `.loop/verdicts/L3-landing-dash-app.plan-validator.md`). All 17 of the
> plan's original numbered premises held; three narrow corrections were
> applied and are folded into the text below: the `rebuild_dash` recipe
> needs an explicit repo-root `cd` because `just` pins a recipe's cwd to
> its own justfile's directory (Requirement 5, §7); the `addopts`
> citation in §6 pointed at the wrong line range (now
> `cli/pyproject.toml:41-44`); and this note itself, since the plan
> previously described the L2 drop as not yet executed when by review
> time it already had been.

## 1. Title

Build and deploy a custom-written "dash" app as the cluster homepage: a
config-driven tile grid (Dashboards row: services with a browsable UI;
Backend services row: connect-info modals, no UI) with live per-tile status
computed by reusing `cli`'s existing, tested Nomad/Consul/HAProxy join logic,
served from a new Nomad job that L1's already-deployed oauth2-proxy fronts,
built and pushed as a container image the same way Hermes is.

## 2. Size / Effort

**L (large).** Not a config edit to an existing job — this is a new
container image with its own backend and frontend, a new Nomad job, a new
Vault/Nomad credential (there is no existing minimal read-only grant for a
machine to call `/v1/jobs/statuses` and `/v1/nodes`, see §4), a new build
pipeline, and one live edit to L1's shared oauth2-proxy upstream. Drivers:

- New Python HTTP backend (tests, mypy `--strict`, ruff — all real gates,
  §8) in its own standalone project directory, depending on `cli` as a
  `uv` path dependency to import its health/join modules rather than
  reimplementing them (Requirement 2, §11 Q3, resolved).
- Net-new Terraform: a Nomad ACL policy, a Vault `nomad` secrets-engine
  role, a Vault policy, and a dedicated `vault_jwt_auth_backend_role` (§4,
  §7) — nothing this narrow exists on this cluster today.
- The Docker build context must reach both `cli/` and the new app's own
  directory, so it cannot be the literal single-directory context the
  Hermes recipe uses (§11 Q3, resolved: repo root).
- Supersedes `L2-landing-homepage` (blocked, not done), which used a
  different design (gethomepage, third-party) that does not have a
  connect-info-modal row or a config-driven tile file and is not built on
  `cli`'s status logic. Operator resolved 2026-08-23 to drop it (§11 Q1).

## 3. Triggered by

Operator request: a "localstack homepage" ("dash", matching the existing
HAProxy route) hosted on Nomad. A design mockup exists as an Artifact (not
in this repo, confirmed absent — `find`/`grep` for a matching asset across
the checkout returns nothing, P14) specifying two tile rows: Dashboards
(vault, nomad, consul, minio, grafana, phoenix, bifrost — clickable, opens
in a new tab) and Backend services (postgres, nats, redis, hermes, memex —
click opens a modal: protocol, host:port, auth method, example command).

## 4. Context

- **L1 is `done` and already routes and gates `dash`.** HAProxy's `dash`
  ACL/backend (`deployments/infrastructure/services/haproxy.hcl:107,118,155-156`)
  sends `dash.lab.orangecluster.nl` to oauth2-proxy on
  `radxa-dragon-q6a:4180`. oauth2-proxy is live, OIDC-gated against Vault's
  `lab` provider with a flat `assignments = ["allow_all"]` client
  (`deployments/infrastructure/oidc.tf:152-186`, esp. `:176`) — **no new
  Vault OIDC client or group is needed.** oauth2-proxy's upstream is a
  deliberate placeholder:
  `deployments/infrastructure/services/oauth2-proxy.hcl:54`,
  `OAUTH2_PROXY_UPSTREAMS="static://200"`. This ticket's only edit at that
  layer is retargeting that one value (Requirement 4).
- **`L2-landing-homepage` occupied this same route and is superseded.**
  Ledger: `stage: "blocked"`, `blocker.code: "eval-missing"`, zero
  commits (`commit_sha: null`, `attempts: 0`) — nothing built to
  preserve. Its design is gethomepage (a third-party app), config in
  gethomepage's own YAML schema, and live status via gethomepage's
  built-in `siteMonitor` widgets for five services — no backend-service
  connect-info modal exists in that design, and nothing in it reuses
  `cli`'s health/join logic. Both tickets retarget the same live file
  (`oauth2-proxy.hcl:54`), so only one design can occupy the route.
  **Operator resolved 2026-08-23: drop L2, this ticket supersedes it**
  (§11 Q1). The ledger action itself is recorded, not executed, by this
  planning pass — see the closing changelog.
- **The health/status logic this ticket must reuse already exists, is
  tested, and is pure.** `cli/src/localstack_cli/api/health.py:101-105`
  (`judge_all`) computes HEALTHY/DEGRADED/STOPPED/UNKNOWN per Nomad job
  from one `/v1/jobs/statuses` call plus node count.
  `cli/src/localstack_cli/api/services.py:91-199` (`join`) ties HAProxy
  routes + Nomad jobs + Consul checks into one row per service, honestly
  reporting "no check" rather than guessing health. Both are covered by
  the `^cli/` pytest gate today. `cli/src/localstack_cli/commands/service.py:79-102`
  (`_collect`) is the worked example of calling all three sources and
  joining them — the shape this ticket's status endpoint should copy.
  **Not the entrypoint to call, though** — see the next bullet and §11
  Q3.
- **The CLI's own command layer cannot be shelled out to from a Nomad
  job — it hard-requires a human login session.**
  `cli/src/localstack_cli/commands/_common.py:26-34`
  (`require_session`) loads a session file written by `localstack login`
  (interactive Vault OIDC) and raises `"not logged in. Run
  \`localstack login\`."` when none exists; there is no environment-token
  or machine-credential fallback anywhere in that function. `cli/src/localstack_cli/commands/service.py:40-42`
  calls `require_session()` before doing anything else. This settles §11
  Q3's subprocess-vs-import fork (§11): a Nomad job cannot run `localstack
  service --json` headlessly without first solving session provisioning
  for a machine, which is strictly more work than importing the
  session-independent `api/` functions directly.
- **No existing credential is both machine-usable and read-only-scoped for
  this.** The CLI's own read commands broker `nomad/creds/manage`
  (`cli/src/localstack_cli/auth/broker.py:34,153,166`,
  `cli/src/localstack_cli/commands/service.py:41-42`) — a full
  **management**-type Nomad token
  (`deployments/infrastructure/nomad_oidc.tf:74-79`), obtainable only
  through an interactive human Vault login via the CLI's broker
  (D10, `done`), never by a Nomad job's own Workload Identity. The other
  machine-mintable Nomad role, `nomad/creds/deploy`
  (`deployments/infrastructure/nomad_deploy_role.tf:21-50`), grants
  `submit-job`, `read-job`, and `host-volume-*` — write capability this
  read-only backend must not hold, and it grants no `node:read` or
  `list-jobs` either. The default per-job Vault grant every workload gets,
  `nomad-workloads`, is KV-only:
  `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`
  grants `secret/data/<ns>/<job_id>/*` read and nothing about
  `nomad/creds/*` or Nomad's own API. **A new, narrower grant does not
  exist yet and is part of this ticket** (Requirement 3, §7).
- **The repo's own pattern for "a workload needs more than
  `nomad-workloads`" is a dedicated, per-consumer
  `vault_jwt_auth_backend_role` whose `token_policies` is additive.**
  `deployments/infrastructure/acme.tf:66-90` (esp. `:87`,
  `token_policies = ["nomad-workloads", vault_policy.acme_tls_write.name]`)
  and `deployments/infrastructure/redis_secrets_engine.tf:159-181` (one
  role per consumer, "the per-job cost", its own comment's words) are the
  two worked examples. This ticket's new role follows the same shape.
- **Consul needs no new credential at all.** `cli/src/localstack_cli/api/consul.py:1-16,65-83`
  — both `list_checks` and `list_services` send no token; the agent's own
  `tokens.default` config authenticates a tokenless call even though
  `default_policy = "deny"` (documented in the module's own docstring).
  No firewall rule in `deployments/infrastructure/services.tf` restricts
  Consul's `8500` below LAN-wide reachability today.
- **Tile config format: JSON, resolved.** `deployments/applications/services.tf:171-224`
  — memex's auth config lives in `services/memex/auth_keys.json` and
  `services/memex/auth_oidc.json`, read via `file()`, round-tripped
  through `jsondecode`/`jsonencode` at `terraform plan` time (a JSON
  syntax error fails the plan, not the job), then baked into the job via
  `templatefile(...)`. Grafana's dashboards are JSON/YAML files read the
  same way (`deployments/infrastructure/services.tf:367-388`). **Every
  in-repo TOML file is tool config** (`aim.toml`, `cli/pyproject.toml`,
  `.loop/plans/*.md` front matter) — none is a Nomad job's own
  service/tile list, and `cli` itself declares `pyyaml` but no TOML
  reader (`cli/pyproject.toml:5-13`; no `tomllib`/`tomli` usage anywhere
  under `cli/src`, verified by grep). Operator adopted this on
  2026-08-23 (§11 Q2, resolved).
- **`cli`'s own pre-commit gates are scoped to `^cli/` only, and the new
  app's own directory needs its own equivalent hooks.**
  `.pre-commit-config.yaml` — `ruff`, `ruff-format`, `mypy` (`--strict`),
  and `pytest` all carry `files: '^cli/'`. Since the operator resolved
  Q3 to a standalone app in its own directory rather than a `cli/`
  subpackage, this backend needs its **own** four equivalent hooks added
  (§7), or it ships with none of them — nothing in
  `deployments/applications/` is lint/type/test-gated today otherwise.
- **`cli/` is a standalone `uv` project, not a workspace member, which is
  what makes it a path dependency rather than a shared-lockfile sibling.**
  There is no root-level `pyproject.toml` and no `[tool.uv.workspace]`
  anywhere in the repo (checked); `cli/pyproject.toml` + `cli/uv.lock`
  are self-contained. `uv` (pinned in this devcontainer at `0.11.16`)
  resolves a plain relative-path dependency (`uv add <path>`) without
  needing a workspace, which is the mechanism the new app's
  `pyproject.toml` uses to depend on `cli` (Requirement 2, §7).
- **`cli/pyproject.toml` has no HTTP server dependency**, and this
  ticket does not add one there — the new dependency belongs to the new
  app's own `pyproject.toml` (§7), added with `uv add`
  (`.claude/rules/uv-installer.md`).
- **Hermes is the only locally-built, pushed image in this repo.**
  `deployments/applications/justfile:33-43` (`rebuild_hermes`) is the sole
  `rebuild_*` recipe: `docker login ghcr.io` with
  `GITHUB_WRITE_PAT`/`GITHUB_USER` from `.devcontainer/.env`
  (`justfile:3`), then `docker build --pull --platform linux/arm64 -t
  ghcr.io/jasperhg90/<name>:<tag> -f services/<name>/Dockerfile
  services/<name>`, then push, with `<tag>` read out of `services.tf`'s
  `hermes_version` var (`:136`) by `grep`/`sed`, so the Dockerfile and
  Terraform never drift. Bifrost pulls a vendor image
  (`deployments/applications/services/bifrost.hcl:40`); Memex's image is
  built by an out-of-repo pipeline
  (`deployments/applications/services/memex.hcl:38,92`, no matching
  justfile recipe). Neither hermes nor memex is a precedent for "a
  standalone local Python project inside `services/<name>/`" — hermes's
  subdirectory holds only a Dockerfile + non-code assets (no local
  Python source: the image installs pre-released memex wheels), and
  memex's own Python source lives in a wholly separate repository. This
  ticket's `services/dash/app/` is new structure, justified in §11 Q3.
- **Node/port landscape.** `radxa-dragon-q6a` (192.168.2.50) already runs
  oauth2-proxy (4180, `oauth2-proxy.hcl:35`), Hermes (8642), Bifrost
  (8080), Redis (6379), NATS (4222 client / 8222 monitor,
  `deployments/infrastructure/services/nats.hcl:8-9`), and the
  Postgres/MinIO backup jobs. `ubuntu` (192.168.2.47) runs Grafana (3000),
  Loki (3100/9095), Prometheus (9090) — the port collisions L2's own
  rework already found and recorded
  (`.loop/plans/L2-landing-homepage.md:103-108,431-436`, still current).
  Operator confirmed colocating `dash` on `radxa-dragon-q6a` (§11 Q4).
- **`deployments/applications/` is the correct root, on precedent
  L2 already established for this exact route and re-derived here.**
  Application-facing, cluster-served jobs (Phoenix, Memex, Hermes,
  Bifrost, Loki) live in `applications`; core platform services
  (HAProxy, oauth2-proxy, Vault-adjacent Terraform) live in
  `infrastructure`. `.loop/plans/L2-landing-homepage.md:523-532` (P9) is
  the citation; the applications root already reads a client created in
  `infrastructure` by static name with no remote-state link
  (`deployments/applications/services.tf:37-39`), so cross-root
  reachability is not gated by which root owns the resource.
- **The connect-info modal must never render live credential material.**
  This repo already treats that as a hard line for a comparable
  read-surface: `cli/src/localstack_cli/commands/secret.py:10-11` — "No
  value is ever read [...] telling someone their secret does not exist
  when they simply cannot see it sends them to write one that is already
  there" — `localstack secret <service>` reports existence, never value.
  Backend-row targets today: Postgres `192.168.2.30:5432`
  (`deployments/infrastructure/services/postgres.hcl:14-15`, credential
  in Vault KV2, `postgres.hcl:142`; still static creds — R3's move to
  Vault dynamic DB creds is `blocked`); NATS `192.168.2.50:4222`
  (client)/`:8222` (monitor, `nats.hcl:8-9`); Redis
  `192.168.2.50:6379`; Hermes `192.168.2.50:8642`; Memex
  `192.168.2.46:8000`.

## 5. Non-goals / out of scope

- Redesigning the mockup's UI/UX. It is already decided; this ticket hosts
  and data-livens it, not visual design.
- Implementing L2/gethomepage. Superseded — see §4 and §11 Q1.
- Executing the ledger action that marks L2 dropped. This ticket
  documents and recommends it; running `loopctl drop` is outside this
  planning pass's own scope (only-write-is-the-ticket-file boundary) —
  see the closing changelog for the exact command.
- Any `haproxy.hcl` edit. The `dash` route already exists and is correct
  as-is (§4).
- Any new Vault OIDC client, group, or assignment. oauth2-proxy's
  `allow_all` client already covers `dash` end to end.
- Fixing the first-SSO-attempt quirk. `docs/vault-human-auth.md:328-335`
  documents it for Nomad's own sign-in button (observed, not
  root-caused); note it in this ticket's docs, do not attempt a fix.
- Per-tile or per-user RBAC. Flat access, matching oauth2-proxy's
  `allow_all` posture.
- Auto-discovering tiles from Consul/Nomad. The tile *list* (which
  services appear, in which row, with which icon/description) stays
  config-driven; only each configured tile's *health* is computed live.
- Rendering any live credential value (password, token, API key) in the
  connect-info modal. Auth method and an example command only (§4).
- Moving Postgres, Redis, or NATS to a different credential model. Out of
  scope for R3/R7/R8/R2, not this ticket.
- Packaging or publishing `cli` as an installable artifact on a registry.
  The new app depends on it via a local `uv` path dependency (§4, §7),
  not a released wheel.
- Turning `cli/` into a `uv` workspace. A plain path dependency is
  sufficient (§4); restructuring `cli/`'s own project shape is out of
  scope.

## 6. Requirements & restrictions

Must achieve:

1. **Config-driven tile list, in JSON.** One file names every tile: name,
   icon, color, description, category (`dashboard` | `backend`), and
   either a target URL (dashboard row) or connection info (protocol,
   host, port, auth method — never a secret value, §4) for the backend
   row. Format resolved to JSON (§4, §11 Q2) — the one in-repo precedent
   for "a job's own structured config" (memex's `services/memex/*.json`).
2. **Live status, not hardcoded.** Every tile's health comes from
   `cli.api.health.judge_all()` and `cli.api.services.join()`
   (`cli/src/localstack_cli/api/health.py:101-105`,
   `cli/src/localstack_cli/api/services.py:91-199`), imported and called
   directly — not reimplemented in JS, not duplicated in a second Python
   copy, and not reached by shelling out to the `localstack` CLI (§4
   explains why that path is closed).
3. **A minimal, read-only Vault/Nomad credential for the status backend.**
   Namespace-scoped `read-job` and `list-jobs` capabilities plus
   `node { policy = "read" }`, and nothing else — no `submit-job`, no
   `host-volume-*`, no management type. Modeled on
   `nomad_deploy_role.tf:21-61`'s shape (a dedicated `nomad_acl_policy` +
   `vault_nomad_secret_role` of `type = "client"`) and
   `acme.tf:66-90`/`redis_secrets_engine.tf:159-181`'s shape (a dedicated,
   additive `vault_jwt_auth_backend_role` so the job keeps its
   `nomad-workloads` KV read too). Do not attach `developer` or
   `nomad/creds/manage` — both are broader than this backend needs (§4).
4. **Point oauth2-proxy's upstream at the new app.**
   `deployments/infrastructure/services/oauth2-proxy.hcl:54` —
   `OAUTH2_PROXY_UPSTREAMS` changes from `static://200` to the dash job's
   real address: a loopback address, since the job is colocated with
   oauth2-proxy on `radxa-dragon-q6a` (§4, §11 Q4, resolved). This is the
   ticket's only edit to L1's already-deployed files, mirroring the
   handoff L1's own plan text anticipated for a homepage successor
   (`.loop/plans/L1-landing-oauth2-proxy.md:529-553`).
5. **Build and push the image the way Hermes is built, with one
   necessary deviation.** Its own
   `deployments/applications/services/dash/Dockerfile`, its own
   `rebuild_dash` justfile recipe copying `rebuild_hermes`'s shape
   (`deployments/applications/justfile:33-43`), and its own
   `dash_version` var threaded into `deployments/applications/services.tf`,
   read by the recipe the same way `hermes_version` is
   (`justfile:38`, `grep ... services.tf`). The one deviation: the build
   **context** is the repo root, not `services/dash/` alone, because the
   image needs both `cli/` and `services/dash/app/` (§4, §11 Q3,
   resolved). **A second, related deviation the recipe itself must
   handle:** `just` pins a recipe's working directory to its own
   justfile's directory (`deployments/applications/`), never the repo
   root, so `rebuild_dash` cannot copy `rebuild_hermes`'s body verbatim
   — it needs an explicit `cd "$(git rev-parse --show-toplevel)"` (or
   equivalent repo-root-relative pathing) before the `docker build`
   call, or the widened context silently resolves to the wrong
   directory and `COPY cli/` fails (plan-validator finding P18,
   demonstrated live against a scratch justfile).
6. **No `haproxy.hcl` edit, no new Vault OIDC resource.** Both already
   exist and are correct (§4).
7. **The connect-info modal shows method, never material.** No password,
   token, or API key value reaches the frontend. Follow
   `cli/src/localstack_cli/commands/secret.py`'s existence-not-value
   convention (§4): an "example command" is something like
   `localstack secret <job>` or a `psql`/`nats`/`redis-cli` invocation with
   a placeholder, never a live credential.
8. **The new app carries its own lint/type/test gates, equivalent to
   `cli/`'s.** Since it lives in its own directory rather than inside
   `cli/` (§11 Q3), it inherits none of `.pre-commit-config.yaml`'s four
   `^cli/`-scoped Python hooks by default; this ticket adds matching
   hooks scoped to the new directory (§7).

Restrictions the repo enforces (each cited):

- Simplicity / surgical changes (`CLAUDE.md` §§1-3): reuse
  `cli.api.health`/`cli.api.services` rather than reimplementing; touch
  `oauth2-proxy.hcl:54` and nothing else in L1's files.
- New Python dependencies via `uv add`, never `uv pip`
  (`.claude/rules/uv-installer.md`) — this covers both the new app's HTTP
  dependency and its path dependency on `cli`.
- Every code change ships a test; a bug fix reproduces first
  (`.claude/rules/python-testing.md`). Cluster-touching tests carry a
  `cluster` marker and stay excluded from the default run, mirroring
  `cli/pyproject.toml:41-44`'s `addopts = "-m 'not cluster'"` — the new
  app's own `pyproject.toml` needs the same marker/addopts pair (§7).
- Secrets live in Vault KV2, never hardcoded (`README.md:36`); any
  connect-info value the modal needs comes from a `vault {}` / `template`
  stanza, and per Requirement 7 the value itself never leaves the backend.
- Nomad HCL formatting (`nomad-fmt` hook) and Terraform
  formatting/validation for both roots (`terraform-fmt`,
  `terraform-validate` via `scripts/tf_validate.sh`) — one `just
  pre_commit` run covers both roots' edits.
- Pin the container image tag; no `:latest` (repo convention, e.g.
  `deployments/applications/services/bifrost.hcl:40`).
- Adversarial review before done (`.claude/rules/adversarial-reviews.md`).
  Hand the reviewer: no `haproxy.hcl` diff; the new Nomad ACL
  policy grants exactly `read-job`/`list-jobs`/`node:read` and nothing
  more; no credential value reaches the frontend; the oauth2-proxy
  upstream edit is the only change to L1's files; the new app's
  pre-commit hooks actually run (not silently skipped for lack of a
  matching `files:` pattern).

## 7. Code surface

- **CREATE** `deployments/applications/services/dash.hcl` — new Nomad job,
  driver `podman`, pinned arm64 image, constrained to `radxa-dragon-q6a`
  (§4, §11 Q4), static port (free port TBD at implementation time, §9),
  `vault { role = "dash" }` (Requirement 3), `template` stanza
  rendering the tile config file into `local/tiles.json` and mounting it
  read-only (model: `bifrost.hcl:39-50` `config.volumes` shape; memex's
  `services/memex/*.json` round-trip pattern for the Terraform side,
  `deployments/applications/services.tf:171-224`), a `service` + health
  `check` block. Models: `deployments/applications/services/hermes.hcl`
  (applications-root job on `radxa-dragon-q6a`),
  `deployments/applications/services/bifrost.hcl:1-58` (podman/vault/template
  shape).
- **CREATE** `deployments/applications/services/dash/app/` — standalone
  Python project (own `pyproject.toml`, `src/`, `tests/`), mirroring
  `cli/`'s own self-contained-uv-project shape rather than `cli/`'s
  internal package layout (§4, §11 Q3, resolved: own directory, not a
  `cli/` subpackage). Its `pyproject.toml` adds `localstack-cli` as a
  `uv` **path dependency** (`uv add --editable <relative-path-to-cli>`,
  e.g. `../../../../../cli` from this directory), then imports
  `localstack_cli.api.health.judge_all` and
  `localstack_cli.api.services.join` directly — the session-independent
  `api/` functions, never `cli.commands.service`'s entrypoint (§4). Also
  contains: the tile-config loader (Requirement 1) and the HTTP app
  (status endpoint + static frontend serving), with one new HTTP
  dependency added via `uv add`.
- **CREATE** `deployments/applications/services/dash/app/tests/...`
  (mirrors the new project's own source tree,
  `.claude/rules/python-testing.md`) — unit tests for the tile-config
  loader and the status-join wiring; a `cluster`-marked test for the live
  endpoint, excluded from the default run.
- **CREATE** `deployments/applications/services/dash/Dockerfile` —
  builds the backend + static frontend. Build context is the **repo
  root**, invoked from the repo root itself
  (`docker build -f deployments/applications/services/dash/Dockerfile .`
  run with cwd at the repo root — **not** the literal command form as
  written inside a `just` recipe, since `just` pins a recipe's cwd to
  its own justfile's directory; see Requirement 5's added note and
  plan-validator finding P18), so it can `COPY cli/` (the path
  dependency's target) and `COPY
  deployments/applications/services/dash/app/` and `.../frontend/`
  (Requirement 5, §11 Q3). This is the one deviation from
  `services/hermes/Dockerfile`'s literal single-directory-context shape;
  the model for the build steps otherwise is that same Dockerfile.
- **CREATE** `deployments/applications/services/dash/tiles.json` — the
  tile list: name, icon, color, description, category,
  target/connect-info per tile (Requirement 1, JSON per §4/§11 Q2).
- **EDIT** `.pre-commit-config.yaml` — add four new hooks
  (`ruff`, `ruff-format`, `mypy --strict`, `pytest`) scoped to
  `files: '^deployments/applications/services/dash/app/'`, mirroring the
  existing four `^cli/`-scoped hooks line for line (entry, `uv run
  --project deployments/applications/services/dash/app ...`), so the new
  project is gated the same way `cli/` is (Requirement 8, §11 Q3).
- **EDIT** `deployments/applications/services.tf` — add
  `resource "nomad_job" "dash"` via `templatefile(...)` (model:
  `nomad_job "hermes"`, `:130-161`, and `nomad_job "loki"`, `:164-169`);
  add a `dash` entry to `local.firewall_rules` (`:42-95`) admitting
  oauth2-proxy's host only (model: the single-caller shape at
  `deployments/infrastructure/services.tf:285-292`, the `oauth2_proxy`
  rule); add `dash_version` inline the way `hermes_version` is
  (`:136`).
- **CREATE** `deployments/infrastructure/nomad_dash_read_role.tf` (name
  indicative) — Requirement 3's new grant: `nomad_acl_policy "dash_read"`
  (model `nomad_deploy_role.tf:21-50`, but `read-job`/`list-jobs`/
  `node { policy = "read" }` only); `vault_nomad_secret_role "dash_read"`
  (`type = "client"`, model `nomad_deploy_role.tf:56-61`); a `vault_policy`
  granting `read` on `nomad/creds/dash_read` (model
  `developer_group.tf:161`'s path shape, scoped to this one role only);
  `vault_jwt_auth_backend_role "dash"` bound to `nomad_job_id = "dash"`,
  `token_policies = ["nomad-workloads", <the new vault_policy>]` (model
  `acme.tf:66-90`).
- **EDIT** `deployments/infrastructure/services/oauth2-proxy.hcl:54` —
  `OAUTH2_PROXY_UPSTREAMS="static://200"` → the dash job's loopback
  address (Requirement 4).
- **EDIT** `deployments/infrastructure/services.tf` (the
  `nomad_job "oauth2_proxy"` resource, currently `:400-409` — re-read the
  live line numbers before editing, this file has grown across other
  tickets) — add the upstream value to the `templatefile(...)` vars map.
- **EDIT** `deployments/applications/justfile` — add `rebuild_dash`
  (model `:33-43`, `rebuild_hermes`), reading `dash_version` out of
  `services.tf` the same way, with the widened build context (Requirement
  5).
- Read-only anchors to consume, not edit: `haproxy.hcl:107,118,155-156`
  (the existing `dash` route); `oidc.tf:152-186` (oauth2-proxy's existing
  `allow_all` client); `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`
  (what the default grant does NOT cover); `cli/src/localstack_cli/commands/secret.py`
  (existence-not-value convention for Requirement 7);
  `cli/src/localstack_cli/commands/_common.py:26-34`
  (`require_session`, decisive evidence for Requirement 2's
  import-not-subprocess call); `.loop/plans/L2-landing-homepage.md`
  (the design this ticket supersedes, §11 Q1).

## 8. Tests & validation gates

- **Repo gate:** `just pre_commit` (`pre-commit run --all-files`,
  `justfile:17-19`). Covers: `nomad-fmt` on `dash.hcl`;
  `terraform-fmt`/`terraform-validate` (`scripts/tf_validate.sh`) on both
  roots' new/edited `.tf`; the four existing `ruff`/`ruff-format`/
  `mypy --strict`/`pytest` hooks scoped to `^cli/` (unaffected — this
  ticket does not edit `cli/`); the four **new**
  `ruff`/`ruff-format`/`mypy --strict`/`pytest` hooks scoped to
  `^deployments/applications/services/dash/app/` (§7, Requirement 8).
- **Unit tests (new, under `deployments/applications/services/dash/app/tests/`):**
  the tile-config loader against a fixture file (valid + malformed
  cases); the status-join wiring against fake `health`/`services`
  inputs, mirroring `health.py`'s own "pure functions, rule table as a
  unit test" approach (`health.py:1-5`). No network, no `cluster` marker.
- **`cluster`-marked test:** one test hitting the live status endpoint
  end to end (needs the deployed job), excluded from the default run,
  run on purpose with `-m cluster`.
- **`terraform -chdir=deployments/infrastructure plan`** must show the
  new Nomad ACL policy, Vault role, Vault policy, and JWT auth role
  added, and the oauth2-proxy job updated in place (upstream value
  changed), destroying nothing.
- **`terraform -chdir=deployments/applications plan`** must show the new
  `dash` job and firewall rule added, destroying nothing.
- **Adversarial review** (`.claude/rules/adversarial-reviews.md`): confirm
  no `haproxy.hcl` diff; the new Nomad ACL policy's `rules_hcl` grants
  exactly `read-job`/`list-jobs`/node-read and nothing else (diff it
  against `nomad_deploy_role.tf`'s policy to show the narrowing); the
  connect-info modal's rendered HTML/JSON carries no credential value for
  any backend-row tile; the image is pinned, not `:latest`; the
  oauth2-proxy upstream edit is the only change to L1's files; the new
  `.pre-commit-config.yaml` hooks actually fire on a change under
  `services/dash/app/`.
- **Eval marker (loop-harness acceptance):** `.loop/evals/L3-landing-dash-app.md`,
  13 rows (12 repo-checkable + 1 `pending-operator` live-endpoint row),
  signed off 2026-08-23. `loopctl eval L3-landing-dash-app` reports `valid`;
  `loopctl verify-eval-substance L3-landing-dash-app` reports `valid`.

## 9. Risk assessment

- **Blast radius:** two surfaces, like L2's. (a) The new job, image,
  Terraform grant, and firewall rule are additive and isolated. (b) The
  `oauth2-proxy.hcl:54` edit touches the live auth gate for the whole
  `dash` route — a malformed upstream value breaks login for the landing
  page specifically (not any other service, since oauth2-proxy gates only
  `dash`).
- **Getting the new Nomad ACL grant wrong is a two-sided risk.** Too
  narrow: the status backend 403s and every tile reads UNKNOWN — a safe,
  visible failure. Too wide (e.g. attaching `developer` or
  `nomad/creds/manage` "to unblock it quickly," the exact shortcut §4 and
  Requirement 3 warn against): a status-reading job holds Nomad management
  or write capability it never needs, the same class of over-grant
  `cluster-roles.md` calls out as "not a containment boundary."
- **L2 was resolved to drop, and the ledger now reflects it.**
  `loopctl drop L2-landing-homepage "<reason>"` has run (§4, §11 Q1, and
  the closing changelog); `loopctl ledger` shows `L2-landing-homepage:
  dropped` with that reason recorded. The risk this bullet originally
  flagged — a decided-but-unrecorded gap where an operator could still
  sign L2's pending eval — no longer applies.
- **The connect-info modal is the one place a careless implementation
  leaks a live secret to a browser.** Requirement 7 and the adversarial
  review step both exist because of this; treat any code path that reads
  a KV2 *value* (not just checks existence) for the modal as a signal
  something has gone wrong.
- **The new app depends on the whole `localstack-cli` package**,
  including dependencies it does not itself need (`textual`, `rich`,
  `click`, `typer` — the TUI/CLI surface, not just `api/`). This is an
  image-size and dependency-surface cost, not a correctness risk;
  `cli` has no narrower "api-only" installable target today, so this is
  what "depend on `cli` directly" concretely costs. Worth a follow-up
  ticket if image size becomes a real constraint; not a blocker here.
- **Reversibility:** high for the additive Terraform/Nomad pieces
  (destroy the job, policy, roles). The oauth2-proxy upstream revert is a
  one-line diff back to `static://200`.
- **Node/port collision**, same class L2 already hit on `ubuntu`
  (§4) — avoided by colocating with oauth2-proxy on `radxa-dragon-q6a`
  (§11 Q4, resolved), but the exact port is not yet confirmed free
  (existing occupants there: 8642, 8080, 4180, 6379, 4222/8222).

## 10. Subtickets

Ordered, dependency-aware.

1. **Ledger housekeeping: mark `L2-landing-homepage` dropped. DONE.**
   `loopctl drop L2-landing-homepage "<reason>"` has already run (§5 and
   the closing changelog record why this planning pass itself did not
   run it, and that it was run afterward, outside the planning pass);
   `loopctl ledger` confirms `L2-landing-homepage: dropped`. No longer
   blocking for step 9. Depends on: nothing.
2. **Scaffold `deployments/applications/services/dash/app/`**: its own
   `pyproject.toml`, `uv add --editable` the path dependency on `cli/`,
   confirm `import localstack_cli.api.health` / `.api.services` resolves
   under `uv run --project`. Depends on: nothing.
3. **Add the new project's pre-commit hooks** to
   `.pre-commit-config.yaml` (Requirement 8, §7). Depends on: 2.
4. **Tile-config schema + loader, with unit tests.** Pure function, no
   HTTP yet. Depends on: 2.
5. **Status-join wiring**: call `health.judge_all()` +
   `services.join()`, matching one tile's config entry to its computed
   health. Unit tests against fakes. Depends on: 4.
6. **Provision the minimal read-only Vault/Nomad grant** (Requirement 3,
   §7's new `.tf` file) in `deployments/infrastructure/`. Depends on:
   nothing (parallel to 2-5).
7. **HTTP app**: serves the static frontend + status endpoint from steps
   4-5; new dependency via `uv add`. Depends on: 5.
8. **Dockerfile (repo-root context) + `rebuild_dash` justfile recipe +
   `dash_version` var.** Depends on: 7.
9. **Nomad job (`dash.hcl`) + `services.tf` registration + firewall
   rule.** Depends on: 6, 8.
10. **Point oauth2-proxy at the new job** (`oauth2-proxy.hcl:54` +
    `services.tf` var). Depends on: 1, 9.
11. **Docs (sign-in note, first-login quirk pointer, "add a tile"
    how-to) + eval + adversarial review.** Depends on: 1-10.

## 11. Resolved forks (operator, 2026-08-23)

All four forks below were open when this ticket was first authored. The
operator resolved all four on 2026-08-23; each entry keeps the original
question and options for the record, per this repo's own convention
(`.loop/plans/R4-rollout-phoenix-oauth2-proxy.md`'s "Operator fork
resolutions" style), with the adopted answer stated first.

- **Q1 — RESOLVED: drop `L2-landing-homepage`.** It occupied this same
  route with a design (gethomepage) that cannot produce a connect-info
  modal or config-driven tiles, and has zero commits — nothing built to
  preserve. This ticket supersedes it (§4). *Execution note:* the ledger
  action was NOT run by the planning pass that first wrote this
  resolution (see the closing changelog for why), but has since been run
  outside that pass — `loopctl ledger` shows `L2-landing-homepage:
  dropped`.
- **Q2 — RESOLVED: JSON**, not the operator's originally suggested TOML.
  It is the only format this repo already uses for "a job's own
  structured, hand-edited config baked into a `templatefile`" (memex's
  `services/memex/*.json`, §4), it round-trips through
  `jsondecode`/`jsonencode` so a syntax error fails `terraform plan`
  rather than reaching the job, and `cli`'s own dependencies carry no
  TOML reader today (`pyyaml` only) while `json` needs nothing added.
- **Q3 — RESOLVED: standalone app, own directory** —
  `deployments/applications/services/dash/app/`, mirroring hermes's
  shape of "the job's own subdirectory holds its build content," **not**
  a `cli/` subpackage. This reopened the concrete question of how the
  standalone app reuses `judge_all()`/`join()` without a shared package
  boundary. Two options were live:
  - **(a) — ADOPTED.** The app adds `cli` as a real `uv` path
    dependency (`uv add --editable <path-to-cli>`) and imports
    `localstack_cli.api.health`/`.api.services` directly.
  - **(b) — REJECTED.** Shell out to the `localstack` CLI as a
    subprocess and parse its `--json` output.
    `cli/src/localstack_cli/commands/_common.py:26-34`
    (`require_session`) settles this: every read command, including
    `service --json`, hard-requires a session file written by
    `localstack login`'s interactive Vault OIDC flow, with no
    environment-token or machine-credential fallback in that function.
    A Nomad job has no browser and no interactive login step, so this
    route would need to *first* solve "how does a machine obtain and
    refresh a CLI session file" — strictly more scope than importing the
    session-independent `api/` functions directly, and it does not avoid
    Requirement 3's new Vault/Nomad grant either way, since the session
    itself still needs *some* credential behind it.
  Cost of (a), named rather than hidden: the app depends on the whole
  `localstack-cli` package, including `textual`/`rich`/`click`/`typer`
  it does not use (§9) — no narrower "api-only" install target exists
  in this repo today. Consequence of "own directory": the app inherits
  none of `cli/`'s pre-commit gates by default, so this ticket adds four
  matching hooks scoped to its own path (§7, Requirement 8), and the
  Docker build context widens to the repo root regardless of (a) vs (b),
  since either the path dependency or a subprocess `localstack` install
  would need `cli/` inside the build context.
- **Q4 — RESOLVED: colocate on `radxa-dragon-q6a`** with oauth2-proxy, as
  originally recommended. The upstream is therefore a loopback address
  and needs no LAN-facing firewall change beyond the existing
  single-caller shape (§7). A free port there is still to be confirmed
  at implementation time (§9) — the colocation choice is settled, the
  exact port number is not.

## Premises / assumptions

- **P1.** L1 is `done`; oauth2-proxy is live, OIDC-gated, and its
  upstream is a deliberate placeholder waiting for a real app.
  `Evidence:` ledger `L1-landing-oauth2-proxy` stage `done`;
  `oauth2-proxy.hcl:54`.
- **P2.** HAProxy's `dash` route already exists and needs zero edits.
  `Evidence:` `haproxy.hcl:107,118,155-156`.
- **P3.** oauth2-proxy's Vault OIDC client already grants flat
  any-authenticated-user access; no new Vault OIDC client, group, or
  assignment is needed.
  `Evidence:` `oidc.tf:152-186`, esp. `:176` (`assignments =
  ["allow_all"]`).
- **P4.** `L2-landing-homepage` is `blocked`, not `done`, has zero
  commits, and its design (gethomepage) does not implement a
  connect-info-modal row, a config-driven tile file this repo already
  has precedent for, or `cli`-backed live status. The operator resolved
  2026-08-23 to drop it on this basis.
  `Evidence:` ledger `L2-landing-homepage` — `stage: "blocked"`,
  `commit_sha: null`, `attempts: 0`; `.loop/plans/L2-landing-homepage.md`
  §§6-7 (gethomepage-native YAML config, `siteMonitor` widgets, no
  modal concept anywhere in the plan text).
- **P5.** `cli.api.health.judge_all()` and `cli.api.services.join()` are
  real, tested, pure functions already computing exactly the health
  states this ticket needs.
  `Evidence:` `cli/src/localstack_cli/api/health.py:101-105`,
  `cli/src/localstack_cli/api/services.py:91-199`; both under the `^cli/`
  pytest gate (`.pre-commit-config.yaml`); both already consumed by
  `cli/src/localstack_cli/commands/service.py:79-102`, a `done` ticket's
  shipped code (D3, D7, D8, D10 per `git log` on that file).
- **P6.** No existing Vault/Nomad role grants a machine read-only access
  to `/v1/jobs/statuses` and `/v1/nodes`; the two that exist are
  human-only-management (`nomad/creds/manage`) and write-capable-client
  (`nomad/creds/deploy`).
  `Evidence:` `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`
  (KV-only, full text read); `nomad_deploy_role.tf:21-50` (`rules_hcl`
  grants `submit-job`, `host-volume-*`, no `node`/`list-jobs`);
  `nomad_oidc.tf:74-79` (`type = "management"`); `cli/src/localstack_cli/auth/broker.py:34,153,166`
  and `cli/src/localstack_cli/commands/service.py:41-42` (`nomad_manage`
  is human-session-only, via the CLI's interactive login broker, D10
  `done`).
- **P7.** The repo's established pattern for "a workload needs more than
  the shared `nomad-workloads` grant" is a dedicated, additive
  `vault_jwt_auth_backend_role` per consumer.
  `Evidence:` `acme.tf:66-90` (esp. `:87`); `redis_secrets_engine.tf:159-181`.
- **P8.** Consul reads need no brokered token from any LAN-reachable
  caller; no firewall rule narrows Consul's `8500` below LAN-wide.
  `Evidence:` `cli/src/localstack_cli/api/consul.py:1-16,65-83`; grep of
  `deployments/infrastructure/services.tf`'s `firewall_rules` finds no
  `consul` entry.
- **P9.** No in-repo precedent uses TOML for a job's own structured
  service/tile config; the one real precedent for that shape is JSON.
  `Evidence:` `deployments/applications/services.tf:171-224` (memex's
  `services/memex/*.json`, `jsondecode`/`jsonencode` round-trip);
  `deployments/infrastructure/services.tf:367-388` (Grafana's
  JSON/YAML dashboards); repo-wide `find -iname "*.toml"` returns only
  tool config (`aim.toml`, `cli/pyproject.toml`, `.loop/plans/*.md`
  front matter — checked, none is application/job config); `cli`
  declares `pyyaml` but no TOML reader
  (`cli/pyproject.toml:5-13`; grep for `tomllib`/`tomli`/`import toml`
  under `cli/src` returns nothing).
- **P10.** `cli`'s pre-commit gates (`ruff`, `ruff-format`, `mypy
  --strict`, `pytest`) apply only to files under `^cli/`; nothing outside
  it is lint/type/test-gated by this repo today, so a standalone app
  outside `cli/` needs its own matching hooks to get equivalent coverage.
  `Evidence:` `.pre-commit-config.yaml`, `files: '^cli/'` on all four
  Python hooks.
- **P11.** `deployments/applications/` is the correct root for `dash`,
  on precedent L2 already established and justified for this exact
  route.
  `Evidence:` `.loop/plans/L2-landing-homepage.md:523-532` (P9);
  `deployments/applications/services.tf:37-39` (cross-root client lookup
  by static name, no remote-state link — reachability is not gated by
  Terraform root).
- **P12.** Hermes is the only locally-built-and-pushed image in this
  repo; the exact recipe Requirement 5 must copy has exactly one worked
  example, and neither it nor memex is a precedent for a standalone
  local Python project inside a `services/<name>/` directory.
  `Evidence:` `deployments/applications/justfile:33-43` (`rebuild_hermes`,
  sole `rebuild_*` recipe); `bifrost.hcl:40` (vendor image);
  `memex.hcl:38,92` (image built out-of-repo, no matching recipe);
  hermes's own subdirectory holds a Dockerfile and non-code assets only
  (no local Python source — the image installs pre-released memex
  wheels).
- **P13.** The connect-info modal's security bar ("show existence/method,
  never value") already has a direct precedent in this repo's own CLI
  surface.
  `Evidence:` `cli/src/localstack_cli/commands/secret.py:1-11` — "No
  value is ever read," stated in the module's own docstring as the
  design reason, not an incidental fact.
- **P14.** No design mockup asset is checked into this repository.
  `probe:` `find /home/vscode/workspace -iname "*mockup*" -o -iname
  "*dash*.html" -o -iname "*dash*.png"` (excluding `.git`/`.cache`)
  returns no results, run 2026-08-23.
- **P15 (UNCERTAIN).** Whether the recommended Nomad ACL policy syntax
  (`node { policy = "read" }` alongside a `namespace "default" {
  capabilities = [...] }` block in the same `rules_hcl`) is accepted
  as written by the Nomad version this cluster runs. Every existing
  `rules_hcl` in this repo (`nomad_acl_policy.deploy`) uses only the
  `namespace` block; no in-repo precedent combines it with a `node`
  block. `probe:` not yet run against the live cluster — confirm with
  `nomad acl policy apply` (or `terraform plan`) against a scratch
  policy name before relying on the exact syntax in §7's Terraform.
- **P16.** `cli`'s command layer cannot be driven headlessly; every read
  command requires a session file from an interactive human login, with
  no machine-credential fallback. This is the decisive evidence against
  §11 Q3's subprocess/shell-out option.
  `Evidence:` `cli/src/localstack_cli/commands/_common.py:26-34`
  (`require_session` raises `"not logged in. Run \`localstack
  login\`."` when no session file exists; no env-token branch in the
  function); `cli/src/localstack_cli/commands/service.py:40-42` calls it
  first, before any Nomad/Consul/HAProxy read.
- **P17.** `cli/` is a self-contained `uv` project, not a workspace
  member, so a sibling project reaches it via a plain path dependency.
  `Evidence:` no root-level `pyproject.toml` and no
  `[tool.uv.workspace]` anywhere in the repo (checked); `cli/pyproject.toml`
  + `cli/uv.lock` are self-contained; devcontainer `uv --version` reports
  `0.11.16`, which resolves relative-path dependencies (`uv add <path>`)
  without a workspace.

## Plan rework, 2026-08-23 (operator fork resolutions applied)

All four forks in the original §11 are resolved (see "Resolved forks"
above). Changes applied across the document:

1. **Q1 (drop L2).** §4's L2 bullet, §5, §9, and §10 subticket 1 all
   updated to state the resolution rather than pose the question. One
   thing this rework does **not** do: run `loopctl drop
   L2-landing-homepage "<reason>"` itself. That is a ledger mutation,
   and this agent's own operating boundary is "read-only toward product
   code; the only write is the ticket file; do not run the loop or
   advance the ledger" — a boundary that a relayed operator decision
   does not lift, since it is a constraint on this agent's role, not a
   judgment call being deferred. The recommended invocation, confirmed
   against `loopctl drop --help`:

       loopctl drop L2-landing-homepage "superseded by L3-landing-dash-app: custom app with config-driven tiles, connect-info modals, and cli-backed live status; L2's gethomepage design cannot produce any of the three and has zero commits"

   **This has since been run, outside this planning pass, as anticipated
   above.** `loopctl ledger` confirms `L2-landing-homepage: dropped` with
   that exact reason text. Precedent checked at the time: this ledger already carries
   `dropped: true` entries (e.g. `F4-foundation-dnsmasq-localstack-dns`,
   `S3-spike-oidc-version-claims`), confirming the mechanism; none of
   them carry a populated `drop_reason`, so this ticket's recommended
   command supplies one explicitly rather than assuming the field
   self-populates.
2. **Q2 (JSON).** §4, Requirement 1, §7's `tiles.json` filename, and
   §11 all changed from "TOML vs JSON, investigate" to "JSON,
   resolved." No other section depended on the format choice besides
   the file extension named in §7.
3. **Q3 (standalone app + path dependency, decided against
   subprocess).** The larger rewrite: §2, §4 (three bullets rewritten,
   two new bullets added on `require_session` and on `cli/`'s
   non-workspace shape), Requirement 2, Requirement 5, new Requirement
   8, §7 (backend/tests/Dockerfile bullets rewritten; the former
   `cli/pyproject.toml` edit bullet removed — this ticket no longer
   touches `cli/` at all; a new `.pre-commit-config.yaml` bullet added),
   §8 (gate description updated to name both the untouched `^cli/`
   hooks and the new hooks), §9 (new dependency-bloat risk bullet
   added), and §10 (subtickets renumbered and split: scaffolding the
   new project and adding its pre-commit hooks are now explicit early
   steps). New premises P16 and P17 added as the evidence backing the
   subprocess-vs-import call.
4. **Q4 (colocate on radxa-dragon-q6a).** Confirmed as originally
   recommended; hedging language ("if colocated... else") removed from
   Requirement 4 and §4's node/port bullet. The exact free port remains
   unconfirmed and stays a named item in §9 and §10 subticket 9 — that
   part of Q4 was never in question, only the node was.

Also renumbered/relabeled: §11's heading changed from "Open questions
(forks the operator must settle)" to "Resolved forks (operator,
2026-08-23)," and Premises P16/P17 were appended rather than inserted,
so every premise number cited elsewhere in the document (P1-P15) stays
correct.
