---
epic = "cli"
depends_on = ["D2-cli-login-broker-tokens"]
priority = 42
tags = ["cli", "textual", "tui", "observability"]
summary = "A Textual `localstack status` panel showing Vault seal state, Nomad node status, per-job allocation health, and Consul critical checks. A developer's glance-check, not a Grafana replacement: no dashboards, no history, no alerting. Each source polls independently so a sealed Vault or a dead endpoint degrades one panel instead of hanging the UI."
---

# D4 — Cluster overview TUI in the `localstack` CLI

## Title
Add a Textual TUI (`localstack status`) that answers "is the cluster fine and
is my job running" in one screen, using the tokens D2 brokers.

## Size / Effort
**Medium.** Four data sources, one screen, four widgets. The cost is not the
rendering: it is (a) deterministic snapshot tests against a live-cluster data
source, (b) degraded-state handling that must be designed in rather than
bolted on, and (c) the Nomad read policy gap in Q2.

## Triggered by
Operator, 2026-07-30, quoted: **"not a Grafana replacement but a panel for
developers"**. Grafana, Prometheus and Loki already run here
(`docs/monitoring.md:1-27`). Reaching them means opening a browser and logging
in. The missing thing is a terminal glance.

## Context (today's state)

### The CLI does not exist yet
- No `pyproject.toml` anywhere in the repo (verified 2026-07-30 by `find`).
  No `cli/` directory. Python deps today are a bare `requirements.txt:1-5`
  (`duckdb`, `pendulum`, `httpx`, `ipykernel`, `hvac`) used by
  `applications/data_lake/`, not by a packaged CLI.
- D1 creates the `cli/` package; D2 adds login and token brokering. **Both are
  unwritten** — no `D1-*` or `D2-*` slug exists in `.loop/plans/` or
  `.loop/ledger.json` (verified). See Q1.

### The cluster this panel reports on (all measured 2026-07-30)
- **19 Nomad jobs**, mixed types: `acme`, `backup-minio`, `backup-postgres`
  (`batch/periodic`); `node-exporter`, `promtail` (`system`); the other 14
  `service`. `GET /v1/jobs` returns all 19 in one call, each with
  `JobSummary.Summary.<group>.{Running,Failed,Lost,Queued,Starting}`, plus
  `Type`, `Periodic`, `Status`.
- **Trap: periodic parents report `Running: 0`.** `acme` returns
  `Summary.acme.Running == 0` and `Children: {Dead: 10, Pending: 0, Running:
  0}` while being perfectly healthy. A naive "Running == 0 means broken" rule
  falsely reds 3 of 19 jobs. Periodic and `system` jobs need different health
  rules from `service` jobs.
- **Trap: `talat-shim` and `talat-consumer` run live but have no job file in
  this repo.** `grep -rl talat deployments/ applications/` returns nothing;
  `deployments/infrastructure/services/` holds 11 `.hcl` files and neither is
  among them. Anything driven off `deployments/` misses two live jobs. The
  panel reads the **API**, never the repo tree.
- **5 Nomad nodes**, all `Status: ready`, `SchedulingEligibility: eligible`,
  `Drain: false`: `firebat`, `orangepi4a`, `radxa-dragon-q6a`, `ubuntu`,
  `jetson-orin-nano`. `GET /v1/nodes` returns them in one call.
- **One Nomad server, `firebat` at 192.168.2.30, `bootstrap_expect = 1`, and
  it is also a client** (`bootstrap/roles/nomad_server/templates/nomad.hcl.j2:11-14`
  server block, `:20-30` client block). The edge proxy is pinned to it
  (`deployments/infrastructure/services/haproxy.hcl:5-9`). Single point of
  failure: firebat down means Nomad API, Vault, Consul and the edge all go at
  once. Build 1.11.3.
