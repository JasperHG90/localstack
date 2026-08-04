---
epic = "cli"
depends_on = ["D2-cli-login-broker-tokens", "F11-foundation-human-read-role"]
priority = 42
tags = ["cli", "textual", "tui", "observability"]
summary = "A Textual `localstack monitor` panel showing Vault seal state, Nomad node status, per-job allocation health, and Consul critical checks. A developer's glance-check, not a Grafana replacement: no dashboards, no history, no alerting. Each source polls independently so a sealed Vault or a dead endpoint degrades one panel instead of hanging the UI."
---

# Ticket: D4-cli-cluster-tui

## 1. Title

Add a Textual TUI (`localstack monitor`) that answers "is the cluster fine and
is my job running" in one screen, using the tokens D2 brokers.

## 2. Size / Effort

**Medium.** Four data sources, one screen, four widgets. The cost is not the
rendering: it is (a) deterministic snapshot tests against a live-cluster data
source, (b) degraded-state handling that must be designed in rather than
bolted on, and (c) building the shared `api/` layer under D3's contract,
because pickup order puts this ticket ahead of D3 (see Q3).

## 3. Triggered by

Operator, 2026-07-30, quoted: **"not a Grafana replacement but a panel for
developers"**. Grafana, Prometheus and Loki already run here
(`docs/monitoring.md:1-27`). Reaching them means opening a browser and logging
in. The missing thing is a terminal glance.

## 4. Context (today's state)

### The CLI package D1 and D2 shipped
- D1 and D2 are `done`. `cli/` ships with `cli/pyproject.toml` (runtime deps
  `click`, `rich`, `typer` at `:7-9`), the `cli/src/localstack_cli/` src
  layout, and D2's command modules under `cli/src/localstack_cli/commands/`
  (`login`, `logout`, `whoami`, `env`, `token`, `config`) registered lazily via
  `LAZY_SUBCOMMANDS` (`cli/src/localstack_cli/main.py:11-14,42`). The legacy
  `requirements.txt:1-5` remains for the non-CLI scripts.
- The package path this ticket writes to is `cli/src/localstack_cli/`, D1's
  src layout (`.loop/archive/D1-cli-package-skeleton/plan.md:167-191`, console
  script at `:171`, src layout at `:174`). See Q1.

### The cluster this panel reports on (all re-measured 2026-07-31)
- **19 Nomad jobs**, mixed types: `acme`, `backup-minio`, `backup-postgres`
  (`batch/periodic`); `node-exporter`, `promtail` (`system`); the other 14
  `service`.
- **The job data source is `GET /v1/jobs/statuses`, not `GET /v1/jobs`.** One
  call returns all 19 jobs, each carrying `GroupCountSum` (the desired count),
  an `Allocs` array of the job's **current** allocations with `ClientStatus`,
  `Group`, `NodeID` and `DeploymentStatus.Healthy`, plus `ChildStatuses`,
  `LatestDeployment.Status`, `Type`, `Status`, `Stop` and `ParentID`. Verified
  live 2026-07-31: 200 with a `list-jobs` token, 403 without. This is the only
  Nomad call the job widget makes.
- **Trap: `GET /v1/jobs` cannot answer "is my job running".** Its
  `JobSummary.Summary.<group>.{Failed,Lost,Complete}` are **cumulative
  lifetime allocation counters, not current state**, and the endpoint carries
  no desired count at all (its full key set has `JobSummary` but nothing like
  `GroupCountSum`). Every job below is `Status: running` at its full desired
  count of 1 right now:

      grafana     Running=1 Failed=4  Lost=0 Complete=11
      haproxy     Running=1 Failed=8  Lost=0 Complete=28
      loki        Running=1 Failed=5  Lost=0 Complete=1
      memex       Running=1 Failed=31 Lost=0 Complete=35
      minio       Running=1 Failed=3  Lost=2 Complete=10
      phoenix     Running=1 Failed=15 Lost=2 Complete=10
      postgres    Running=1 Failed=6  Lost=0 Complete=6
      prometheus  Running=1 Failed=4  Lost=0 Complete=8

  A "`Failed > 0` means unhealthy" rule reds **8 of the 14 service jobs on a
  fully healthy cluster**. Add the three periodic and system jobs below and 11
  of 19 rows are wrong on day one. Health is judged from current allocations
  and never from these counters, and the counters are not rendered at all.
- **Trap: periodic parents have no allocations and no live children.** `acme`,
  `backup-minio` and `backup-postgres` each return `Allocs: null` (the JSON
  null, not an empty array), `ChildStatuses: []` and `GroupCountSum: 1` while
  being perfectly healthy. Nomad garbage-collects the child jobs, so `GET
  /v1/jobs?prefix=acme` returns the parent alone and `?include_children=true`
  adds nothing: there is **no last-child outcome to read** here. The parser
  must normalize `Allocs: null` to `[]` so a shared `len(job["Allocs"])` code
  path does not `TypeError`. A parent is healthy when `Status ==
  "running"` and `Stop == false`, and on nothing else. `ChildStatuses` being
  non-null is how the panel spots a parent: it is `null` on every `service`
  and `system` job and `[]` on all three parents.
- **Trap: `GroupCountSum` is per-node for `system` jobs.** `node-exporter` and
  `promtail` both report `GroupCountSum: 1` with **5** running allocs, one per
  node. A `system` job is healthy when its running alloc count equals the
  eligible node count, which the node widget already fetches.
- **Pagination.** `/v1/jobs/statuses` paginates. Today all 19 come back in one
  page, but the response sets `X-Nomad-Nexttoken` when they do not (verified
  with `?per_page=5`). Send no `per_page` and follow `X-Nomad-Nexttoken` while
  it is non-empty, or the panel silently under-reports the day this cluster
  outgrows a page.
- **Trap: `talat-shim` and `talat-consumer` run live but have no job file in
  this repo.** `grep -rl talat deployments/ applications/` returns nothing;
  `deployments/infrastructure/services/` holds 11 `.hcl` files and neither is
  among them. Anything driven off `deployments/` misses two live jobs. The
  panel reads the **API**, never the repo tree.
- **5 Nomad nodes**, all `Status: ready`, `SchedulingEligibility: eligible`,
  `Drain: false`: `firebat`, `orangepi4a`, `radxa-dragon-q6a`, `ubuntu`,
  `jetson-orin-nano`. `GET /v1/nodes` returns them in one call.
