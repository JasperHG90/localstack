---
epic = "landing"
depends_on = ["L3-landing-dash-app"]
priority = 10
summary = "Revise the done L3 dash job: split its single task into a frontend task (static files only, no Python) and a backend task (status computation), and remove the backend's uv path dependency on cli/ entirely by copying the narrow subset of cli's health/nomad/services/consul logic it uses into the backend's own tree, with a provenance comment. Operator-decided, not up for debate: the split, and the no-cli-dependency rule."
tags = ["dash", "homepage", "nomad", "vault", "refactor", "fe-be-split"]
---

# Ticket: L4-landing-dash-fe-be-split

## 1. Title

Split `dash`'s single Nomad task into a frontend task (static files, no
Python, no `cli`) and a backend task (status computation, its own copy of
`cli`'s health/join logic, zero dependency on `cli`), in the same job.

## 2. Size / Effort

**L (large).** Not a config tweak — it rewrites the backend's Python import
graph (five new local modules copied out of `cli`), splits one Nomad task
into two with a new port and a new inter-task routing question, moves a
directory tree, retargets four pre-commit hooks, and touches the justfile,
`services.tf`, and `docs/dash-landing-page.md`. Drivers:

- The no-`cli`-dependency rule (operator hard requirement, §11 Decision 2)
  forces a genuine code copy, not a refactor: five new backend-local
  modules (`health.py`, `nomad_client.py`, `consul_client.py`,
  `services.py`, `_http.py`), each carrying a provenance comment (§7).
- The frontend/backend split reopens a question L3 never had to answer:
  today's single task serves both static files and `/api/status` on one
  port behind oauth2-proxy's single upstream
  (`deployments/infrastructure/services/oauth2-proxy.hcl:54`); splitting
  them needs a routing mechanism connecting the browser's still-single-origin
  `fetch('/api/status')` call to two different tasks. Genuinely open — see
  §11 Q1.
- Directory rename (`dash/app/` → `dash/backend/` + new `dash/frontend/`)
  touches every `path:line` anchor L3's own plan and this repo's
  pre-commit config, justfile, and docs currently cite for that tree.

## 3. Triggered by

Operator-directed follow-up to the `done` `L3-landing-dash-app`
(`.loop/plans/L3-landing-dash-app.md`, merged `43d4061`/`2bb1641`,
integrated `d971d7d`). Verbatim operator decisions (not open questions,
restated in full in §11 so this ticket does not relitigate them):

1. Split into a frontend task and a backend task in the **same** Nomad job.
2. "I don't give a shit about drift. I don't give a shit about code being
   copied or not. The backend should not depend on the CLI. This is a hard
   requirement." — no `uv` path dependency, no `import localstack_cli`,
   anywhere in the backend.
3. "Copy the Python code and call the Nomad endpoints with it." — the
   backend gets its own copies of the narrow subset of `cli`'s
   health/join/consul logic it actually uses today, plus its own minimal
   HTTP-calling code, each copy carrying a short provenance comment.

## 4. Context

- **What L3 built, exactly, today.** One task (`dash.hcl:17-88`), driver
  `podman`, `network_mode = "host"`, one static port (`http`, `8000`,
  `dash.hcl:12-14`), `vault { role = "dash" }` (`dash.hcl:54-56`), two
  `template` stanzas rendering the brokered Nomad token
  (`dash.hcl:67-72`) and `tiles.json` (`dash.hcl:79-82`) into the task,
  and a `service`/`check` block on `/api/status`
  (`dash.hcl:20-30`). (**P1**)
- **The backend's Python import graph today spans four `cli` modules, not
  the three the operator's own request named.**
  `deployments/applications/services/dash/app/src/dash_app/status.py:25-31`
  imports `localstack_cli.api.consul.Check`,
  `localstack_cli.api.haproxy.Route`, `localstack_cli.api.health.Health`
  and `judge_all`, `localstack_cli.api.nomad.Job`/`Node`, and
  `localstack_cli.api.services.JobSource`/`join`. The operator's own
  enumeration ("`health.py`... `Job`/`Node`/`Alloc`... `services.py`/
  `consul.py`") does not name `api/haproxy.py`, but `status.py:26` imports
  its `Route` dataclass to build synthetic per-tile routes
  (`status.py:80-87`, `build_routes`) — this is a correction to the
  request, not a new decision: the copy is incomplete without it. (**P2**)
- **`live.py` is the other half of the call graph.**
  `deployments/applications/services/dash/app/src/dash_app/live.py:9-16`
  imports `localstack_cli.api.consul.list_checks`/
  `list_services` and `localstack_cli.api.nomad.job_service_names`/
  `job_statuses`/`list_nodes`, and calls `dash_app.status.compute_tile_states`
  — it never imports `cli.api.services` or `cli.api.haproxy` directly; those
  live only in `status.py`. (**P3**)
- **`main.py` is what stops being "one app."**
  `deployments/applications/services/dash/app/src/dash_app/main.py:77-80`
  mounts both routes on one Starlette app: `Route("/api/status",
  status_endpoint)` and `Mount("/", app=StaticFiles(directory=FRONTEND_DIR,
  html=True))`. Splitting the task means this single `create_app` call no
  longer exists as one thing — the backend keeps the status route, the
  frontend keeps nothing Python at all (`FRONTEND_DIR`, at the same
  `main.py:26`, points at
  `deployments/applications/services/dash/app/src/dash_app/frontend/index.html`,
  the one static file to move).
- **`tiles.json`'s full content already flows through `/api/status`,
  not through any frontend-local data.** `main.py:29-52` (`_tile_json`)
  builds `key/name/desc/color/icon/category/node/status/counts` plus
  `url` or `connect` in one payload per tile, straight from `Tile` +
  computed `TileState`. The frontend has no separate tile-metadata source
  today and needs none after the split: it renders whatever
  `/api/status` returns. (**P15**)
- **The one call in `index.html` is a single, same-origin, relative
  fetch.**
  `deployments/applications/services/dash/app/src/dash_app/frontend/index.html:561`:
  `fetch('/api/status', { cache: 'no-store' })` — no other backend route
  is called anywhere in the file (grep for `fetch(` returns this one
  hit). Splitting frontend/backend does not require touching this line;
  it requires making sure *something* still answers `/api/status` at the
  same origin the browser already talks to. (**P11**)
- **oauth2-proxy fronts `dash` with exactly one upstream today, and that
  upstream is a loopback address to the single task's port.**
  `oauth2-proxy.hcl:54`, `OAUTH2_PROXY_UPSTREAMS="${dash_upstream}"`;
  `deployments/infrastructure/services.tf:415`,
  `dash_upstream = "http://127.0.0.1:8000"`. A frontend/backend split with
  two ports means this one upstream can no longer reach both — see §11
  Q1, the one genuine open question this ticket carries.
- **oauth2-proxy's own `--upstream` flag natively supports more than one
  upstream, routed by path — probed, not assumed.**
  `docker run quay.io/oauth2-proxy/oauth2-proxy:v7.13.0 --help`
  (run 2026-08-24) prints: `--upstream strings   the http url(s) of the
  upstream endpoint, file:// paths for static files or
  static://<status_code> for static response. Routing is based on the
  path`. The env var this repo already uses is documented in its own
  file as accepting the plural form: `oauth2-proxy.hcl:10-13`
  ("EMAIL_DOMAINS and UPSTREAMS are PLURAL... though their flags are
  singular"). (**P9**) The exact match semantics (prefix vs. exact,
  precedence between two upstreams) are **not** confirmed by this probe —
  only that the feature exists. (**P10**, UNCERTAIN)
- **This repo's own precedent for "two tasks, one job" always declares
  every port once, at group level, never per task.** `nats.hcl:12-25`
  (`nats`/`nats-exporter`, three group-level ports: `client`, `monitor`,
  `metrics`, each task's own `config.ports` naming only the ones it
  uses); `postgres.hcl:12-21` (`postgres`/`postgres-exporter`, two
  group-level ports: `db`, `exporter`). No job anywhere in
  `deployments/**/*.hcl` declares `network { port ... }` inside a
  `task {}` block. (**P5**)
- **This repo's own precedent for `vault {}` placement in a multi-task
  job is always task-scoped, and always symmetric (every task that needs
  Vault gets its own stanza) — but no job has the asymmetric shape this
  split introduces.** `postgres.hcl:70,96` (both `postgres` and
  `postgres-exporter` carry their own `vault {}`, same secret);
  `acme.hcl:73,154` (`issue`/`store`, both vaulted); `memex.hcl:44,114`
  (`db-migrate`/`memex`, both vaulted). `nats.hcl`'s two tasks carry
  neither. No existing job vaults one sibling task and not the other.
  (**P6**, **P7**)
- **The dash-read Vault role's `bound_claims` scopes to the job, not the
  task — so this split needs zero edit to
  `nomad_dash_read_role.tf`.** `nomad_dash_read_role.tf:76-79`:
  `bound_claims = { nomad_namespace = "default", nomad_job_id = "dash" }`
  — no `nomad_task` key, despite `claim_mappings` recording one
  (`:84-88`). Any task inside the `dash` job that presents `vault { role
  = "dash" }` authenticates identically regardless of which task asks.
  The stanza simply moves from the old single task onto the new backend
  task; the Terraform file itself does not change. (**P8**)
- **The Dockerfile's `--no-editable` flag is justified, in its own
  comment, entirely by the `cli` path dependency — and only by it.**
  `deployments/applications/services/dash/Dockerfile` (full text read):
  "The path dependency in pyproject.toml is relative to this
  directory... `--no-editable` is required. `pyproject.toml` declares the
  `cli` dependency editable... but an editable install lands as a `.pth`
  file pointing at this stage's absolute `/build/cli` path... found in
  adversarial review, AR1." With that dependency gone, the backend's
  remaining dependencies (`starlette`, `uvicorn`, the new `httpx`) are
  ordinary PyPI packages `uv sync` never installs in editable mode
  regardless of the flag — `--no-editable` becomes a no-op whose
  justifying comment no longer applies. (**P12**)
- **The image needs `httpx` as a direct dependency it does not
  declare today.** `pyproject.toml:6-9` lists `localstack-cli`,
  `starlette`, `uvicorn` — no `httpx`. `cli/src/localstack_cli/api/_http.py:10`
  (`import httpx`) is what actually supplies it today, transitively,
  through the `cli` path dependency. Dropping that dependency drops
  `httpx` with it unless added directly. (**P4**)
- **The firewall rule admitting `dash` traffic is scoped to loopback,
  self-host traffic that "never crosses this firewall" by the rule's own
  comment** — `deployments/applications/services.tf:94-104`. A new
  backend-only port used purely for same-host inter-task or
  oauth2-proxy-to-backend traffic should not need its own entry, on the
  same reasoning already recorded there. (**P13**)
- **This repo already has a tested convention for HTTP-calling code:
  `respx`-mocked, no real network**, covering parse-shape, token-header
  placement, and pagination-follow behavior.
  `cli/tests/test_api_nomad.py:1-73` — `test_job_statuses_parses_the_live_capture`,
  `test_the_token_is_sent_in_nomads_own_header`, `test_pagination_is_followed`,
  `test_pagination_passes_the_token_back`. (**P14**)
- **L3's own named dependency-bloat risk (`textual`/`rich`/`click`/`typer`
  riding along with `cli`) is not deferred by this ticket, it is fully
  resolved by it** — Requirement 2 drops the `cli` dependency outright.
  (**P16**)

## 5. Non-goals / out of scope

- Relitigating the frontend/backend split, the no-`cli`-dependency rule,
  or the "copy the code" mechanism. All three are operator-decided (§3,
  §11 Decisions 1-3) and restated, not reopened, by this ticket.
- Redesigning the mockup's UI/UX, or editing `index.html`'s client-side
  JS/CSS logic. The one fetch call (`index.html:561`) needs no code
  change under either §11 Q1 option — only where it resolves to matters.
- Changing `tiles.json`'s schema, content, or the `jsondecode`/`jsonencode`
  round-trip Terraform does with it (`services.tf:187-206`, unaffected).
- Changing the Nomad ACL policy's granted capabilities.
  `nomad_dash_read_role.tf`'s `rules_hcl` stays exactly
  `read-job`/`list-jobs`/`node:read` — only which task's `vault {}`
  stanza requests role `"dash"` changes (§4, P8).
- Any `haproxy.hcl` edit. The split happens entirely behind the existing
  `dash` route; L1's edge routing is untouched.
- Publishing an "api-only" narrower install target for `cli`, or turning
  `cli/` into a `uv` workspace. Both are now moot for this ticket's own
  purposes (backend no longer depends on `cli` at all, P16) and remain
  out of scope for `cli/`'s own shape regardless.
- Building a general-purpose, reusable multi-upstream pattern into
  oauth2-proxy's Terraform beyond what this one job needs, if §11 Q1
  resolves to the oauth2-proxy option.
- Any change to Postgres/Redis/NATS credential models. Unrelated.
- Fixing the first-SSO-attempt quirk (`docs/dash-landing-page.md:19-24`).
  Still observed, still not root-caused, still out of scope.

## 6. Requirements & restrictions

Must achieve:

1. **Two tasks, one job.** `dash.hcl` gets `task "frontend"` and
   `task "backend"` inside the existing `group "dash"` — not two jobs
   (§3 Decision 1).
2. **Zero `cli` dependency anywhere under the backend's tree.** No
   `[tool.uv.sources]` path entry, no `localstack-cli` in
   `dependencies`, no `import localstack_cli` in any `.py` file under
   `deployments/applications/services/dash/backend/`. Checkable by grep
   (§3 Decision 2, hard requirement — not an Open Question).
3. **The backend's own copies of the narrow subset actually used today**
   (§4 P2, P3), each carrying a short provenance comment naming the
   exact `cli` source file it was copied from, per this repo's own
   hidden-constraint-comment convention (e.g. `dash.hcl:48-53`'s own
   comment block is the model). Minimum surface, resolved against the
   two call sites (`status.py`, `live.py`):
   - `Health`, `JobHealth`, `eligible_nodes`, `judge`, `judge_all` (from
     `cli/src/localstack_cli/api/health.py`, all of it — `judge_all`
     calls the other four).
   - `Job`, `Node`, `Alloc`, `job_statuses`, `list_nodes`,
     `job_service_names`, `get_job` (from
     `cli/src/localstack_cli/api/nomad.py` — `Template`/`job_templates`
     are unused by dash and stay out of the copy).
   - `JobSource`, `ServiceRow`, `NO_CHECK`, `NOT_FOUND`,
     `AGENT_ENDPOINT`, `_check_state`, `_sole_tag_carrier`, `join` (from
     `cli/src/localstack_cli/api/services.py` — `find` is unused and
     stays out).
   - `Check`, `list_checks`, `list_services` (from
     `cli/src/localstack_cli/api/consul.py` — the module-level
     `failing()` helper is unused by dash and stays out; the `Check.failing`
     property IS used, inside the copied `_check_state`, and stays in).
   - `Route` (from `cli/src/localstack_cli/api/haproxy.py:46-57` — the
     four-field dataclass only, never `parse_routes`/`HaproxyParseError`/
     the regexes; dash only ever builds synthetic routes,
     `status.py:80-87`). Named explicitly because the operator's own
     request omitted it (§4 P2) — this is a correction, not a new scope
     item.
4. **The backend's own minimal HTTP-calling code**, replacing
   `cli.api._http.get_json` (§3 Decision 3). Must support an optional
   bearer/token header (Nomad calls) and return response headers
   alongside the parsed body, since `job_statuses`'s pagination reads
   `X-Nomad-Nexttoken` off them (`nomad.py:131`, carried into the copy).
   The full 401-vs-403 typed-error taxonomy
   (`cli/src/localstack_cli/api/errors.py`) is not required: `main.py`'s
   existing broad `except Exception` (`main.py:60-67`, unchanged by this
   ticket) already turns any failure into an "unknown" tile plus an
   error string, so the fine distinction between "dead token" and
   "missing capability" is not behaviorally load-bearing here.
5. **The frontend serves static files only.** No Python, no `cli`, no
   Vault/Nomad credential, no `tiles.json` mount, no `vault {}` stanza
   on the frontend task at all (§4 P8 — the grant is job-scoped, not
   task-scoped, so nothing forces the frontend to hold it, and
   Requirement 5 says it must not).
6. **The Nomad ACL grant's capabilities do not change.**
   `nomad_dash_read_role.tf`'s `rules_hcl` stays byte-identical; only
   the `vault { role = "dash" }` stanza's task location moves, from the
   old single task onto the new backend task (§4 P8).
7. **The `.Data.secret_id` Vault template nesting fix carries over
   verbatim** on whichever task now renders `nomad/creds/dash_read`
   (the backend task) — `dash.hcl:58-72`'s existing comment and template
   body, unchanged in substance.
8. **Resolve `--no-editable`'s status rather than assuming it.** Since
   its sole justification (§4 P12) no longer applies, either drop it
   from the backend's Dockerfile with an updated comment, or state
   explicitly in the Dockerfile why it is kept. Do not carry a stale
   comment that cites a dependency the backend no longer has.
9. **No credential value reaches the frontend task, its image, or the
   browser**, at any point — same bar L3's own Requirement 7 set,
   unchanged by the split.
10. **`/api/status`'s JSON contract stays byte-for-byte identical.**
    `index.html`'s own rendering logic is out of scope (§5) and depends
    on the shape `main.py:29-52`'s `_tile_json` already produces.
11. **Resolve and implement §11 Q1** (how the browser's single-origin
    `/api/status` fetch reaches the backend task once the frontend is
    static-only) behind the same oauth2-proxy gate, with no new
    unauthenticated route to either task.
12. **The four `dash-app-*` pre-commit hooks keep firing after the
    move.** `.pre-commit-config.yaml:78-101`'s `files:` patterns
    (`^deployments/applications/services/dash/app/`) must retarget to
    wherever the backend's Python tree actually lands, or they silently
    stop matching anything.
13. **`docs/dash-landing-page.md` reflects the new architecture** —
    directory layout, task split, and (once §11 Q1 resolves) the
    routing mechanism and any changed rebuild/deploy steps.

Restrictions the repo enforces (each cited):

- Simplicity / surgical changes (`CLAUDE.md` §§1-3): copy only the
  functions/dataclasses named in Requirement 3, not the rest of `cli`'s
  `api/` modules; do not touch `cli/` itself anywhere (this ticket's
  code surface never edits a file under `cli/`).
- New Python dependencies via `uv add`, never `uv pip`
  (`.claude/rules/uv-installer.md`) — covers the new `httpx` dependency
  (Requirement 4).
- Every code change ships a test; a bug fix reproduces first
  (`.claude/rules/python-testing.md`). HTTP-calling code is tested with
  `respx`, not real network, matching `cli/tests/test_api_nomad.py`'s
  own convention (§4 P14) — never hand-rolled patches, never a live call.
- Cluster-touching tests carry the `cluster` marker and stay excluded
  from the default run (`pyproject.toml:29-36`'s existing
  `markers`/`addopts` pair, unchanged in substance, just possibly
  retargeted addresses per §11 Q1's resolution).
- Secrets live in Vault KV2, never hardcoded (`README.md:36`) — the
  brokered Nomad token continues to reach the backend task only via the
  existing `template` stanza (Requirement 7).
- Nomad HCL formatting (`nomad-fmt`) and Terraform
  formatting/validation (`terraform-fmt`, `terraform-validate` via
  `scripts/tf_validate.sh`) for whichever root(s) this ticket edits.
- Pin the container image tag(s); no `:latest`, matching this repo's
  existing convention (e.g. `bifrost.hcl:40`) and `dash.hcl:33`'s own
  current `${dash_version}` pattern.
- Adversarial review before done (`.claude/rules/adversarial-reviews.md`).
  Hand the reviewer: no diff in `nomad_dash_read_role.tf`'s `rules_hcl`;
  a repo-wide grep for `localstack_cli`/`localstack-cli` under the
  backend's tree returns nothing; every copied module carries a
  provenance comment; no credential value reaches the frontend; the
  retargeted pre-commit hooks actually fire on a change under the new
  backend path and do not fire on a frontend-only change (it has no
  Python to lint).

## 7. Code surface

Layout decision (this ticket's call, per the operator's own invitation
to "decide the new layout... state and justify"): rename
`deployments/applications/services/dash/app/` to
`deployments/applications/services/dash/backend/`, and create
`deployments/applications/services/dash/frontend/` as a sibling. Both
mirror `deployments/applications/services/dash/`'s existing shape of
"the job's own subdirectory holds its build content" (L3 §11 Q3), now
once per task instead of once per job. "Backend"/"frontend" is
unambiguous once there are two things; "app" stops meaning anything
once it no longer names the whole job.

- **MOVE + EDIT**
  `deployments/applications/services/dash/app/` →
  `deployments/applications/services/dash/backend/` (git mv, preserving
  history). Within it:
  - **EDIT** `pyproject.toml` — drop `localstack-cli` from
    `dependencies` (`pyproject.toml:7`) and the whole
    `[tool.uv.sources]` block (`:58-59`); drop the
    `[[tool.mypy.overrides]] module = "localstack_cli.*"` exemption
    (`:54-56`), now dead config; add `httpx` via `uv add` (Requirement
    4).
  - **CREATE** `src/dash_app/health.py` — copied subset from
    `cli/src/localstack_cli/api/health.py` (Requirement 3), provenance
    comment.
  - **CREATE** `src/dash_app/nomad_client.py` — copied subset from
    `cli/src/localstack_cli/api/nomad.py` (Requirement 3), provenance
    comment.
  - **CREATE** `src/dash_app/consul_client.py` — copied subset from
    `cli/src/localstack_cli/api/consul.py` (Requirement 3), provenance
    comment.
  - **CREATE** `src/dash_app/services.py` — copied subset from
    `cli/src/localstack_cli/api/services.py` plus the `Route` dataclass
    from `cli/src/localstack_cli/api/haproxy.py:46-57` (Requirement 3),
    provenance comment(s) for both sources.
  - **CREATE** `src/dash_app/_http.py` — the minimal HTTP-calling code
    (Requirement 4), replacing `cli.api._http.get_json`.
  - **EDIT** `src/dash_app/status.py` — import from the new local
    modules instead of `localstack_cli.*` (`status.py:25-31`); update
    the module docstring's "the same tested, pure functions the
    `localstack service` command already uses" framing (`:1-19`) to
    describe a copy, not a shared import, so a future reader is not
    told the two are the same code.
  - **EDIT** `src/dash_app/live.py` — same import rewire
    (`live.py:9-16`); same docstring correction ("Thin glue over cli's
    own read functions" → this app's own copies, `:1-7`).
  - **EDIT** `src/dash_app/main.py` — drop `FRONTEND_DIR`
    (`main.py:26`) and the `Mount("/", app=StaticFiles(...))` route
    (`:79`); keep the `/api/status` route and its existing broad
    `except Exception` handling (`:56-75`) unchanged.
  - `src/dash_app/config.py`, `src/dash_app/tiles.py` — unedited;
    neither imports `cli` today (confirmed by reading both in full).
  - `tests/test_status.py`, `tests/test_tiles.py`,
    `tests/test_main.py` — import-path edits only for the first two
    (assertions unchanged); `test_main.py` needs no static-serving
    assertions removed (it never tested that route). New tests for
    `_http.py`, `nomad_client.py`, `consul_client.py`: pagination-follow
    and token-header-placement, `respx`-mocked, modeled on
    `cli/tests/test_api_nomad.py:27-73` (§4 P14).
  - **EDIT** `tests/test_cluster.py` — `_dash_addr()`'s default
    (`test_cluster.py:24`, currently `http://192.168.2.50:8000`) must
    retarget to whichever task/port now actually answers `/api/status`
    once §11 Q1 resolves; port 8000 may no longer serve that route at
    all under one of the two options.
  - **EDIT** `Dockerfile` (moves with the directory) — build context
    narrows to `deployments/applications/services/dash/backend/` alone
    (single directory, matching `hermes/Dockerfile`'s shape); drop the
    `COPY cli` stage entirely; resolve `--no-editable` per Requirement
    8.
- **CREATE** `deployments/applications/services/dash/frontend/` —
  `index.html`, moved verbatim from
  `dash/app/src/dash_app/frontend/index.html` (no content edit, per §5
  and P11); its own `Dockerfile` (indicative: single-stage, e.g.
  `FROM nginx:alpine` + `COPY index.html /usr/share/nginx/html/` — no
  repo precedent binds the exact tool, "small, dependency-free
  static-file server" is the only constraint from §3 Decision 1). No
  proxy config in the frontend image — §11 Q1 resolved to oauth2-proxy
  doing the routing instead.
- **EDIT** `deployments/applications/services/dash.hcl` — group-level
  `network {}` gains a second named port for the backend (indicative
  name `backend`, exact number TBD at implementation, matching L3's own
  §9 TBD-port precedent for the original `8000`); `task "frontend"`
  (no `vault {}`, no `template`, its own `service`/`check` on `/`,
  `config.image` = new frontend image); `task "backend"` (keeps
  `vault { role = "dash" }` and both existing `template` stanzas
  verbatim in content, own `service`/`check` on `/api/status`,
  `config.image` = new backend image). Ports declared once at group
  level per Requirement 1's model (§4 P5).
- **EDIT** `deployments/applications/services.tf` — `nomad_job "dash"`'s
  `templatefile(...)` vars (`:191-206`) gain a second version var for
  the two images (indicative: `dash_frontend_version`/
  `dash_backend_version`, or one shared tag — implementer's call, either
  satisfies "pin the image, no `:latest`"); `locals.dash_tiles_json`
  (`:187-189`) is unchanged, still feeding the backend task only.
- **EDIT** `deployments/applications/justfile` — `rebuild_dash`
  (`:54-63`) retargets the backend build to the narrowed single-directory
  context and drops the `cd "$(git rev-parse --show-toplevel)"` line
  (`:61`), now unnecessary (Requirement 8's finding, P12); add an
  equivalent recipe for the frontend image (or extend one recipe to
  build both — implementer's call), using `rebuild_hermes`'s plain
  single-directory shape (`justfile:35-43`) as the model for both.
- **EDIT** `.pre-commit-config.yaml:78-101` — retarget all four
  `dash-app-*` hooks' `files:` and `entry` paths from
  `deployments/applications/services/dash/app/` to
  `deployments/applications/services/dash/backend/`; rename the hook
  `id`s (`dash-app-*` → `dash-backend-*`) so a future reader is not told
  "app" when the tree now holds only the backend (Requirement 12).
- **EDIT** `docs/dash-landing-page.md` — architecture description
  (two tasks, not one), the "Rebuilding and deploying the image"
  section's commands if the recipe split changes them, and a line
  covering the routing mechanism once §11 Q1 resolves (Requirement 13).
- **Per §11 Q1's resolution (option (a)):** **EDIT**
  `deployments/infrastructure/services/oauth2-proxy.hcl:54`
  (`OAUTH2_PROXY_UPSTREAMS` becomes two comma-separated, path-routed
  values) and **EDIT** `deployments/infrastructure/services.tf:415`
  (`dash_upstream` var, split into frontend/backend loopback URLs). No
  frontend-side proxy config; the frontend stays static-file-only.
- Read-only anchors to consume, not edit:
  `cli/src/localstack_cli/api/health.py`,
  `cli/src/localstack_cli/api/nomad.py`,
  `cli/src/localstack_cli/api/services.py`,
  `cli/src/localstack_cli/api/consul.py`,
  `cli/src/localstack_cli/api/haproxy.py:46-57` (the four copy
  sources, Requirement 3); `nats.hcl`, `postgres.hcl` (two-task job
  model, §4 P5, P6); `hermes/Dockerfile` (single-directory build
  context model); `nomad_dash_read_role.tf` (unchanged grant, re-cited
  for the "no Terraform edit needed here" claim, P8);
  `cli/tests/test_api_nomad.py` (test model for the new HTTP-calling
  code, P14).

## 8. Tests & validation gates

- **Repo gate:** `just pre_commit` (`justfile:18-19`,
  `pre-commit run --all-files`). Covers: `nomad-fmt` on `dash.hcl`;
  `terraform-fmt`/`terraform-validate`
  (`scripts/tf_validate.sh`) on whichever root(s) §11 Q1's resolution
  touches; the four retargeted `dash-backend-*` hooks
  (`ruff`/`ruff-format`/`mypy --strict`/`pytest`) against the new
  `dash/backend/` path.
- **Unit tests** (`deployments/applications/services/dash/backend/tests/`):
  `test_status.py`/`test_tiles.py` ported (import paths only,
  assertions unchanged, §7); new `respx`-mocked tests for `_http.py`/
  `nomad_client.py`/`consul_client.py` covering successful parse,
  token-header placement, and pagination-follow, modeled on
  `cli/tests/test_api_nomad.py:27-73` (§4 P14, Requirement 4). No
  network, no `cluster` marker.
- **`cluster`-marked test:** `test_cluster.py` retargeted to whichever
  task/port answers `/api/status` after §11 Q1 resolves (§7); excluded
  from the default run, run on purpose with `-m cluster`.
- **`terraform -chdir=deployments/applications plan`** must show the
  `dash` job's spec changed (two tasks) and destroy nothing.
- **`terraform -chdir=deployments/infrastructure plan`** must show the
  `oauth2_proxy` job updated in place (new upstream value) and
  **no diff at all** in `nomad_dash_read_role.tf`'s resources
  (Requirement 6 — an explicit thing to confirm, not assume).
- **Adversarial review** (`.claude/rules/adversarial-reviews.md`):
  confirm `nomad_dash_read_role.tf` has zero diff; a repo-wide grep
  under `dash/backend/` for `localstack_cli`/`localstack-cli` returns
  nothing; every copied module (`health.py`, `nomad_client.py`,
  `consul_client.py`, `services.py`) carries a provenance comment
  naming its `cli` source file; no credential value reaches the
  frontend task, its image, or any `/api/status` response; the
  retargeted pre-commit hooks fire on a `dash/backend/` change and do
  not spuriously fire on a `dash/frontend/`-only change.
- **Eval marker (loop-harness acceptance, `require_eval: true` per
  `.loop/config.json`):** none exists yet for this ticket. Loop pickup
  is blocked until `.loop/evals/L4-landing-dash-fe-be-split.md` exists
  and `loopctl eval`/`loopctl verify-eval-substance` both report
  `valid` — see the closing recommendation.

## 9. Risk assessment

- **Blast radius:** the `dash` job's own spec and image build are
  additive/isolated to this ticket's own tree. The one place this
  ticket touches a live, shared file is `oauth2-proxy.hcl:54`
  (§11 Q1 resolved to the multi-upstream option) — a malformed
  upstream value there breaks the whole `dash` route the same way a
  bad edit would have under L3 (§9 of that ticket), still scoped to
  `dash` alone, not any other oauth2-proxy'd service.
- **Copying, not importing, means the two implementations of
  health/join logic can now drift.** Named risk, explicitly accepted
  by the operator (§3 Decision 2 — "I don't give a shit about drift"),
  not a blocker and not something requiring further sign-off. Recorded
  here per the operator's own instruction, the way L3 named its own
  accepted risks (§9 of that ticket).
- **The asymmetric vault-stanza shape (frontend unvaulted, backend
  vaulted, same job) has no exact precedent in this repo** (§4 P7).
  Low risk in practice — Nomad's `vault {}` stanza is unconditionally
  per-task-optional, and single-task jobs across this repo already
  show plenty with none — but it is a first-of-its-kind combination
  worth naming rather than silently assuming works.
- **`nomad_dash_read_role.tf`'s task-agnostic `bound_claims` (§4 P8)
  is the load-bearing fact that keeps Requirement 6 true.** If that
  premise is wrong (unlikely, given the file's own text, but not
  independently probed against a live Vault), the backend task's
  `vault { role = "dash" }` stanza could fail to authenticate after
  the move, and the fix would be a `nomad_task` addition to
  `bound_claims` — a real Terraform change this ticket currently
  expects not to need.
- **`--no-editable`'s removal (Requirement 8) is argued from the
  Dockerfile's own comment, not independently rebuilt against the
  image.** If some other, uncited reason exists for it, dropping it
  blind could reintroduce a packaging bug. Low risk — the comment is
  explicit and singular about its cause — but worth a build-and-run
  smoke test before trusting it silently.
- **Reversibility:** high. The directory rename is a `git mv`; the
  Nomad job spec change reverts to L3's own committed version; if
  `oauth2-proxy.hcl` is touched, its revert is a one-line diff back to
  the single-upstream form.
- **Node/port collision**, same recurring class L2 and L3 both hit —
  a new backend-only port on `radxa-dragon-q6a` needs confirming free
  against existing occupants there (8000 dash-frontend, 8642 hermes,
  8080 bifrost, 4180 oauth2-proxy, 6379 redis, 4222/8222 nats) before
  implementation.

## 10. Subtickets

Ordered, dependency-aware. Steps 5 onward assume §11 Q1 is resolved;
until then, they are blocked on that decision, not merely sequenced
after earlier steps.

1. **Scaffold the rename**: `git mv dash/app` → `dash/backend`; edit
   `pyproject.toml` to drop `localstack-cli`/`[tool.uv.sources]`/the
   mypy override, add `httpx`. Depends on: nothing.
2. **Copy the five backend-local modules** (`health.py`,
   `nomad_client.py`, `consul_client.py`, `services.py`, `_http.py`),
   each with its provenance comment. Depends on: 1.
3. **Rewire `status.py`/`live.py`/`main.py`** to the new local imports;
   drop the static-file mount; port `test_status.py`/`test_tiles.py`/
   `test_main.py`'s import paths; write the new `_http.py`/
   `nomad_client.py`/`consul_client.py` tests. Depends on: 2.
4. **Move `index.html`** into a new `dash/frontend/` directory (no
   content edit). Depends on: nothing (parallel to 1-3).
5. **§11 Q1 resolved: option (a), oauth2-proxy multi-upstream.** Recorded
   settled in §11. Depends on: nothing (parallel to 1-4).
6. **Frontend's own Dockerfile.** Depends on: 4, 5.
7. **`dash.hcl`**: two tasks, group-level second port, `vault {}`
   moved onto the backend task only, per-task `service`/`check`.
   Depends on: 3, 6.
8. **`services.tf`**: second version var, unchanged `dash_tiles_json`
   local. Depends on: 7.
9. **`justfile`**: retarget `rebuild_dash`'s context, drop the
   repo-root `cd`, add the frontend build. Depends on: 7.
10. **`.pre-commit-config.yaml`**: retarget the four hooks. Depends on:
    1 (path exists as soon as the rename lands; can run in parallel
    with 2-9).
11. **Edit `oauth2-proxy.hcl:54` and `services.tf:415`** for the
    multi-upstream split. Depends on: 7, 8.
12. **`test_cluster.py`** address retarget. Depends on: 7, 11.
13. **`docs/dash-landing-page.md`** update. Depends on: 1-12.
14. **Adversarial review + eval.** Depends on: 1-13.

## 11. Decisions carried forward (operator, do not relitigate) & Open questions

**Decision 1 — frontend/backend split, same job.** Two tasks in
`group "dash"`, not two jobs. Source: §3, verbatim operator request.

**Decision 2 — no `cli` dependency in the backend, at all.** Hard
requirement, explicitly weighed against and accepted the drift
tradeoff ("I don't give a shit about drift... This is a hard
requirement"). Not an Open Question; do not resurface it as one.
Source: §3.

**Decision 3 — copy the code, with provenance comments.** The
mechanism for Decision 2: self-contained copies of the narrow subset
`status.py`/`live.py` actually use, not a blind full copy of every
function in the four (now, per §4 P2, five) source modules, each
carrying a short comment naming its origin. Source: §3.

**Q1 — OPEN: how does the browser's `/api/status` fetch reach the
backend task once the frontend is static-only?** Not resolved by the
operator's own request, the repo, or any prior ticket. `index.html`'s
one fetch call (`index.html:561`) is same-origin and relative, and
oauth2-proxy currently forwards the whole `dash` route to one upstream
(`oauth2-proxy.hcl:54`). Two options:

- **(a) — oauth2-proxy multi-upstream, path-routed.** Point
  `OAUTH2_PROXY_UPSTREAMS` at two comma-separated URLs: a catch-all to
  the frontend's loopback port, and a path-scoped one to the backend's
  `/api/status`. Verified as a real oauth2-proxy capability by probe
  (§4 P9: `--upstream strings ... Routing is based on the path`,
  `docker run quay.io/oauth2-proxy/oauth2-proxy:v7.13.0 --help`,
  run 2026-08-24) and consistent with this file's own documented
  plural-env convention (`oauth2-proxy.hcl:10-13`). Cost: a second edit
  to `oauth2-proxy.hcl` and `services.tf:415` beyond L3's original
  one-time upstream retarget — a live, shared file, though the same
  file L3 already established as this job's one legitimate edit point.
  Exact path-match semantics (prefix vs. exact, precedence) are
  UNCERTAIN (§4 P10) and need implementation-time verification before
  the exact upstream values are trusted.
- **(b) — frontend embeds its own reverse proxy** for `/api/status`
  only, forwarding to the backend's loopback port; `oauth2-proxy.hcl`
  stays untouched. Cost: the frontend is no longer *purely* a
  static-file server (§3 Decision 1's own words) — it also holds
  routing logic and a proxy config, a small but real expansion of what
  the operator described the frontend as being.

  **Recommendation: (a).** It keeps the frontend genuinely limited to
  serving files, matching Decision 1's own description most literally,
  and it uses a verified, native oauth2-proxy capability rather than
  adding new logic to a component explicitly scoped down to "no logic
  at all." The cost — one more `oauth2-proxy.hcl` edit — is smaller
  than the cost of quietly widening what "frontend" means.

**Q1 — RESOLVED: (a), oauth2-proxy multi-upstream, path-routed.**
Operator delegated this decision ("I'm not here so drive the loop
yourself. You are in control."); resolved per the plan's own
recommendation above, on the same reasoning: it holds Decision 1's
"small, dependency-free static-file server" description literally,
rather than growing the frontend into something that also proxies.
`OAUTH2_PROXY_UPSTREAMS` becomes two comma-separated values — a
catch-all to the frontend's loopback port, a path-scoped one
(`/api/status=...`) to the backend's. §7's "Conditional on §11 Q1"
bullet resolves to its first branch (edit `oauth2-proxy.hcl:54` and
`services.tf:415`); its second branch (frontend-side proxy) is
dropped. §10 steps 6, 11, 12 resolve to their oauth2-proxy-option
paths. P10's UNCERTAIN status stands and is NOT resolved by this
decision — the exact path-match semantics (prefix vs. exact,
precedence) still need implementation-time verification against a
real oauth2-proxy config before the exact upstream values are
trusted; this is deferred to subticket 11, not to this planning pass.

## Premises / assumptions

- **P1.** `dash.hcl` today is one task, `network_mode = "host"`, one
  static port 8000, `vault { role = "dash" }`, two `template` stanzas
  (token, tiles), one `service`/`check` on `/api/status`.
  `Evidence:` `dash.hcl:1-90`, full text read.
- **P2.** `status.py` imports from four `cli` modules
  (`consul`/`haproxy`/`health`/`nomad`/`services` — five files, since
  `nomad` and `services` are separate), not the three the operator's
  own request named; `haproxy.Route` is a real, load-bearing import
  the request omitted.
  `Evidence:` `status.py:25-31`.
- **P3.** `live.py` imports only from `cli.api.consul` and
  `cli.api.nomad`; it never imports `cli.api.services`/`cli.api.haproxy`
  directly — those are `status.py`'s alone.
  `Evidence:` `live.py:9-16`.
- **P4.** `httpx` is not a direct dependency of `dash`'s
  `pyproject.toml` today; it arrives transitively through the `cli`
  path dependency (`cli.api._http`'s own `import httpx`). Dropping
  `cli` drops `httpx` unless added directly.
  `Evidence:` `pyproject.toml:6-9` (no `httpx` in `dependencies`);
  `cli/src/localstack_cli/api/_http.py:10`.
- **P5.** Every multi-task job in this repo declares all its
  `network { port ... }` stanzas once, at group level; no job declares
  a port inside a `task {}` block.
  `Evidence:` `nats.hcl:12-25` (two tasks, three group-level ports);
  `postgres.hcl:12-21` (two tasks, two group-level ports).
- **P6.** Every multi-task job in this repo that vaults any task vaults
  every task that needs Vault, individually and symmetrically; the
  stanza is always task-scoped, never group-scoped.
  `Evidence:` `postgres.hcl:70,96`; `acme.hcl:73,154`; `memex.hcl:44,114`;
  grep sweep of `vault {` across `deployments/**/*.hcl` (run
  2026-08-24) finds only task-nested occurrences.
- **P7.** No existing job in this repo has an asymmetric multi-task
  vault split (one task vaulted, a sibling not) — every multi-task job
  either vaults all its tasks or none.
  `Evidence:` same sweep as P6; `nats.hcl` (neither task vaulted)
  against `postgres.hcl`/`acme.hcl`/`memex.hcl` (all tasks vaulted).
- **P8.** `vault_jwt_auth_backend_role.dash`'s `bound_claims` checks
  `nomad_namespace` and `nomad_job_id` only, never `nomad_task` — any
  task in the `dash` job authenticates identically under role `"dash"`,
  so the split needs no edit to `nomad_dash_read_role.tf` itself.
  `Evidence:` `nomad_dash_read_role.tf:76-79` (the `bound_claims`
  block); `:84-88` (`claim_mappings` records `nomad_task` but nothing
  gates on it).
- **P9.** oauth2-proxy's `--upstream` flag accepts multiple,
  path-routed values, and this repo's own `OAUTH2_PROXY_UPSTREAMS` env
  var is documented to accept the plural form.
  `probe:` `docker run quay.io/oauth2-proxy/oauth2-proxy:v7.13.0
  --help`, run 2026-08-24, captured: `--upstream strings   the http
  url(s) of the upstream endpoint, file:// paths for static files or
  static://<status_code> for static response. Routing is based on the
  path`. `Evidence:` `oauth2-proxy.hcl:10-13`.
- **P10 (UNCERTAIN).** The exact path-match semantics of oauth2-proxy's
  multi-upstream routing (prefix vs. exact, precedence when two
  upstreams could both match) are not confirmed by the P9 probe — only
  that the feature exists. `probe:` not yet run against a real
  multi-upstream config; confirm before finalizing §11 Q1 option (a)'s
  exact upstream values.
- **P11.** `index.html` makes exactly one backend call, a same-origin
  relative `fetch('/api/status', ...)`, and needs no code change under
  either §11 Q1 option.
  `Evidence:` `index.html:561`; grep for `fetch(` across the file
  returns this one hit.
- **P12.** The Dockerfile's `--no-editable` flag is justified, in its
  own comment, entirely by the `cli` path dependency's editable-install
  `.pth`-path bug (AR1); with that dependency removed, `uv sync` has no
  local/path/workspace dependency left to install in editable mode, so
  the flag becomes a no-op.
  `Evidence:` `Dockerfile`, full text — the `--no-editable` comment
  block names only the `cli` dependency as its cause.
- **P13.** The `dash` firewall rule is scoped to self-host loopback
  traffic that, by its own comment, never crosses the firewall; a new
  backend-only port used purely for same-host traffic should not need
  its own entry on that same reasoning.
  `Evidence:` `services.tf:94-104`.
- **P14.** This repo's convention for testing httpx-calling code is
  `respx`-mocked, covering parse-shape, token-header placement, and
  pagination-follow — the model for the new backend's own HTTP-code
  tests.
  `Evidence:` `cli/tests/test_api_nomad.py:1-73`.
- **P15.** `tiles.json`'s full display content already flows through
  `/api/status`'s own JSON payload; the frontend has no separate
  tile-metadata source today and needs none after the split.
  `Evidence:` `main.py:29-52` (`_tile_json`).
- **P16.** L3's own named dependency-bloat risk (the whole `cli`
  package, including `textual`/`rich`/`click`/`typer`, riding along for
  `api/`-only use) is fully resolved by this ticket's Requirement 2,
  not merely deferred.
  `Evidence:` L3 §9's dependency-bloat bullet; this ticket's Requirement
  2 (backend drops `cli` entirely).