- **Vault** at `http://192.168.2.30:8200`, unsealed today, shamir 3-of-5,
  v1.21.4. **A sealed Vault after a reboot is the common real outage here** —
  the root justfile carries `unseal_vault` for exactly that
  (`justfile:22-23`, `scripts/unseal_vault.sh:1-13`).
- **`GET /v1/sys/seal-status` needs no token** (verified: HTTP 200 with no
  auth header). Seal state is therefore readable even when the CLI's token is
  dead — the one panel that always renders.
- **Nomad refuses unauthenticated reads**: `GET /v1/jobs` and `GET /v1/nodes`
  both return **403** with no token (verified). ACL is on
  (`bootstrap/roles/nomad_server/templates/nomad.hcl.j2:16-18`).
- **Consul** at `http://192.168.2.30:8500`, 5 members, ACL
  `default_policy = "deny"` (`bootstrap/roles/consul_server/templates/consul.hcl.j2:25-33`).
  But `GET /v1/health/state/any` returns **200 with no token** (verified, 41
  checks, 0 critical), because the agent's `tokens.default` is set to the
  agent token at `:31` — the agent authenticates tokenless HTTP calls as
  itself. Convenient today, fragile: it is a config side effect, not a grant.
- **Failed allocations are usually already gone.** `GET /v1/allocations`
  returns 24 allocs, all `ClientStatus: running`. Nomad GCs dead allocs, so a
  dedicated "recent failures" panel is empty most of the time.

### Auth today
- Vault brokers cluster tokens: `vault read nomad/creds/deploy`
  (`deployments/infrastructure/nomad_deploy_role.tf:32-41`) and
  `vault read consul/creds/deploy` (`deployments/infrastructure/consul_deploy_role.tf:1-25`).
  F5 and F6 are `done` in the ledger; this brokering path works.
- **The existing `deploy` Nomad policy cannot drive this panel.** Its own
  comment says so: "no alloc-exec, no alloc-node-exec, no list-jobs /
  dispatch-job / read-logs / read-fs, and no node / agent / operator access"
  (`nomad_deploy_role.tf:1-12`); rules grant only `submit-job`, `read-job`,
  `host-volume-*` (`:17-29`). `GET /v1/jobs` needs `list-jobs`; `GET /v1/nodes`
  needs `node:read`. A token minted from `nomad/creds/deploy` gets 403 on both.
  See Q2.

### Network reach
- ufw admits ports 4646, 8200 and 8500 from `192.168.0.0/16` **only**
  (`bootstrap/playbooks/configure_network.yml:13-25`). The tailnet
  `100.64.0.0/10` is allowed on port 22 alone (`:10-11`). A developer off-LAN
  reaches these APIs only through the SSH hop, not directly. See Q5.

### What Grafana already does
- `docs/monitoring.md:12-15`: Grafana is the authenticated front door to
  Prometheus and Loki, both of which have no auth of their own.
- `docs/monitoring.md:48-56` names the three things Grafana does not give:
  scrape-failure text, the expression browser, Loki's raw HTTP API. **This
  panel adds none of those.** It is orthogonal: current control-plane state,
  not metrics.

## Non-goals / out of scope

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
- Does not change any Nomad job, Terraform root, or Ansible role — **except**
  possibly one new read-only ACL policy, pending Q2.
- Does not read `deployments/**` to enumerate jobs. See the `talat-*` trap.
- No JSON/`--output` mode, no non-interactive fallback, no web UI.

## Requirements & restrictions

1. **The panel shows exactly four things.** Adding a fifth is scope creep and
   needs a new ticket:
   - **Vault seal state** — the most common real outage (`justfile:22-23`
     exists for it) and the only source readable without a token.
   - **Node status** — 5 rows: name, status, eligibility, drain. A job that
     will not place is usually a node that went away, and the single-server
     topology (`nomad.hcl.j2:11-14`) makes node loss consequential.
   - **Per-job allocation health** — 19 rows: name, type, status, and
     running/desired plus failed/lost from `JobSummary`. This is the "is my
     job running" answer and the reason the panel exists.
   - **Consul critical checks** — the count, and the failing checks only
     (never all 41). A Nomad alloc can be `running` while its Consul check is
     critical; nothing else on the screen shows that.