- **One Nomad server, `firebat` at 192.168.2.30, `bootstrap_expect = 1`, and
  it is also a client**
  (`bootstrap/roles/nomad_server/templates/nomad.hcl.j2:29-32`
  server block, `:49-59` client block). The edge proxy is pinned to it
  (`deployments/infrastructure/services/haproxy.hcl:5-9`). Single point of
  failure: firebat down means Nomad API, Vault, Consul and the edge all go at
  once. Nomad **2.0.4**.
- **Vault** at `http://192.168.2.30:8200`, unsealed today, shamir 3-of-5,
  **2.0.3**. Consul is **2.0.2**. The whole stack crossed a major version on
  2026-07-31 when unattended-upgrades restarted the services
  (`bootstrap/roles/nomad_server/templates/nomad.hcl.j2:18-22` records the
  incident;
  `.loop/archive/U1-upgrade-pin-hashistack-versions/plan.md:72-74`
  has the before-and-after). Every payload shape this plan depends on was
  re-probed against the 2.x cluster on 2026-07-31.
  **A sealed Vault after a reboot is the common real outage here** —
  the root justfile carries `unseal_vault` for exactly that
  (`justfile:33-34`, `scripts/unseal_vault.sh:1-13`).
- **`GET /v1/sys/seal-status` needs no token** (verified: HTTP 200 with no
  auth header). Seal state is therefore readable even when the CLI's token is
  dead — the one panel that always renders.
- **Nomad refuses unauthenticated reads**: `/v1/jobs/statuses` and `/v1/nodes`
  both return **403** with no token (verified 2026-07-31). ACL is on
  (`bootstrap/roles/nomad_server/templates/nomad.hcl.j2:45-47`).
- **Consul** at `http://192.168.2.30:8500`, 5 members, ACL
  `default_policy = "deny"`
  (`bootstrap/roles/consul_server/templates/consul.hcl.j2:25-33`,
  the `default_policy` line at `:27` and the `tokens` block at `:29-32`).
  But `GET /v1/health/state/any` returns **200 with no token** (verified, 41
  checks, 0 critical), because the agent's `tokens.default` is set to the
  agent token at `:31` — the agent authenticates tokenless HTTP calls as
  itself. Three probes separate the mechanism from "Consul is just open": the
  tokenless read is 200, the same read with a bogus token is 403, and
  tokenless `GET /v1/acl/tokens` is 403. Convenient today, fragile: it is a
  config side effect, not a grant. See Q7.
- **Failed allocations are usually already gone.** `GET /v1/allocations`
  returns 24 allocs, all `ClientStatus: running`. Nomad GCs dead allocs, so a
  dedicated "recent failures" panel is empty most of the time.

### Auth today
- Vault brokers cluster tokens: `vault read nomad/creds/deploy`
  (`deployments/infrastructure/nomad_deploy_role.tf:36-41`) and
  `vault read consul/creds/deploy`
  (`deployments/infrastructure/consul_deploy_role.tf:22-25`).
  F5 and F6 are `done` in the ledger; this brokering path works.
- **The existing `deploy` Nomad policy cannot drive this panel.** Its own
  comment says so: "no alloc-exec, no alloc-node-exec, no list-jobs /
  dispatch-job / read-logs / read-fs, and no node / agent / operator access"
  (`deployments/infrastructure/nomad_deploy_role.tf:1-12`); rules grant only
  `submit-job`, `read-job`, `host-volume-*`
  (`:17-29`). `/v1/jobs/statuses` needs `list-jobs`;
  `/v1/nodes` needs `node:read`. A token minted from `nomad/creds/deploy` gets
  403 on both.
- **The Nomad read token is `nomad/creds/manage`, brokered by D2.** D2 today
  brokers only `nomad/creds/deploy`; it needs to also broker
  `nomad/creds/manage` for the CLI to have a Nomad token that can list jobs
  and read nodes. The `manage` Vault role
  (`deployments/infrastructure/nomad_oidc.tf:74-78`, `type = "management"`)
  mints a Nomad **management** token, which bypasses ACLs entirely (list-jobs,
  read-job, node read — everything). The `developer` Vault policy already
  grants `nomad/creds/manage` read
  (`deployments/infrastructure/developer_group.tf:140`), so the grant exists.
  D2 shipped `nomad/creds/deploy` and `consul/creds/deploy` only
  (`cli/src/localstack_cli/auth/broker.py:25-26`), so brokering `manage` is a
  **change to a done ticket**: a new creds path in `broker.py`. This is a
  precondition relayed to D2 via the `relay-finding` skill, not a hard
  `depends_on` edge, because D2 is done and the change is small and local —
  but it is a real follow-up, not a no-op, and until it lands the Nomad widgets
  render "denied". **Recorded honestly**: a `management` token is full Nomad
  access, not read-only. Brokering it to a read-only TUI is a privilege
  widening the operator accepted over the rejected alternative (a narrow read
  policy). This replaces the old Q2 option (b) "author a narrow
  `nomad_read_role.tf`", which is now **rejected** in favor of D2 brokering
  `manage`. See Q2.

### Network reach
- ufw admits ports 4646, 8200 and 8500 from `192.168.0.0/16` **only**
  (`bootstrap/playbooks/configure_network.yml:13-25`). The tailnet
  `100.64.0.0/10` is allowed on port 22 alone (`:10-11`).
- **But every API this panel reads also answers over the HTTPS edge, and 443
  is open to both the LAN and the tailnet**
  (`deployments/infrastructure/services.tf:189-190`). haproxy routes `vault.`,
  `nomad.` and `consul.lab.orangecluster.nl`
  (`deployments/infrastructure/services/haproxy.hcl:98-107`). Probed
  from the devcontainer 2026-07-31:
  `https://vault.lab.orangecluster.nl/v1/sys/seal-status` 200 tokenless,
  `https://nomad.lab.orangecluster.nl/v1/jobs/statuses` 200 with a token,
  `https://consul.lab.orangecluster.nl/v1/health/state/any` 200 tokenless. All
  three with a valid certificate, no `-k`.
- **`N4-netsec-edge-only-service-access` closes the plaintext LAN ports and
  has priority 50 against this ticket's 42, so it runs first.** It narrows
  `from_ip` for 4646, 8200 and 8500
  (`.loop/plans/N4-netsec-edge-only-service-access.md:418`) and says outright
  that "the only route to Nomad's API becomes haproxy"
  (`.loop/plans/N4-netsec-edge-only-service-access.md:465`). The edge is what
  N4 keeps. Point the panel at the edge hostnames and it works before N4,
  after N4, on the LAN and on the tailnet. Point it at `192.168.2.30` and N4
  breaks it. See Q5 and Q6.