2. **Cut candidate: a separate "recent failed allocations" panel.** Nomad GCs
   dead allocs (24 allocs live, all running, verified), so it is empty most
   days, and `JobSummary.Failed`/`Lost` on the job row already answers it. Do
   not build it.
3. **Enumerate jobs from the Nomad API, never from `deployments/`.** The
   `talat-*` jobs prove the repo tree is not the cluster.
4. **Job health rules branch on job type.** `service`: running vs desired.
   `system`: running count vs eligible node count. `batch/periodic`: the
   parent's `Status` and last child outcome, never `Running == 0`.
5. **No source may block the UI.** Each of the four fetches runs
   independently with its own timeout; a slow or dead endpoint degrades its
   own panel and nothing else. A TUI that hangs on a dead Vault is worse than
   no TUI.
6. **Degraded states are first-class, not error handling.** Named, rendered,
   and snapshot-tested: token expired, Vault sealed, Nomad unreachable,
   Consul unreachable, permission denied (403). These are exactly when a
   developer opens the panel.
7. **Auth comes entirely from D2.** No token acquisition, no Vault login, no
   credential file reading, no env-var token fallback authored here. If D2's
   surface does not fit, that is `out-of-scope-fix-needed`, not a second login
   path.
8. **Secrets never printed.** No token value renders on screen or in a
   snapshot fixture. `detect-private-key` (`.pre-commit-config.yaml:12`) stays
   green.
9. **Fetchers live in a module separate from the widgets**, and every widget
   takes its data through an injected callable. This is what makes Q3 (D3
   reuse) a one-file swap and what makes the snapshot tests deterministic.
10. **Dependencies via `uv add`**, never `uv pip`
    (`.claude/rules/uv-installer.md:6-8`). New deps: `textual`,
    `pytest-textual-snapshot`, `respx`. `httpx` is already the repo's HTTP
    client (`requirements.txt:3`) — use it, do not add `requests`.
11. **Every code change ships a test** (`.claude/rules/python-testing.md:6-10`).
12. **Live-cluster tests carry a marker and are excluded from the default run
    via `addopts`** (`.claude/rules/python-testing.md:26-32`). Default
    `uv run pytest` is offline and fast.
13. **Textual snapshots via `pytest-textual-snapshot`; refresh baselines only
    on a reviewed intentional change, never to clear a red test**
    (`.claude/rules/python-testing.md:112-117`).
14. **Mock HTTP with respx, not hand-rolled patches**
    (`.claude/rules/python-testing.md:89`).
15. **Plain language in every rendered string, comment and doc line**
    (`.claude/rules/plain-language.md`). Panel labels say "sealed", "no
    token", "unreachable" — not "degraded telemetry posture".
16. **Adversarial review before done** (`.claude/rules/adversarial-reviews.md`).
17. **Pre-existing failures get fixed, not skipped**
    (`.claude/rules/pre-existing-issues.md`).

## Code surface

**All paths under `cli/` are the layout D1 establishes. Before writing any
file, read `cli/pyproject.toml` and the existing `cli/` tree and match it.
The names below are the intent; D1's actual package name wins.**

New:
- `cli/src/localstack/tui/cluster.py` — the Textual `App`: one screen, four
  widgets, the refresh timer, the keybindings (`q` quit, `r` refresh now).
- `cli/src/localstack/tui/widgets.py` — the four widgets. Each takes a fetch
  result (data or a named degraded state) and renders it. No I/O here.
- `cli/src/localstack/cluster_api.py` — the four read-only fetchers over
  `httpx`, each with its own timeout, each returning either parsed data or a
  named failure (`unreachable`, `unauthorized`, `timeout`). No Textual import
  here. **This is the file Q3 either creates or deletes.**