### What Grafana already does
- `docs/monitoring.md:12-15`: Grafana is the authenticated front door to
  Prometheus and Loki, both of which have no auth of their own.
- `docs/monitoring.md:48-56` names the three things Grafana does not give:
  scrape-failure text, the expression browser, Loki's raw HTTP API. **This
  panel adds none of those.** It is orthogonal: current control-plane state,
  not metrics.

## 5. Non-goals / out of scope

**The Grafana boundary is the scope constraint. A diff that crosses it is a
violation, not an improvement.**

- **No metrics.** No Prometheus queries, no PromQL, no `up{}`, no CPU/memory
  gauges. `docs/monitoring.md:12-15` already routes that through Grafana.
- **No charts, sparklines, or history of any kind.** Current state only. The
  panel has no memory across refreshes and no time axis.
- **No logs.** No Loki queries, no `nomad alloc logs`.
- **No alerting, notification, thresholds, or paging.**
- **No dashboard framework**: no configurable panels, no layouts, no saved
  views, no plugin surface. One screen, fixed.
- **No write actions.** No restart, stop, drain, unseal, or job submit from
  the TUI. Read-only. (`unseal_vault` stays a justfile recipe.)
- **No log tailing, alloc exec, or filesystem browsing.**
- Not a replacement for `nomad job status` / `vault status` / `consul
  members`. It condenses their headlines onto one screen.
- Does not create the `cli/` package (D1) or any login/token-broker code (D2).
- Does not change any Nomad job, Terraform root, or Ansible role. **No
  Terraform at all**: the Nomad read token comes from D2 brokering
  `nomad/creds/manage` (Q2), and the firewall belongs to N4 (Q5).
- Does not read `deployments/**` to enumerate jobs. See the `talat-*` trap.
- No JSON/`--output` mode, no non-interactive fallback, no web UI.

## 6. Requirements & restrictions

1. **The panel shows exactly four things.** Adding a fifth is scope creep and
   needs a new ticket:
   - **Vault seal state** — the most common real outage (`justfile:33-34`
     exists for it) and the only source readable without a token.
   - **Node status** — 5 rows: name, status, eligibility, drain. A job that
     will not place is usually a node that went away, and the single-server
     topology (`bootstrap/roles/nomad_server/templates/nomad.hcl.j2:29-32`)
     makes node loss consequential.
   - **Per-job allocation health** — 19 rows: name, type, status, and a
     current running-vs-desired count derived from `/v1/jobs/statuses`
     (`Allocs[].ClientStatus` against `GroupCountSum`). This is the "is my job
     running" answer and the reason the panel exists.
   - **Consul critical checks** — the count, and the failing checks only
     (never all 41). A Nomad alloc can be `running` while its Consul check is
     critical; nothing else on the screen shows that.
2. **Cut: a separate "recent failed allocations" panel.** Nomad GCs dead
   allocs (24 live, all running, verified), so the panel is empty most days
   and the data is gone by the time anyone looks. **`JobSummary.Failed`/`Lost`
   are not the reason for the cut** — they are lifetime counters and cannot
   answer "did something fail recently" at all. Recent-failure history is
   Grafana and Loki's job (`docs/monitoring.md:12-15`). Do not build it, and
   do not render the lifetime counters as a substitute.
3. **Enumerate jobs from the Nomad API, never from `deployments/`.** The
   `talat-*` jobs prove the repo tree is not the cluster.
4. **Job health is judged from current allocation status, never from
   cumulative counters.** No rule anywhere in this ticket reads
   `JobSummary.Failed`, `.Lost` or `.Complete`. The rules branch on job type,
   all three computed from one `/v1/jobs/statuses` response:
   - `service`: count `Allocs` with `ClientStatus == "running"` against
     `GroupCountSum`. Below it is degraded.
   - `system`: count running `Allocs` against the **eligible node count** from
     the node fetch. `GroupCountSum` is per-node here and is 1 while 5 allocs
     run.
   - `batch/periodic` parent (`ChildStatuses` non-null): healthy when
     `Status == "running"` and `Stop == false`. Its `Allocs` and
     `ChildStatuses` are both empty on a healthy cluster, so neither may feed
     the verdict.
5. **No source may block the UI.** Each of the four fetches runs
   independently with its own timeout; a slow or dead endpoint degrades its
   own panel and nothing else. A TUI that hangs on a dead Vault is worse than
   no TUI.
6. **Degraded states are first-class, not error handling.** Named, rendered,
   and snapshot-tested: token expired, Vault sealed, Nomad unreachable, Consul
   unreachable, permission denied (403), **stale** (a value kept past a
   timeout), and **no data yet** (the first fetch timed out, so there is
   nothing to keep). These are exactly when a developer opens the panel.
   **403 and token-expired are two states, not one.** A 403 names the
   capability the token lacks; an expired token tells the developer to run
   `localstack login`. Conflating them sends someone to re-login over a
   policy gap.
7. **Auth comes entirely from D2.** No token acquisition, no Vault login, no
   credential file reading, no env-var token fallback authored here. If D2's
   surface does not fit, that is `out-of-scope-fix-needed`, not a second login
   path.
8. **Addresses come entirely from D1's `config.py`, and the documented values
   are the HTTPS edge hostnames.** No address resolution, no defaults, and no
   config format authored here
   (`.loop/archive/D1-cli-package-skeleton/plan.md:188-191` owns it,
   reading `VAULT_ADDR`, `NOMAD_ADDR` and `CONSUL_HTTP_ADDR` and erroring by
   name when one is missing). Subticket 11 adds the three edge addresses
   `https://{vault,nomad,consul}.lab.orangecluster.nl` to
   `docs/monitoring.md`, which does not name them today, because those survive
   N4 and the plaintext LAN addresses do not.
9. **Secrets never printed.** No token value renders on screen or in a
   snapshot fixture. `detect-private-key` (`.pre-commit-config.yaml:12`) stays
   green.
10. **The fetch layer is `cli/src/localstack_cli/api/`, built under D3's
    contract**, and every widget takes its data through an injected callable.
    D3's contract requires `api/` to return dataclasses and import neither
    typer nor rich, so a TUI can consume it (D3's `cli/src/localstack_cli/api/`
    layer, the reuse contract D4 imports). Pickup order puts this ticket
    first, so this ticket creates those modules; D3 adds its own functions to
    them later. **No `cluster_api.py`, no second fetch module, no HTTP client
    under `tui/`.** See Q3.