- `cli/tests/test_cluster_api.py` — respx tests per fetcher: happy path, 403,
  timeout, connection error, and the periodic/system job-health rules.
- `cli/tests/test_cluster_tui.py` — `pytest-textual-snapshot` tests: healthy
  cluster, Vault sealed, Nomad 403 (expired token), Nomad unreachable, mixed
  (one job failed).
- `cli/tests/fixtures/cluster/*.json` — canned payloads captured from the live
  cluster (jobs, nodes, seal-status, consul health), with tokens and cluster
  IDs stripped. The snapshot tests' only input.
- `cli/tests/__snapshots__/` — pytest-textual-snapshot baselines (generated).

Modified:
- `cli/pyproject.toml` (D1's) — `uv add textual`; dev deps
  `pytest-textual-snapshot`, `respx`; register the live-cluster marker and
  exclude it in `addopts` per `.claude/rules/python-testing.md:26-32`.
- `cli/src/localstack/__main__.py` or D1's command registry — register the
  `status` subcommand. Exact file per D1's structure.
- `docs/monitoring.md` — one short section: what `localstack status` shows and
  what it deliberately does not (pointing at `:48-56`'s existing boundary
  discussion). Do not restructure the doc.

Conditional (only if Q2 resolves to "yes, in this ticket"):
- `deployments/infrastructure/nomad_read_role.tf` (new) — a `nomad_acl_policy`
  granting `list-jobs`, `read-job`, and node read, plus a
  `vault_nomad_secret_role`, following the shape of
  `nomad_deploy_role.tf:13-41`. **Do not edit `nomad_deploy_role.tf` itself.**

## Tests & validation gates

### Repo gates (discovered, not assumed)
- **`just pre_commit`** → all Passed. This is the loop's configured gate
  (`.loop/config.json` `gates`). It runs `pre-commit run --all-files`
  (`justfile:18-19`) over `.pre-commit-config.yaml:1-33`: `check-json`,
  `check-ast`, `check-merge-conflict`, `check-yaml`, `debug-statements`,
  `detect-private-key`, `end-of-file-fixer`, plus `nomad fmt`, `terraform
  fmt -check`, and `scripts/tf_validate.sh`. `check-ast` and
  `debug-statements` apply to the new Python.
- **`uv run pytest`** from `cli/` → green, offline, no live-cluster tests.
- **There is no CI for these gates.** `.github/workflows/` holds only
  `claude-ollama.yaml` and `hermes-interactive.yaml`, both agent runners.
  Gates are local; run them.
- **No ruff/mypy hook exists** in `.pre-commit-config.yaml` today. If D1 added
  one, it applies. Do not add lint hooks in this ticket (see Q4).
- If the conditional Terraform file lands: `terraform -chdir=deployments/infrastructure plan`
  adds the policy and role, destroys nothing. Worktree prerequisite:
  `just worktree_setup <path>` (`justfile:30-32`).
- Adversarial review (`.claude/rules/adversarial-reviews.md`).

### How snapshot tests get deterministic input
The data source is a live cluster, so it never touches a test. Three layers:
1. Capture real payloads once into `cli/tests/fixtures/cluster/*.json` (strip
   tokens, cluster IDs, and any timestamp the render displays).
2. Widget tests take fixtures through the injected fetch callable
   (requirement 9). **No HTTP at all** in the snapshot tests.
3. Fetcher tests (`test_cluster_api.py`) serve those same fixtures over respx
   (`.claude/rules/python-testing.md:89`), so the parsing layer is exercised
   against real payload shapes without a network.

Anything that varies per run must be excluded from the render or frozen: no
`SubmitTime` deltas, no "updated 3s ago", no wall-clock strings. If a relative
timestamp is wanted, inject the clock.

### Tests to add (each file listed in §7)
`cli/tests/test_cluster_api.py`:
- Per fetcher: 200 happy path against a captured fixture.
- Nomad 403 → `unauthorized`, not an exception. (The verified real behavior of
  an expired or under-scoped token.)
- Connection refused → `unreachable`; slow response → `timeout`.
- Vault `sealed: true` payload → sealed state.
- Job health rules, parametrized: `acme` (periodic, `Running == 0`) is
  **healthy**; `node-exporter` (system) healthy at running == eligible nodes;
  a `service` job with `Running < desired` is unhealthy; a job with
  `Failed > 0` is unhealthy.
- Consul health filtered to critical only; 0 critical renders as fine.

`cli/tests/test_cluster_tui.py` (snapshots):
- Healthy cluster (all four panels green).
- Vault sealed, everything else fine.
- Nomad 403 — job and node panels show "no token / expired", Vault and Consul
  panels still render. **This is the token-expired requirement, tested.**
- Nomad unreachable — same panels show "unreachable", others still render.
- One `service` job failed — the failure is visible without scrolling.

Live-cluster smoke test, marked and excluded from the default run
(`.claude/rules/python-testing.md:26-32`): one test that hits the real cluster
and asserts each fetcher returns parseable data. Run on purpose with `-m`.

## Risk assessment

- **Blast radius: near zero for the cluster.** Read-only HTTP GETs against
  three APIs. The panel cannot change cluster state. The only cluster-side
  change is the conditional new ACL policy in Q2, which is additive and does
  not touch `deploy`.
- **Reversibility: high.** Delete the subcommand and its module; nothing else
  depends on it. The Terraform policy, if added, is a clean `terraform
  destroy` target for that resource.
- **Likeliest failure mode: the token cannot read what the panel needs.**
  `nomad/creds/deploy` explicitly lacks `list-jobs` and node read
  (`nomad_deploy_role.tf:1-12`). If Q2 is not settled first, the panel ships
  showing 403 in its two most important widgets. **This is the single biggest
  risk in the ticket.**
- **Second failure mode: the UI hangs.** A synchronous fetch in the render
  path against a sealed Vault or a downed firebat freezes the whole screen at
  the exact moment it is needed. Requirement 5 exists for this; the snapshot
  tests for unreachable states are what prove it.
- **Third: false alarms from the periodic/system jobs.** 3 of 19 jobs report
  `Running: 0` while healthy (verified). Getting rule 4 wrong makes the panel
  cry wolf, which is worse than no panel because a developer stops trusting it.
- **Scope drift toward Grafana.** The panel is one refactor away from "well,
  we could also chart that". The non-goals section is the guardrail; a diff
  importing a Prometheus client is a review failure.
- **Snapshot brittleness.** Textual snapshots break on terminal size, theme,
  and library version. Pin `textual` and set a fixed terminal size in the
  tests, or every unrelated dependency bump reds the suite and invites the
  forbidden `--snapshot-update` reflex.
- **Dependency risk is real, not nominal.** D1 and D2 do not exist yet (Q1).
  Nothing here can be written, let alone tested, until `cli/` and its token
  source do.

## Subtickets (ordered)

1. **Settle Q1–Q3 with the operator.** Q2 in particular gates everything: the
   panel needs a Nomad token that can list jobs and read nodes.
2. Read D1's `cli/` tree and D2's token surface; fix the real module paths and
   the fetch-credential call. Confirm the §7 anchors.
3. `cluster_api.py`: four fetchers over `httpx`, per-source timeouts, named
   failure states. No Textual import.
4. Capture live payloads into `cli/tests/fixtures/cluster/`, scrubbed.
5. `test_cluster_api.py` with respx, including the job-health rule table
   (periodic/system/service) and the 403/timeout/unreachable paths. Green
   before any UI exists.
6. The four widgets, data injected, no I/O.
7. The `App`: layout, refresh timer, `q`/`r` keys, independent per-source
   refresh.
8. Snapshot tests for the healthy case and all four degraded cases. Review
   each baseline before committing it.
9. Register the `status` subcommand in D1's command surface.
10. Run it against the real cluster. Deliberately seal-check, revoke the
    token, and stop reaching Nomad, and confirm the panel degrades as
    snapshot-tested rather than hanging.
11. `docs/monitoring.md` section, including the explicit Grafana boundary.
12. `just pre_commit` and `uv run pytest`, then adversarial review.

## Open questions

- **Q1 — D1 and D2 do not exist as tickets.** No `D1-*` or `D2-*` slug is in
  `.loop/plans/` or `.loop/ledger.json` (verified 2026-07-30). `depends_on =
  ["D2-cli-login-broker-tokens"]` is a **hard gate**: `loopctl advance <slug>
  implementing` refuses until that exact slug is `done`, and an unregistered
  slug is an unsatisfiable dependency. *Recommendation:* keep the dependency
  as the operator specified and author D1/D2 next, using exactly the slug
  `D2-cli-login-broker-tokens`. Do not weaken the front-matter to unblock
  pickup.

- **Q2 — Which Nomad token does the panel use, and who creates its policy?**
  The existing `deploy` role cannot list jobs or read nodes
  (`nomad_deploy_role.tf:1-12`, `:17-29`), so a `nomad/creds/deploy` token
  yields 403 on the panel's two main widgets (403 verified for tokenless
  requests; the policy comment is explicit about the missing capabilities).
  Options: (a) D2 brokers a new read-only role and this ticket only consumes
  it; (b) this ticket adds `deployments/infrastructure/nomad_read_role.tf` and
  D2 brokers from it; (c) reuse `deploy` and accept the degraded panels.
  *Recommendation:* **(b)**. The policy is this panel's requirement, so it
  belongs to the ticket that knows what to grant, and it is additive (a new
  file, `deploy` untouched). Grant `list-jobs` and `read-job` on the `default`
  namespace plus node read, and nothing else — no `read-logs`, no
  `alloc-exec`, no `submit-job`. Reject (c): a panel whose headline widgets
  say "denied" is not worth shipping.

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
  against a 5-node home cluster is negligible load (one `/v1/jobs`, one
  `/v1/nodes`, one seal-status, one health call). If the operator prefers
  manual-only, the same structure supports it by setting the interval to 0.