11. **Dependencies via `uv add`**, never `uv pip`
    (`.claude/rules/uv-installer.md:6-8`). New deps: `textual`,
    `pytest-textual-snapshot`, `respx` (dev), and **`httpx` (runtime)**. D1
    built the CLI's existing HTTP on `urllib` (stdlib,
    `cli/src/localstack_cli/auth/vault.py:9-10`), and `cli/pyproject.toml:7-9`
    lists only `click`, `rich`, `typer` — `httpx` is NOT a CLI dependency
    today. The `requirements.txt:3` httpx entry serves the non-CLI scripts,
    not this package. The `api/` fetch layer uses `httpx.Timeout(2.0)`
    (`plan:779`) and the tests use `respx` (httpx-specific), so `httpx` must be
    added via `uv add httpx` as a runtime dep and `respx` via
    `uv add --dev respx`. Do not add `requests`.
12. **Every code change ships a test** (`.claude/rules/python-testing.md:6-10`).
13. **Live-cluster tests carry a marker and are excluded from the default run
    via `addopts`** (`.claude/rules/python-testing.md:26-32`). Default
    `uv run pytest` is offline and fast.
14. **Textual snapshots via `pytest-textual-snapshot`; refresh baselines only
    on a reviewed intentional change, never to clear a red test**
    (`.claude/rules/python-testing.md:112-117`).
15. **Mock HTTP with respx, not hand-rolled patches**
    (`.claude/rules/python-testing.md:89`).
16. **Plain language in every rendered string, comment and doc line**
    (`.claude/rules/plain-language.md`). Panel labels say "sealed", "no
    token", "unreachable" — not "degraded telemetry posture".
17. **Adversarial review before done** (`.claude/rules/adversarial-reviews.md`).
18. **Pre-existing failures get fixed, not skipped**
    (`.claude/rules/pre-existing-issues.md`).

## 7. Code surface

**The package root is `cli/src/localstack_cli/`, D1's layout
(`.loop/archive/D1-cli-package-skeleton/plan.md:167-191`). The `api/`
sub-package is D3's contract (D3's `cli/src/localstack_cli/api/` layer, the
reuse contract D4 imports), and this ticket builds it because pickup order
puts D4 ahead of D3. Read the existing `cli/` tree before writing: if D1
shipped a different root, keep the shape and change the prefix. There is no
Terraform in this ticket.**