- **Q5 — Does the panel need to work from off-LAN?** ufw admits 4646/8200/8500
  from `192.168.0.0/16` only; the tailnet gets port 22 alone
  (`configure_network.yml:10-25`). So a developer on tailscale but off the LAN
  cannot reach these APIs directly today. *Recommendation:* scope this ticket
  to on-LAN use and make the failure legible — "unreachable" plus a one-line
  hint about the SSH hop, not a stack trace. Opening 4646/8200/8500 to
  `100.64.0.0/10` is a firewall decision with its own blast radius and belongs
  in a separate ticket, not smuggled in here.

- **Q6 — Where does the panel read its endpoint addresses from?** Today the
  shell carries `NOMAD_ADDR`, `VAULT_ADDR`, `CONSUL_HTTP_ADDR` (all pointing
  at `192.168.2.30`), and Terraform hardcodes `192.168.2.30:8500`
  (`deployments/infrastructure/services.tf:338`). *Recommendation:* read the
  standard env vars, fall back to the `192.168.2.30` defaults, and let D1's
  config file override if D1 created one. Do not invent a config format here.

- **Q7 — Does a Consul token get brokered too?** Consul health reads work
  tokenless today only because `tokens.default` is set to the agent token
  (`consul.hcl.j2:29-32`) despite `default_policy = "deny"` at `:27`.
  *Recommendation:* rely on the tokenless read for now and note the
  dependency in a code comment, since D2 brokering a Consul token for a
  read that needs none is unearned work. If that config ever tightens, the
  panel's Consul widget degrades to "denied" like any other source, which is
  the designed behavior rather than a crash.