New, under `api/` (D3's contract: dataclasses out, no typer, no rich, no
Textual, addresses from D1's `config.py`, no literal host or port):
- `cli/src/localstack_cli/api/errors.py` — `NotAuthenticated`,
  `MissingCapability`, `NotFound`, `Unreachable`, `Timeout`, each carrying the
  service name. D3 extends this file; do not fork it.
- `cli/src/localstack_cli/api/nomad.py` — `job_statuses()` over
  `GET /v1/jobs/statuses`, following `X-Nomad-Nexttoken` while it is
  non-empty, and `list_nodes()` over `GET /v1/nodes`. Both return dataclasses
  and map 403 to `MissingCapability` naming `list-jobs` or `node:read`. D3
  later adds `list_jobs()`, `get_job()` and `job_templates()` here.
- `cli/src/localstack_cli/api/vault.py` — `seal_status()` over
  `GET /v1/sys/seal-status`, no token. D3 later adds `health()` and the policy
  readers.
- `cli/src/localstack_cli/api/consul.py` — `list_checks()` over
  `GET /v1/health/state/any`, tokenless per Q7, returning every check so the
  widget filters. D3 later adds its own service calls.
- `cli/src/localstack_cli/api/health.py` — the job-health rules from
  requirement 4, pure functions over the `api/nomad.py` dataclasses plus the
  eligible node count. Pure so the rule table is a unit test, not a snapshot.

New, under `tui/` (imports `api/`, never `httpx`):
- `cli/src/localstack_cli/tui/monitor.py` — the Textual `App`: one screen,
  four widgets, `set_interval(5, ...)`, four `@work(group=..., exclusive=True)`
  fetch workers, the keybindings (`q` quit, `r` refresh now).
- `cli/src/localstack_cli/tui/widgets.py` — the four widgets. Each takes a
  fetch result (data or a named degraded state) and renders it. No I/O here.

New tests (each listed here in section 7 and detailed in section 8):
- `cli/tests/test_api_nomad.py`, `test_api_vault.py`, `test_api_consul.py` —
  respx tests per fetcher: happy path against a captured fixture, 403,
  timeout, connection error, and the `X-Nomad-Nexttoken` second page.
- `cli/tests/test_health_rules.py` — the parametrized rule table from
  requirement 4, including the healthy-job-with-lifetime-counters case.
- `cli/tests/test_monitor_tui.py` — `pytest-textual-snapshot` tests: healthy
  cluster, Vault sealed, Nomad 403, expired token, Nomad unreachable, Nomad
  slow (stale), Nomad slow from cold (no data yet), and one `service` job
  genuinely below its desired count.
- `cli/tests/fixtures/cluster/*.json` — payloads captured from the live
  cluster (`/v1/jobs/statuses`, `/v1/nodes`, `/v1/sys/seal-status`,
  `/v1/health/state/any`), with tokens, node IDs and alloc IDs stripped. The
  snapshot tests' only input.
- `cli/tests/__snapshots__/` — pytest-textual-snapshot baselines (generated).

Modified:
- `cli/pyproject.toml` (D1's) — `uv add textual` and **`uv add httpx`**
  (runtime; D1 built on `urllib`, so httpx is new to the CLI package); dev
  deps `pytest-textual-snapshot`, `respx` via `uv add --dev`; register the
  `cluster` marker and exclude it in `addopts` per
  `.claude/rules/python-testing.md:26-32`.
- `cli/src/localstack_cli/main.py` (D1's typer app) — register **`monitor`**.
  The name `status` belongs to D3.
- `docs/monitoring.md` — one short section: what `localstack monitor` shows,
  what it deliberately does not (pointing at `:48-56`'s existing boundary
  discussion), and the three edge addresses from requirement 8. Do not
  restructure the doc.

## 8. Tests & validation gates

### Repo gates (discovered, not assumed)
- **`just pre_commit`** → all Passed. This is the loop's configured gate
  (`.loop/config.json` `gates`). It runs `pre-commit run --all-files`
  (`justfile:18-19`) over `.pre-commit-config.yaml`. Beyond the `check-json`,
  `check-ast`, `check-merge-conflict`, `check-yaml`, `debug-statements`,
  `detect-private-key`, `end-of-file-fixer`, `nomad fmt`, `terraform fmt
  -check`, and `scripts/tf_validate.sh` hooks, D1 landed `ruff`, `ruff-format`,
  `mypy` (strict, `--config-file cli/pyproject.toml`) and `pytest` scoped to
  `^cli/` (`.pre-commit-config.yaml:37-72`). These run on this ticket's code.
- **`uv run --project cli pytest`** from the repo root → green, offline, no
  live-cluster tests.
- **There is no CI for these gates.** `.github/workflows/` holds only
  `claude-ollama.yaml` and `hermes-interactive.yaml`, both agent runners.
  Gates are local; run them.
- **No Terraform runs here.** This ticket touches no `.tf` file, so the
  `terraform fmt -check` and `tf_validate.sh` hooks have nothing new to see.
  Worktree prerequisite for the gate: `just worktree_setup <path>`
  (`justfile:41-42`).
- Adversarial review (`.claude/rules/adversarial-reviews.md`).

### How snapshot tests get deterministic input
The data source is a live cluster, so it never touches a test. Three layers:
1. Capture real payloads once into `cli/tests/fixtures/cluster/*.json` (strip
   tokens, node and alloc IDs, and any timestamp the render displays).
   **Capture the whole 19-job `/v1/jobs/statuses` response**, not a hand-picked
   subset, so the fixture cannot encode a tidier world than the real one.
   Note that `/v1/jobs/statuses` elements carry **no `JobSummary` key at all**
   (verified: the key set is `Allocs ChildStatuses Datacenters GroupCountSum
   ID IsPack LatestDeployment ModifyIndex Name Namespace NodePool ParentID
   Priority Status Stop SubmitTime Type Version`). The lifetime counters are
   structurally absent from the panel's data source, which is the strongest
   protection against reading them, and the reason no fixture here needs to
   carry them.
2. Widget tests take fixtures through the injected fetch callable
   (requirement 10). **No HTTP at all** in the snapshot tests.
3. Fetcher tests serve those same fixtures over respx
   (`.claude/rules/python-testing.md:89`), so the parsing layer is exercised
   against real payload shapes without a network.

Anything that varies per run must be excluded from the render or frozen: no
`SubmitTime` deltas, no "updated 3s ago", no wall-clock strings. If a relative
timestamp is wanted, inject the clock.

### Tests to add (each file listed in section 7)
`cli/tests/test_api_*.py`:
- Per fetcher: 200 happy path against a captured fixture.
- Nomad 403 → `MissingCapability` naming `list-jobs` or `node:read`, not an
  exception escaping the layer. (The verified behavior of an expired or
  under-scoped token.)
- Connection refused → `Unreachable`; slow response → `Timeout`.
- Vault `sealed: true` payload → sealed state.
- `/v1/jobs/statuses` served in two pages with `X-Nomad-Nexttoken` on the
  first → all jobs returned. A single-page implementation fails this.
- Consul health filtered to critical only; 0 critical renders as fine.

`cli/tests/test_health_rules.py`, parametrized:
- **The three jobs whose lifetime counters are loudest render healthy.**
  `memex`, `phoenix` and `haproxy` at `GroupCountSum: 1` with one `running`
  alloc each, from the live `/v1/jobs/statuses` capture. Their `/v1/jobs`
  counters (`memex` `Failed: 31`; `phoenix` `Failed: 15, Lost: 2`; `haproxy`
  `Failed: 8`) are what the old model would have reded them on, and they are
  named here so a reader can check the claim, not because the fixture carries
  them.
- `acme` (periodic parent, `Allocs: null` normalized to `[]`,
  `ChildStatuses: []`) is **healthy** on `Status == "running"` and `Stop ==
  false`.
- `node-exporter` (system, `GroupCountSum: 1`, 5 running allocs) is healthy at
  running == eligible-node count, and degraded at 4 of 5.
- A `service` job with fewer `running` allocs than `GroupCountSum` is
  degraded. This is the only way a service job goes red.
- **The counters cannot enter the panel.** Two assertions, since the fixture
  cannot carry them: `grep -rn "JobSummary\|/v1/jobs\b" cli/src/localstack_cli/`
  returns nothing, and a fixture with a `JobSummary` block bolted onto a
  statuses element yields the same verdict as one without it.

`cli/tests/test_monitor_tui.py` (snapshots):
- Healthy cluster (all four panels green), from the full 19-job fixture.
- Vault sealed, everything else fine.
- Nomad 403 — job and node panels name the denied capability, Vault and Consul
  panels still render.
- Expired token — a **different** render, pointing at `localstack login`.
  Vault and Consul still render. **This is the token-expired requirement,
  tested, and it is not the 403 case.**
- Nomad unreachable — the same panels show "unreachable" naming the endpoint,
  others still render.
- Nomad slow — one good response, then a response past the 2s timeout: the
  panel keeps its last value marked stale.
- Nomad slow from cold — the first fetch times out, so there is no value to
  keep: the panel renders "no data yet", not a fake-empty table.
- One `service` job genuinely below its desired count — the failure is visible
  without scrolling.

Live-cluster smoke test, marked and excluded from the default run
(`.claude/rules/python-testing.md:26-32`): one test that hits the real cluster
and asserts each fetcher returns parseable data. Run on purpose with `-m`.

## 9. Risk assessment

- **Blast radius: zero for the cluster.** Read-only HTTP GETs against three
  APIs. No Terraform, no Ansible, no job change. The panel cannot alter
  cluster state.
- **Reversibility: high.** Delete the `monitor` command and the `tui/`
  package; nothing else depends on them. `api/` stays, because D3 needs it.
- **Likeliest failure mode: the panel lies about job health.** Reading
  `JobSummary.Failed`/`Lost` as current state reds 8 of the 14 service jobs on
  a fully healthy cluster (measured, section 4). Add the periodic and system
  jobs and 11 of 19 rows are wrong. A panel that cries wolf on more than half
  the cluster is worse than no panel, because a developer stops trusting it
  and then misses the real outage. Requirement 4 and the
  `test_health_rules.py` table exist for exactly this, and the fixture is
  captured from the live cluster so it carries the loud counters rather than a
  tidied-up copy. **This is the single biggest risk in the ticket.**
- **Second: the token cannot read what the panel needs.** `nomad/creds/deploy`
  explicitly lacks `list-jobs` and node read
  (`deployments/infrastructure/nomad_deploy_role.tf:1-12`). D2 must broker
  `nomad/creds/manage` for the panel to get a Nomad token that can list jobs
  and read nodes. The grant already exists via the `developer` policy
  (`deployments/infrastructure/developer_group.tf:140`); D2 just needs to
  relay it. This is a precondition, relayed to D2, not a hard edge. A
  `management` token is full Nomad access, not read-only — the operator
  accepted this widening over the rejected narrow read policy.
- **Third: the UI hangs.** A synchronous fetch in the render path against a
  sealed Vault or a downed firebat freezes the whole screen at the exact
  moment it is needed. Requirement 5 exists for this; the snapshot tests for
  unreachable and slow states are what prove it.
- **Fourth: N4 moves the addresses under the panel.** N4 has priority 50
  against this ticket's 42 and closes 4646, 8200 and 8500 to the LAN
  (`.loop/plans/N4-netsec-edge-only-service-access.md:418`). Requirement 8 is
  the mitigation: addresses come from D1's `config.py` and the documented
  values are the edge hostnames, which are verified working today and are the
  route N4 keeps
  (`.loop/plans/N4-netsec-edge-only-service-access.md:465`). A hardcoded
  `192.168.2.30` anywhere in this ticket is a review failure.
- **Scope drift toward Grafana.** The panel is one refactor away from "well,
  we could also chart that". The non-goals section is the guardrail; a diff
  importing a Prometheus client is a review failure.
- **Snapshot brittleness.** Textual snapshots break on terminal size, theme,
  and library version. Textual **8.2.8** is what resolves today and carries
  the `@work(group=, exclusive=, thread=)` decorator and `App.set_interval`
  the refresh contract needs. Pin it and set a fixed terminal size in the
  tests, or every unrelated dependency bump reds the suite and invites the
  forbidden `--snapshot-update` reflex.
- **Dependency risk is real, not nominal.** D1 and D2 are `done`; `cli/`
  ships and D2 brokers `nomad/creds/deploy` and `consul/creds/deploy`
  (`cli/src/localstack_cli/auth/broker.py:25-26`). What does not exist yet is
  the D2 brokering of `nomad/creds/manage`, which this ticket needs. That is
  a relayed finding to D2, not a hard edge: until it lands the Nomad widgets
  render "denied".

## 10. Subtickets (ordered)

1. Read D1's `cli/` tree and D2's token surface. Confirm the package root, the
   typer app's registration point, and the fetch-credential call, then fix the
   section 7 anchors against what actually shipped.
2. `api/errors.py`, `api/nomad.py`, `api/vault.py`, `api/consul.py` under D3's
   contract: dataclasses out, no typer, no rich, no Textual, addresses from
   D1's `config.py`, per-source timeouts, named failure states. Includes
   `X-Nomad-Nexttoken` paging.
3. `api/health.py`: the requirement 4 rules as pure functions.
4. Capture live payloads into `cli/tests/fixtures/cluster/`, scrubbed, all 19
   jobs including the ones with loud lifetime counters.
5. `test_api_*.py` with respx and `test_health_rules.py` with the full rule
   table. Green before any UI exists.
6. The four widgets, data injected, no I/O.
7. The `App`: layout, `set_interval(5, ...)`, four exclusive workers with 2s
   timeouts, `q`/`r` keys.
8. Snapshot tests for the healthy case and all five degraded cases. Review
   each baseline before committing it.
9. Register the **`monitor`** subcommand in D1's typer app.
10. Run it against the real cluster over the edge hostnames. Deliberately seal
    Vault, revoke the token, and block Nomad, and confirm the panel degrades
    as snapshot-tested rather than hanging.
11. `docs/monitoring.md` section: the Grafana boundary and the three edge
    addresses.
12. `just pre_commit` and `uv run pytest`, then adversarial review.

## 11. Open questions

> **This section is history, kept for the reasoning. Every question was
> resolved on 2026-07-31 and re-resolved after the plan review; the
> resolutions live in `## Forks resolved, 2026-07-31` at the end of this plan
> and they win wherever they disagree with a recommendation below.** Four
> recommendations were overturned outright: **Q2** (the read token is D2
> brokering `nomad/creds/manage`, not this ticket's), **Q3** (this ticket
> builds `api/` because it is picked before D3, and `cluster_api.py` is never
> created), **Q5** and **Q6** (the panel goes over the HTTPS edge, not the
> plaintext LAN addresses, because N4 closes those ports first). Do not act
> on the recommendation text below.


- **Q1 — D1 and D2 do not exist as tickets.** *(Historical, 2026-07-30.)* Both
  are now `done`: `cli/` ships and D2 brokers tokens. `depends_on =
  ["D2-cli-login-broker-tokens", "F11-foundation-human-read-role"]` resolves.
  See `## Forks resolved, 2026-07-31` for the current dependency posture.

- **Q2 — Which Nomad token does the panel use, and who creates its policy?**
  The existing `deploy` role cannot list jobs or read nodes
  (`deployments/infrastructure/nomad_deploy_role.tf:1-12`, `:17-29`), so a
  `nomad/creds/deploy` token yields 403 on the panel's two main widgets. **Resolved
  2026-07-31: D2 brokers `nomad/creds/manage`** (a Nomad management token, full ACL
  bypass; the `developer` policy already grants the read at
  `deployments/infrastructure/developer_group.tf:140`, the `manage` role is at
  `deployments/infrastructure/nomad_oidc.tf:74-78`). Option (b), a narrow
  `nomad_read_role.tf`, is **rejected** — it duplicates ownership and the operator
  accepted the management token's wider scope. Reject (c): a panel whose headline
  widgets say "denied" is not worth shipping. The trade-off — brokering a
  management token to a read-only TUI is a privilege widening — is recorded
  plainly in `## Forks resolved, 2026-07-31`.

- **Q3 — Does this reuse D3's data-fetching layer?** D3 is also unwritten, so
  its shape is unknown. *Recommendation:* build `cluster_api.py` here as the
  single fetch module, keep it free of any Textual import, and keep every
  widget on injected data (requirement 9). Then whichever ticket lands second
  imports the first one's module and deletes its own — a one-file change, not
  a rewrite. Explicitly: **do not** speculatively generalize it for a D3 that
  may never exist. If D3 lands first, this ticket imports it and
  `cluster_api.py` is never created.

- **Q4 — Refresh: how often, and live or manual?** *Recommendation:* live,
  polling every **5 seconds**, with `r` to force a refresh now. Each source
  fetched independently in a Textual worker with a **2-second** timeout, so
  one dead endpoint never delays the others and never blocks the render. A
  timed-out panel keeps its last value, marked stale, rather than blanking. 5s
  against a 5-node home cluster is negligible load (one `/v1/jobs/statuses`,
  one `/v1/nodes`, one seal-status, one health call). If the operator prefers
  manual-only, the same structure supports it by setting the interval to 0.

- **Q5 — Does the panel need to work from off-LAN?** ufw admits 4646/8200/8500
  from `192.168.0.0/16` only; the tailnet gets port 22 alone
  (`bootstrap/playbooks/configure_network.yml:13-25`). So a developer on
  tailscale but off the LAN cannot reach these APIs directly today.
  *Recommendation:* scope this ticket to on-LAN use and make the failure
  legible — "unreachable" plus a one-line hint about the SSH hop, not a stack
  trace. Opening 4646/8200/8500 to `100.64.0.0/10` is a firewall decision with
  its own blast radius and belongs in a separate ticket, not smuggled in here.

- **Q6 — Where does the panel read its endpoint addresses from?** Today the
  shell carries `NOMAD_ADDR`, `VAULT_ADDR`, `CONSUL_HTTP_ADDR` (all pointing
  at `192.168.2.30`), and Terraform hardcodes `192.168.2.30:8500`
  (`deployments/infrastructure/services.tf:338`). *Recommendation:* read the
  standard env vars, fall back to the `192.168.2.30` defaults, and let D1's
  config file override if D1 created one. Do not invent a config format here.

- **Q7 — Does a Consul token get brokered too?** Consul health reads work
  tokenless today only because `tokens.default` is set to the agent token
  (`bootstrap/roles/consul_server/templates/consul.hcl.j2:29-32`) despite
  `default_policy = "deny"` at `:27`. *Recommendation:* rely on the tokenless
  read for now and note the dependency in a code comment, since D2 brokering a
  Consul token for a read that needs none is unearned work. If that config
  ever tightens, the panel's Consul widget degrades to "denied" like any
  other source, which is the designed behavior rather than a crash.

## Premises / assumptions

- **P1.** `/v1/jobs` `JobSummary.Summary.<group>.{Failed,Lost,Complete}` are
  cumulative lifetime allocation counters, not current state. `probe:` live
  2026-07-31, 8 of 14 healthy service jobs carry `Failed > 0` while running at
  full desired count (section 4). `GET /v1/jobs` key set verified: carries
  `JobSummary` but no `GroupCountSum`.
- **P2.** `/v1/jobs/statuses` returns current state in one call:
  `GroupCountSum` (desired), `Allocs[].ClientStatus` (current running),
  `ChildStatuses` (periodic), `LatestDeployment.Status`, `Type`, `Status`,
  `Stop`, `ParentID`. `probe:` live 2026-07-31, 200 with a list-jobs token,
  403 without.
- **P3.** Periodic parents (`acme`, `backup-minio`, `backup-postgres`) report
  `Allocs: null` (JSON null, not `[]`), `ChildStatuses: []`, `Running: 0`
  while healthy. `probe:` live 2026-08-03. The parser normalizes `null` to
  `[]`. A parent is healthy on `Status == "running"` and `Stop == false`
  alone.
- **P4.** `GroupCountSum` is per-node for `system` jobs. `node-exporter` and
  `promtail` report `GroupCountSum: 1` with 5 running allocs. `probe:` live
  2026-07-31.
- **P5.** Tokenless Consul reads work via `tokens.default` set to the agent
  token (`bootstrap/roles/consul_server/templates/consul.hcl.j2:29-32`).
  `probe:` tokenless `GET /v1/health/state/any` is 200 with 41 checks; same
  call with a bogus token is 403; tokenless `GET /v1/acl/tokens` is 403. Probed
  live 2026-07-31.
- **P6.** Vault `GET /v1/sys/seal-status` returns 200 with no auth header.
  Nomad `GET /v1/jobs/statuses` and `GET /v1/nodes` return 403 tokenless. ACL
  is on (`bootstrap/roles/nomad_server/templates/nomad.hcl.j2:45-47`).
  `probe:` live 2026-07-31.
- **P7.** `nomad/creds/deploy` lacks `list-jobs` and node read
  (`deployments/infrastructure/nomad_deploy_role.tf:1-12`, `:17-29`), so the
  panel's `GET /v1/jobs/statuses` and `GET /v1/nodes` are 403 under it. D2
  must broker `nomad/creds/manage` instead. The `manage` Vault role
  (`deployments/infrastructure/nomad_oidc.tf:74-78`) mints a Nomad management
  token. The `developer` policy already grants `nomad/creds/manage` read
  (`deployments/infrastructure/developer_group.tf:140`), so D2 just needs to
  relay it. `anchor:` a management token is full Nomad access, not read-only;
  the operator accepted this widening.
- **P8.** N4 (`N4-netsec-edge-only-service-access`) will close direct LAN
  access to ports 4646, 8200 and 8500
  (`.loop/plans/N4-netsec-edge-only-service-access.md:418`, `:465`). N4 has
  priority 50 against this ticket's 42, so it runs first. `anchor:` the HTTPS
  edge (port 443) survives N4 and works on both LAN and tailnet today
  (`deployments/infrastructure/services.tf:189-190`).
- **P9.** The HTTPS edge routes `vault.`, `nomad.` and
  `consul.lab.orangecluster.nl`
  (`deployments/infrastructure/services/haproxy.hcl:98-107`). `probe:` all
  three answer correctly over TLS with valid certificates (probed 2026-07-31).
- **P10.** The cluster runs Nomad 2.0.4, Vault 2.0.3, Consul 2.0.2 (crossed a
  major version on 2026-07-31 via unattended-upgrades,
  `bootstrap/roles/nomad_server/templates/nomad.hcl.j2:18-22`). `probe:`
  every payload shape this plan depends on was re-probed against the 2.x
  cluster.
- **P11.** Pickup order puts D4 (priority 42) ahead of D3 (priority 20). The
  harness sorts on `-priority` when neither ticket depends on the other. D4
  therefore builds the `api/` layer under D3's contract; D3 adds its functions
  later. `anchor:` `.loop/ledger.json:892` carries D4 priority 42;
  `.loop/ledger.json:842` carries D3 priority 20.
- **P12.** D1 establishes `cli/src/localstack_cli/` as the package root
  (`.loop/archive/D1-cli-package-skeleton/plan.md:167-191`). `anchor:` this
  ticket writes to that path.
- **P13.** Repo gates are `just pre_commit`
  (`.loop/config.json` `gates`; `justfile:18-19`), running
  `.pre-commit-config.yaml`. `anchor:` D1 landed `ruff`, `ruff-format`,
  `mypy` (strict) and `pytest` hooks scoped to `^cli/`
  (`.pre-commit-config.yaml:37-72`); they run on this ticket's code. No CI for
  these gates; they are local.

## Renamed, 2026-07-31

`localstack status` becomes **`localstack monitor`**, per the operator's
command-surface decision. The name `status` moves to D3, as the one-shot,
scriptable renderer of the same data.

Two commands, two renderers, one `api/` layer:

- `localstack status` prints once and exits. Pipe it, script it, use it in a
  health check.
- `localstack monitor` is this ticket: the live Textual panel you leave open.

The four widgets and the independent polling so one dead source degrades one
panel both stand. The shared `api/` layer stands too, but this ticket now
**builds** it rather than importing it, because pickup order puts D4 before
D3 (Q3).

The eval marker's signature was cleared for the rename. No row's rigor
changed, only the command each row launches.

## Forks resolved, 2026-07-31

- **Q1 → resolved, dependency satisfied.** `D1-cli-package-skeleton` and
  `D2-cli-login-broker-tokens` are both `done`; `cli/` ships and D2 brokers
  tokens. The `depends_on` edge was never weakened and is now met. D1 settled
  the package root at `cli/src/localstack_cli/`, which section 7 uses.
- **Q2 → none of (a), (b) or (c). D2 brokers `nomad/creds/manage`.** The
  question offered three homes for a read-capable Nomad role and all three are
  worse than the fourth. D2 carries a guardrail forbidding it from authoring
  Terraform, D3 needs the same token for `status` and `service`, and reusing
  `deploy` ships a panel whose headline widgets say "denied". **The operator
  decided: D2 brokers `nomad/creds/manage`**, giving the CLI a Nomad management
  token that can list jobs and read nodes. The `manage` Vault role
  (`deployments/infrastructure/nomad_oidc.tf:74-78`, `type = "management"`)
  mints a Nomad management token, which bypasses ACLs entirely. The
  `developer` policy already grants `nomad/creds/manage` read
  (`deployments/infrastructure/developer_group.tf:140`), so the grant exists;
  D2 just needs to broker it. **Recorded honestly**: a management token is
  full Nomad access, not read-only. Brokering it to a read-only TUI is a
  privilege widening the operator accepted over the rejected alternative (a
  narrow read policy). The old option (b) "author a narrow
  `nomad_read_role.tf`" is **rejected**. This is a precondition relayed to D2,
  not a hard `depends_on` edge — D2 is done and brokering `manage` is a small
  but real follow-up to its `broker.py` (a new creds path), not a no-op. The
  posture is the same the plan already used for preconditions: D4 waits on D2
  brokering manage.
- **Q3 → this ticket builds `api/` under D3's contract, because it is picked
  first.** The earlier resolution assumed D3 would land first. It will not.
  `priority` is a soft ordering preference where higher runs sooner, and the
  pick order sorts on `-priority`. D4 is **42**, D3 is **20**, neither depends
  on the other, so the harness picks **D4 first**. So: create
  `cli/src/localstack_cli/api/{errors,nomad,vault,consul,health}.py` with only
  the functions this panel needs, obeying D3's contract exactly — dataclasses
  out, no typer, no rich, addresses from D1's `config.py`, no literal host or
  port (D3's `cli/src/localstack_cli/api/` layer, the reuse contract D4
  imports). D3 then adds `list_jobs()`, `get_job()`, `job_templates()` and its
  own modules to the same package. **`cluster_api.py` is never created**, and
  there is no second HTTP client under `tui/`. Two fetch layers means two places
  where a 403 is classified, and they will disagree.
- **Q4 → live, 5-second poll, `r` to force, 2-second per-source timeout.** A
  timed-out panel keeps its last value marked stale rather than blanking.
  Textual 8.2.8 supports the mechanism directly: `App.set_interval` plus four
  `@work(group=..., exclusive=True)` workers, each with an `httpx.Timeout(2.0)`.
  **The load argument holds only because the job widget is one call.** Four
  calls every 5 seconds against a five-node cluster is negligible;
  `/v1/jobs` plus a `/v1/job/<id>` per job would be 15 calls per refresh, and
  that is the second reason the data source is `/v1/jobs/statuses`.
- **Q5 → over the HTTPS edge, which works on-LAN and on the tailnet.** The
  earlier resolution scoped the panel to the LAN and reasoned from a firewall
  `N4-netsec-edge-only-service-access` removes. N4 has priority 50 against
  D4's 42, so it runs first, and it narrows 4646, 8200 and 8500 away from
  `192.168.0.0/16`
  (`.loop/plans/N4-netsec-edge-only-service-access.md:418`) leaving haproxy
  as the only route
  (`.loop/plans/N4-netsec-edge-only-service-access.md:465`). But 443 is
  already open to both the LAN and the tailnet
  (`deployments/infrastructure/services.tf:189-190`), haproxy already routes
  `vault.`, `nomad.` and `consul.lab.orangecluster.nl`
  (`deployments/infrastructure/services/haproxy.hcl:98-107`), and all three
  answer correctly over TLS today (probed 2026-07-31). Pointing the panel at
  the edge makes off-LAN work rather than degrade, and makes N4 a no-op for
  this ticket. No firewall change is smuggled in here; none is needed.
- **Q6 → addresses come from D1's `config.py`, and the documented values are
  the edge hostnames.** D1 owns resolution: three env vars, an error naming
  the missing one, no defaults
  (`.loop/archive/D1-cli-package-skeleton/plan.md:188-191`). This ticket
  invents nothing and hardcodes nothing, which is also what keeps N4's address
  move off its surface. `localstack config` (D2 R13) prints what got resolved,
  so a panel saying "unreachable" is diagnosable in one command.
- **Q7 → rely on the tokenless Consul read, and comment why.** The strongest
  premise in this plan, and it survived the review. It works only because
  `tokens.default` is set to the agent token
  (`bootstrap/roles/consul_server/templates/consul.hcl.j2:29-32`) despite
  `default_policy = "deny"` (`:27`). Three probes pin the mechanism: tokenless
  `GET /v1/health/state/any` is 200 with 41 checks and 0 critical, the same
  call with a bogus token is 403, and tokenless `GET /v1/acl/tokens` is 403.
  So the default identity is the agent policy, not management. Brokering a
  Consul token for a read that needs none is unearned. If that config
  tightens, the Consul widget degrades to "denied" like any other source,
  which is the designed behavior.