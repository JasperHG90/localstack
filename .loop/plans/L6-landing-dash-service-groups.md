---
epic = "landing"
priority = 10
depends_on = ["L4-landing-dash-fe-be-split"]
summary = """
Reorganize the dash landing page around operator-chosen service groups.
tiles.json becomes an ordered list of groups of tiles; a tile is one
SERVICE carrying an optional frontend URL and optional backend connect
instructions, not one row per endpoint. Every card opens a panel.
Drops the memex tile, adds prometheus, folds openviking-api into
openviking and registry-ui into registry.
"""
---
# Ticket: L6-landing-dash-service-groups

## 1. Title

Group the dash landing page by service group, and give every tile one
panel carrying its frontend button, its backend instructions, or both.

## 2. Size / Effort

M. Confined to one service directory, but it rewrites a config schema
and the API payload derived from it, so the backend parser, the status
fold, the JSON shape, the frontend render and three test modules move
together. No infrastructure, auth or edge-routing change.

## 3. Triggered by

Operator, verbatim: "I don't like the way that the dashboard is
organized. We should be able to organize both the headers and the
tiles." Plus the standing `TODO.md:6` item, and "Remove memex".

## 4. Context

Today's tile config is a FLAT array whose three-value `category` field
doubles as the section it renders in.

- `deployments/applications/services/dash/tiles.json` — 17 tiles in one
  JSON array. Probe: `load_tiles` on the shipped file returned
  `count 17`, `Counter({'dashboard': 9, 'backend': 5, 'agents': 3})`.
- `deployments/applications/services/dash/backend/src/dash_app/tiles.py:14`
  — `Category` is a closed `Literal`, rejected at
  `deployments/applications/services/dash/backend/src/dash_app/tiles.py:83`.
  Sections are not config; they are an enum in Python.
- `deployments/applications/services/dash/backend/src/dash_app/tiles.py:88`
  — a `dashboard` tile REQUIRES `url` and carries no `connect`; every
  other category REQUIRES `connect` and carries no `url`. A service
  cannot have both, which is exactly the `TODO.md:6` complaint.
- `deployments/applications/services/dash/frontend/index.html:413` —
  three `section` blocks with hardcoded headers `Dashboards`, `Agents`
  and `Backend services`, each feeding a fixed grid id
  (`deployments/applications/services/dash/frontend/index.html:418`,
  `:426`, `:434`).
- `deployments/applications/services/dash/frontend/index.html:552` —
  `sortTiles` orders every grid degraded-first then alphabetically, so
  config order is discarded.
- `deployments/applications/services/dash/frontend/index.html:474` — a
  `dashboard` tile renders as an anchor that navigates away. Only
  agent/backend tiles open the panel
  (`deployments/applications/services/dash/frontend/index.html:518`), so
  a service with a UI can never show its API.
- `deployments/applications/services/dash/frontend/index.html:568` —
  `refresh` partitions the flat list by `category` into those three
  fixed grids.
- `deployments/applications/services/dash/backend/src/dash_app/tiles.py:32`
  — `Tile` carries exactly one `job` and one `node`, so a service
  spanning two Nomad jobs has no representation.
- `deployments/applications/services/dash/backend/src/dash_app/status.py:91`
  — `build_routes` builds one synthetic route per TILE, named after
  `tile.job`.
- `deployments/applications/services/dash/backend/src/dash_app/main.py:29`
  — `_tile_json` branches on category to emit either `url` or
  `connect`, never both.

Three services are mis-shaped by the one-tile-per-endpoint model:

- `deployments/applications/services/dash/tiles.json:36` (`openviking`,
  a dashboard tile) and
  `deployments/applications/services/dash/tiles.json:47`
  (`openviking-api`, an agents tile) are the SAME Nomad job rendered
  twice in two different sections.
- `deployments/applications/services/dash/tiles.json:107`
  (`registry-ui`) and
  `deployments/applications/services/dash/tiles.json:214` (`registry`)
  are the browser view and the API of one artifact store, in two
  sections, backed by two Nomad jobs on two different nodes.
- `deployments/applications/services/dash/tiles.json:182` (`memex`) is
  dead on the page: its Nomad job is commented out at
  `deployments/applications/services.tf:716`, marked "Staged, not dead".

Prometheus has no tile and should. Loki needs nothing from a service
author — `deployments/infrastructure/services/alloy.hcl:113` discovers
every Nomad alloc's log files by path and forwards them. Prometheus
scrapes only a service whose author TAGS its Consul service, at
`deployments/infrastructure/services/prometheus.hcl:170`. That is
configuration the operator has to be told about.

## 5. Non-goals / out of scope

- NO memex teardown beyond the tile. `deployments/applications/services.tf:716`
  stays commented, and every memex secret, OIDC client, auth JSON and
  Bifrost key stays as it is.
- NO loki, embark, haproxy, alloy, node-exporter, oauth2-proxy or
  dash-itself tile. Operator rule: a service that works with no
  configuration, or that is reached through something else, earns no
  tile.
- NO change to
  `deployments/applications/services/dash/backend/src/dash_app/health.py`,
  `deployments/applications/services/dash/backend/src/dash_app/nomad_client.py`,
  `deployments/applications/services/dash/backend/src/dash_app/consul_client.py`
  or
  `deployments/applications/services/dash/backend/src/dash_app/services.py`
  — the copied-down cli logic.
- NO HAProxy route, oauth2-proxy, Nomad ACL or firewall change.
- NO image build, push, or `terraform apply`. The commit bumps the
  version strings; deploying is the operator's step (§9).
- NO visual redesign beyond what group headers and the panel need. The
  existing palette, card, badge and dialog CSS stays.
- NO `localstack` CLI change. `cli/src/localstack_cli/api/services.py:56`
  is a separate copy and is not touched.

## 6. Requirements & restrictions

R1. `deployments/applications/services/dash/tiles.json` becomes an
ordered array of GROUPS. Each group: `key`, `title`, optional `hint`,
and an ordered `tiles` array. Array order is display order for both
headers and tiles, with no re-sorting anywhere. This is the ask, and it
retires
`deployments/applications/services/dash/frontend/index.html:552`.

R2. Groups and their tiles, in this order (operator-settled):

| Group key | title | hint | tiles, in order |
|---|---|---|---|
| `platform` | Platform | the cluster's own control plane | nomad, consul, vault |
| `storage` | Storage | databases and object storage | postgres, redis, minio |
| `telemetry` | Telemetry | traces, metrics, logs, dashboards | grafana, phoenix, tempo, prometheus |
| `events` | Events | the message bus | nats |
| `agentic` | Agentic | the model gateway and the agents behind it | bifrost, hermes, openviking |
| `artifacts` | Artifacts | container images and model weights | registry |

Every group carries a `hint`. The three hints on the page today
(`deployments/applications/services/dash/frontend/index.html:416` is one)
describe the SORT and the CLICK, both of which R1 and R5 make uniform, so
they are replaced by a hint that says what the group holds.

R3. A tile is one SERVICE. It carries an optional `fe` object (`url`,
optional `label`) and an optional `connect` object (today's four fields,
`deployments/applications/services/dash/backend/src/dash_app/tiles.py:22`).
At least one of the two is required; both together is the case
`TODO.md:6` asks for. The `category` field and the `Category` literal at
`deployments/applications/services/dash/backend/src/dash_app/tiles.py:14`
are removed — group membership replaces them. `connect` keeps its four
fields but widens in meaning, from "how to call this service" to "how to
work with this service without a browser", so R10's prometheus tile can
use it to say how to get scraped. Update the docstring at
`deployments/applications/services/dash/backend/src/dash_app/tiles.py:23`
to match.

R4. A tile carries `jobs`: an ordered, non-empty array of
`{name, node}`. Its status is the WORST of its jobs' statuses, severity
`down > degraded > unknown > up`. `unknown` outranks `up` because
absence of a signal is not evidence of health — the stance
`deployments/applications/services/dash/backend/src/dash_app/services.py:48`
already states for `NO_CHECK`.

R5. Every card opens the panel. The panel carries, in order: name and
desc, one status row per job with its node, the `connect` block when
present, and a frontend button when `fe` is present.

R6. A tile with an `fe` keeps a one-click route out: the card's corner
icon is a real anchor to the frontend URL. An anchor nested inside a
button is invalid HTML, so the card becomes a container holding a
stretched panel-opening button with the anchor layered above it.

R7. `memex` is dropped from
`deployments/applications/services/dash/tiles.json`. Nothing else memex
moves.

R8. `openviking-api` folds into `openviking`: one tile,
`fe.url` of `https://openviking.lab.orangecluster.nl`, the `connect`
block currently at
`deployments/applications/services/dash/tiles.json:55`, one job
`openviking` on `radxa-dragon-q6a`.

R9. `registry-ui` folds into `registry`: one tile in `artifacts`,
`fe.url` of `https://registry-ui.lab.orangecluster.nl`, the `connect`
block currently at
`deployments/applications/services/dash/tiles.json:222`, and two jobs —
`registry` on `ubuntu`
(`deployments/applications/services/registry.hcl:16`) and `registry-ui`
on `radxa-dragon-q6a`
(`deployments/applications/services/registry-ui.hcl:8`).

R10. A `prometheus` tile is added to `telemetry`: job `prometheus` on
`ubuntu` (`deployments/infrastructure/services/prometheus.hcl:9`) and no
`fe`, because N1 restricted its UI to the cluster and it has no edge
hostname. Its `address` is the cluster-internal `ubuntu:9090`, and its
`auth` and `example` state the Consul-tag contract at
`deployments/infrastructure/services/prometheus.hcl:170` — tag the
service `prometheus`, optionally set `metrics_path` service metadata.
This tile reads `connect` as "how to be SCRAPED by this service" rather
than "how to call it", which widens the field's meaning from the
docstring at
`deployments/applications/services/dash/backend/src/dash_app/tiles.py:23`.
R3 records that widening; the fields themselves do not change shape.

R11. `/api/status` returns `groups`, in config order, each with its
`key`, `title`, `hint` and its tiles' JSON. The top-level `tiles` key is
gone. Per-tile JSON carries EVERY field the page reads, namely:

- `key`, `name`, `desc`, `color`, `icon` — unchanged.
- `status` — the FOLDED tile status from R4. The badge, the inset border
  (`deployments/applications/services/dash/frontend/index.html:221`) and
  the summary counts
  (`deployments/applications/services/dash/frontend/index.html:588`) all
  key off this one field, so it stays tile-level.
- `node` and `counts` — those of the DECIDING job: the worst-severity
  job, ties broken by config order. For a one-job tile this is exactly
  today's value, so the card foot
  (`deployments/applications/services/dash/frontend/index.html:492`) keeps
  working; for the two-job registry tile it names the node where the
  problem actually is.
- `jobs` — every job as `{name, node, status, counts}`, in config order.
  The panel renders one row each. This is the only place a healthy job
  behind a failing sibling stays visible.
- `fe` and/or `connect` — present only when configured. A tile with no
  `fe` carries no `fe` key at all, rather than a null.

`category` is gone from the payload. The error path
(`deployments/applications/services/dash/backend/src/dash_app/main.py:60`)
degrades every tile to `unknown` inside its group rather than flattening
the groups away, so a failed fetch still renders the page skeleton.

R12. `deployments/applications/services/dash/tiles.json` must contain
neither a `${` nor a `%{` sequence.
`deployments/applications/services/dash.hcl:126` splices the file into a
Nomad heredoc, so its bytes are parsed as jobspec template text. Probed
behavior, not inferred (P10): a bare `$` round-trips byte for byte;
`${IDENT}` PARSES and is preserved verbatim, reaching the deployed
template for Nomad's own runtime interpolation; a `${` around anything
expression-shaped FAILS the parse at `terraform apply`; and `%{ if ... }`
PARSES and SILENTLY REWRITES the text. `%{` is the more dangerous of the
two and the reason the ban covers both. A test enforces it (§8), because
neither failure is visible in the repo.

R13. `deployments/applications/services.tf:599` and
`deployments/applications/services.tf:600` bump both image versions from
`0.2.1` to `0.3.0`. Both images change, and the rebuild recipes read the
tag straight out of that file
(`deployments/applications/justfile:54`,
`deployments/applications/justfile:89`).

R14. Every change ships a test (`.claude/rules/python-testing.md`,
constraint `all-code-needs-tests`). Tests are linted and type-checked
like the rest (`tests-are-real-code`); no `skip`, `xfail` or
`type: ignore` to make a gate green.

R15. Comments only where the code cannot carry the meaning
(`.claude/rules/minimal-comments.md`). The provenance docstrings at
`deployments/applications/services/dash/backend/src/dash_app/status.py:1`
and
`deployments/applications/services/dash/backend/src/dash_app/services.py:1`
are load-bearing and stay.

R16. Plain language in every comment, docstring and the commit message
(`.claude/rules/plain-language.md`).

R17. Surgical changes only (`AGENTS.md` §3). Every changed line traces
to a requirement here.

R18. The deployed-endpoint test at
`deployments/applications/services/dash/backend/tests/test_cluster.py:39`
moves to the grouped payload. It reads the removed top-level `tiles` key
(`:39`, `:40`, `:41`) and the moved `node` field (`:44`), and
`test_a_known_dashboard_tile_reports_a_real_status` (`:47`) reads
`body["tiles"]` again at `:61` while its name and docstring describe a
`dashboard` category that no longer exists. It is marked `cluster` and
excluded by `addopts` at
`deployments/applications/services/dash/backend/pyproject.toml:37`, so
the gate stays GREEN whether or not this is done. It must be updated by
hand and by intent, not left to the gate.

R14 through R17 are cross-cutting constraints on how the work is done,
not deliverables. They have no row of their own in §7 or §10 by design;
§8's gate list is what enforces R14, and the adversarial review pass
enforces R15 through R17.

## 7. Code surface

| File | Change |
|---|---|
| `deployments/applications/services/dash/tiles.json` | Whole file rewritten to the grouped schema (R1, R2). memex dropped (R7); openviking-api and registry-ui folded (R8, R9); prometheus added (R10); no `${` (R12). |
| `deployments/applications/services/dash/backend/src/dash_app/tiles.py` | Remove `Category` (`:14`). Keep `ConnectInfo` (`:22`), add `FrontEnd` and `JobRef`. `Tile` (`:32`) loses `category`/`job`/`node`/`url`, gains `jobs` and `fe`. Add `Group`. Rewrite `_parse_tile` (`:70`) with no category branch, requiring at least one of `fe`/`connect` and a non-empty `jobs`; add `_parse_group`. `load_tiles` (`:107`) returns groups and rejects a duplicate group key or tile key. |
| `deployments/applications/services/dash/backend/src/dash_app/status.py` | `build_routes` (`:91`) emits one route per JOB across all groups. `compute_tile_states` (`:101`) takes groups, resolves each job, folds to the worst status (R4); severity table beside `_HEALTH_TO_STATUS` (`:37`). |
| `deployments/applications/services/dash/backend/src/dash_app/live.py` | `fetch_tile_states` (`:19`) iterates every job of every tile of every group when building `service_names`. |
| `deployments/applications/services/dash/backend/src/dash_app/main.py` | `_tile_json` (`:29`) emits `fe`/`connect`/`jobs` with no category branch. `create_app` (`:55`) payload carries `groups`; the error path degrades every tile to `unknown` group-wise. |
| `deployments/applications/services/dash/frontend/index.html` | Replace the three hardcoded sections (`:413`) with one container rendered from `groups`. The hint promising the old sort order (`:416`) dies with that block, so no separate footnote edit is needed: `:437` describes where status comes from and stays true. Rewrite `cardHtml` (`:474`) to the container/button/anchor shape (R6). Rewrite the panel open (`:501`) for per-job rows, connect block and frontend button (R5); move the two grid listeners (`:518`) to one delegated listener. Delete `sortTiles` (`:552`). Rewrite `refresh` (`:568`) to render groups in order and count across all of them. Add CSS for the stretched button, the layered corner link, the per-job rows and the frontend button. |
| `deployments/applications/services/dash/backend/tests/test_tiles.py` | Rewritten for the grouped schema; cases per §8. |
| `deployments/applications/services/dash/backend/tests/test_status.py` | Multi-job folding cases per §8; existing agent-endpoint cases (`:90`, `:103`) kept. |
| `deployments/applications/services/dash/backend/tests/test_main.py` | Payload-shape cases per §8; existing credential and fetch-failure cases (`:116`, `:144`) kept. |
| `deployments/applications/services/dash/backend/tests/test_cluster.py` | `assert "tiles" in body` (`:39`) and `assert tile["node"]` (`:44`) are both falsified by R11. Update to the grouped payload (R18). |
| `deployments/applications/services.tf` | Bump `dash_frontend_version` (`:599`) and `dash_backend_version` (`:600`) to `0.3.0` (R13). |
| `deployments/applications/services/dash.hcl` | Correct the stale claim at `:122` that the tile config "contains no dollar-sign characters" — it has carried one since `deployments/applications/services/dash/tiles.json:59`. State the real rule (R12). Free here: R13 re-registers the job anyway. |
| `docs/dash-landing-page.md` | Rewrite the schema reference. `:7` (dashboard tiles link out, agent and backend tiles open a modal), `:40` (the `category` enum), `:41-43` and `:46` (the url-or-connect either/or) all document what R1, R3, R5 and R7 remove. |
| `TODO.md` | Delete line 6, the item this ticket closes. |

## 8. Tests & validation gates

Gate, from `.loop/config.json`: `just pre_commit` — `justfile:19` runs
`pre-commit run --all-files`. Hooks that fire on this diff:

- `check-json` (`.pre-commit-config.yaml:6`) on the tile config.
- `dash-backend-ruff` (`.pre-commit-config.yaml:120`),
  `dash-backend-ruff-format` (`.pre-commit-config.yaml:126`),
  `dash-backend-mypy` (strict, `.pre-commit-config.yaml:132`).
- `dash-backend-pytest` (`.pre-commit-config.yaml:138`), whose `files`
  pattern (`.pre-commit-config.yaml:144`) covers the tile config, so a
  bad tile fails this gate.
- `terraform-fmt` (`.pre-commit-config.yaml:22`) and
  `terraform-validate` (`.pre-commit-config.yaml:28`).
- `end-of-file-fixer` (`.pre-commit-config.yaml:13`).

Baseline, probed before any edit:
`uv run --project deployments/applications/services/dash/backend pytest
deployments/applications/services/dash/backend/tests -q` gave
`38 passed, 2 deselected, 1 warning in 0.17s`.

In `deployments/applications/services/dash/backend/tests/test_tiles.py`:

- `test_loads_ordered_groups_in_file_order` — group order and per-group
  tile order come back as written, not sorted.
- `test_rejects_a_tile_with_neither_fe_nor_connect` (R3).
- `test_accepts_a_tile_with_both_fe_and_connect` (R3, the `TODO.md:6`
  case).
- `test_rejects_a_tile_with_an_empty_jobs_list` (R4).
- `test_rejects_a_duplicate_group_key` (R1).
- `test_rejects_a_duplicate_tile_key` (R1).
- `test_the_shipped_config_parses_into_the_six_expected_groups` (R2),
  pinning the full expected key set so a dropped tile fails.
- `test_the_shipped_config_has_no_memex_tile` (R7).
- `test_the_shipped_openviking_tile_carries_both_fe_and_connect` (R8).
- `test_the_shipped_registry_tile_names_both_of_its_jobs` (R9).
- `test_the_shipped_prometheus_tile_documents_the_consul_tag` (R10).
- `test_the_shipped_config_carries_no_nomad_template_opener` (R12) —
  asserts both `${` and `%{` are absent from the raw file text. `%{` is
  the one that corrupts silently, so the test must cover it.
- Existing `test_rejects_syntactically_invalid_json` (`:130`) kept.

In `deployments/applications/services/dash/backend/tests/test_status.py`:

- `test_a_single_job_tile_reports_that_jobs_status` — regression for
  what `:49` through `:89` cover today.
- `test_a_two_job_tile_reports_the_worst_of_the_two`, parametrized over
  R4's severity order, including up plus unknown giving unknown.
- `test_each_job_of_a_tile_carries_its_own_node` (R11).

In `deployments/applications/services/dash/backend/tests/test_main.py`:

- `test_status_payload_carries_groups_in_config_order` (R11).
- `test_a_tile_with_both_fe_and_connect_emits_both` (R3).
- `test_a_tile_with_only_connect_emits_no_fe_key` (R3).
- `test_each_tile_carries_a_per_job_status_array` (R11).
- `test_a_two_job_tile_reports_the_folded_status_in_the_payload` (R4,
  R11) — the fold must be pinned AT the JSON layer, not only in
  `compute_tile_states`. Without this the backend suite can be wholly
  green while the page renders no badge at all.
- `test_a_two_job_tile_reports_the_deciding_jobs_node_and_counts` (R11).

In `deployments/applications/services/dash/backend/tests/test_cluster.py`
(R18):

- `test_status_endpoint_answers_with_live_tiles` (`:29`) — read `groups`,
  walk each group's tiles, and assert `node` on each job rather than on
  the tile.
- `test_a_known_dashboard_tile_reports_a_real_status` (`:47`) — renamed
  and re-pointed: it looks grafana up through `body["groups"]`, and its
  name and docstring drop the `dashboard` category.

WARNING on both: `addopts` at
`deployments/applications/services/dash/backend/pyproject.toml:37`
excludes the `cluster` mark, which is why the baseline probe reads
`2 deselected`. `just pre_commit` will pass whether or not these two are
fixed. They are verified on purpose, against the deployed job, with
`uv run --project deployments/applications/services/dash/backend pytest
-m cluster` — and only after the deploy in §9, since they read the live
endpoint.

The acceptance layer above these tests is
`.loop/evals/L6-landing-dash-service-groups.md`: nine scenarios, four of
them scored by hand in a browser because nothing here can assert them.
A green `just pre_commit` is not that eval passing.

NO automated gate covers
`deployments/applications/services/dash/frontend/index.html`. The repo
runs no JS test or linter, and `.pre-commit-config.yaml:117` says so.
The frontend is verified by hand against a locally served page, and that
manual check belongs in the eval, not in the gate. R5 and R6 are checked
there: every card opens the panel, a tile with both parts shows both, and
the corner anchor still leaves the page in one click.

## 9. Risk assessment

Blast radius: one Nomad job and one landing page. No auth, no routing,
no persistent state, and nothing else reads the tile config —
`deployments/applications/services.tf:586` says it feeds the backend
task only.

Reversibility: high. A revert plus an apply restores the old jobspec and
the old image tags, both still in ghcr.

Failure modes, likeliest first:

1. **A `%{` or an expression-shaped `${` reaches the tile config.** The
   heredoc at `deployments/applications/services/dash.hcl:126` makes the
   config's bytes jobspec template text. `%{ if ... }` is the bad case: it
   parses clean and silently rewrites the deployed JSON, so the page ships
   with mangled text and nothing complains. An expression-shaped `${...}`
   is the loud case, failing at `terraform apply`. A plain `${IDENT}` does
   neither — it survives into the deployed template. R12's test bans both
   openers rather than reasoning about which body is safe.
2. **Versions bumped, images not pushed.** An apply then leaves the job
   unable to place. ORDER: rebuild and push BOTH images
   (`deployments/applications/justfile:54`,
   `deployments/applications/justfile:89`), then apply. This is why
   deploy is out of scope for the loop (§5) and stays an operator step.
3. **Frontend regression no gate catches.** Panel-always touches every
   card; only a manual browser pass finds a broken listener or an
   unrendered group.
4. **A tile silently vanishes.** A typo in a group's `tiles` array drops
   a service off the page with no error;
   `test_the_shipped_config_parses_into_the_six_expected_groups` pins
   the full set.
5. **The two-job registry tile masks one job.** Written as "first job
   wins" rather than worst-of, a dead `registry-ui` shows green behind a
   healthy `registry`. R4's parametrized test is the guard.

## 10. Subtickets

One loop iteration, in this order:

1. `deployments/applications/services/dash/backend/src/dash_app/tiles.py`
   — dataclasses, parser, grouped `load_tiles`. Verify: the fixture
   cases in `test_tiles.py` pass.
2. `deployments/applications/services/dash/tiles.json` — rewrite to the
   grouped schema. Verify: the shipped-config cases pass.
3. `deployments/applications/services/dash/backend/src/dash_app/status.py`
   and
   `deployments/applications/services/dash/backend/src/dash_app/live.py`
   — per-job routes and the worst-of fold. Verify: `test_status.py`
   passes.
4. `deployments/applications/services/dash/backend/src/dash_app/main.py`
   — grouped payload. Verify: `test_main.py` passes.
5. `deployments/applications/services/dash/frontend/index.html` — group
   render, panel-always, corner link. Verify: served locally against a
   stubbed status response, by hand.
6. `deployments/applications/services.tf` version bump. Verify:
   `terraform fmt -check -recursive` and `scripts/tf_validate.sh`.
7. Full gate: `just pre_commit`.

## 11. Open questions

**Q1 — config order versus degraded-first.**
`deployments/applications/services/dash/frontend/index.html:552` sorts
every grid degraded-first then alphabetically. R1's operator-chosen
order and that sort cannot both win.
RECOMMENDATION: config order wins and `sortTiles` goes. A degraded
service stays visible three ways — the summary counts
(`deployments/applications/services/dash/frontend/index.html:398`), the
colored inset border
(`deployments/applications/services/dash/frontend/index.html:221`), and
the badge — and a landing page whose tiles move under you is worse than
one where the operator knows where each service sits. The alternative,
config order for groups but status order within a group, makes R1 half
true.

**Q2 — does the commit carry the version bump?** R13 bumps both image
versions, but the loop never builds or pushes an image, so between merge
and the operator's rebuild the repo names a tag that is not in ghcr.
RECOMMENDATION: keep the bump in the commit and treat the ordered deploy
as a manual eval row. Leaving
`deployments/applications/services.tf:599` at `0.2.1` is worse: an apply
would quietly redeploy the OLD frontend against the NEW tile config,
the one combination that renders a blank page.

## Premises / assumptions

P1. The shipped tile config today is a flat array of 17 tiles split
9 dashboard, 3 agents, 5 backend. EVIDENCE, probe: `load_tiles` on
`deployments/applications/services/dash/tiles.json` returned `count 17`
and `Counter({'dashboard': 9, 'backend': 5, 'agents': 3})`.

P2. The dash backend suite is green before this change. EVIDENCE, probe:
`uv run --project deployments/applications/services/dash/backend pytest
deployments/applications/services/dash/backend/tests -q` returned
`38 passed, 2 deselected, 1 warning in 0.17s`.

P3. A dashboard tile cannot carry connect instructions today. EVIDENCE:
`deployments/applications/services/dash/backend/src/dash_app/tiles.py:88`
takes `url` on one branch and `connect` on the other;
`deployments/applications/services/dash/backend/src/dash_app/main.py:42`
mirrors the same either/or into the payload.

P4. `openviking` and `openviking-api` are the same Nomad job. EVIDENCE:
`deployments/applications/services/dash/tiles.json:42` and
`deployments/applications/services/dash/tiles.json:53` both read
`"job": "openviking"`.

P5. `registry` and `registry-ui` are two jobs on two different nodes.
EVIDENCE: `deployments/applications/services.tf:320` registers the first
and `deployments/applications/services.tf:617` the second;
`deployments/applications/services/registry.hcl:16` pins one node and
`deployments/applications/services/registry-ui.hcl:8` pins the other.

P6. memex is not running. EVIDENCE:
`deployments/applications/services.tf:716` — the whole job block is
commented out under "Staged, not dead".

P7. Prometheus needs per-service configuration to scrape a service and
loki does not. EVIDENCE:
`deployments/infrastructure/services/prometheus.hcl:170` keeps only
targets whose Consul tags match its regex;
`deployments/infrastructure/services/alloy.hcl:113` discovers alloc log
files by path and forwards them, naming no service.

P8. Prometheus runs on `ubuntu` and registers a Consul service with a
check, so a tile reads its health like every other job-backed tile.
EVIDENCE: `deployments/infrastructure/services/prometheus.hcl:9` and
`deployments/infrastructure/services/prometheus.hcl:30`.

P9. The tile config is spliced into the Nomad jobspec, so its bytes are
jobspec text. EVIDENCE: `deployments/applications/services.tf:589`
round-trips the file through `jsonencode`;
`deployments/applications/services/dash.hcl:126` writes it into a
heredoc template.

P10. In the heredoc splice, a bare `$` is safe, `${IDENT}` survives into
the deployed template, an expression-shaped `${...}` fails the parse, and
`%{ ... }` silently rewrites the text. EVIDENCE, probe: the plan reviewer
emulated `templatefile()` on
`deployments/applications/services/dash.hcl` and fed the result to the
same HCL2 parser the Nomad provider uses (`nomad job run -output`),
across eight variants of one tile's `desc`:

    bare-dollar            PARSED  identical
    dollar-ident           PARSED  identical
    dollar-nomad-var       PARSED  identical
    dollar-string-expr     FAILED  Error parsing job file
    dollar-invalid-expr    FAILED  Error parsing job file
    dollar-unterminated    FAILED  Error parsing job file
    pct-directive          PARSED  MANGLED -> 'x YES y'
    pct-bare               FAILED  Error parsing job file

So `${` alone is NOT a sufficient guard, and `%{` is the opener that
corrupts instead of failing. R12 bans both. The shipped bare `$` at
`deployments/applications/services/dash/tiles.json:59` round-trips
untouched, which is why it has deployed safely.
`deployments/applications/services/dash.hcl:122` claims the file
"contains no dollar-sign characters"; that has been false since line 59
landed, and §7 homes the correction.

P11. The dash images are built by hand from recipes that read the tag
out of Terraform, not by CI. EVIDENCE:
`deployments/applications/justfile:54` and
`deployments/applications/justfile:89` each grep
`deployments/applications/services.tf` for the version;
`.github/workflows/` holds only `claude-ollama.yaml` and
`hermes-interactive.yaml`, neither mentioning dash.

P12. The dash frontend has no automated gate. EVIDENCE:
`.pre-commit-config.yaml:117` states the frontend holds no Python and
needs no hooks, and the file defines no JS linter or test hook.

P13. The pytest gate fires on a tile-config change, so a broken config
cannot commit green. EVIDENCE: `.pre-commit-config.yaml:144`.

P14. `registry-ui` is live on `main` even though ticket
`L5-landing-registry-tab` sits at `blocked` in the ledger. EVIDENCE:
`git ls-files deployments/applications/services/registry-ui` returns
tracked backend and frontend files;
`deployments/applications/services.tf:617` registers the job;
`deployments/infrastructure/services/haproxy.hcl:109` routes its
hostname. This ticket cites the code rather than declaring a
`depends_on` that would deadlock.

P15. The worst-of fold in R4 is achievable on today's resolution ladder,
including the agent-endpoint rung Vault, Nomad and Consul use. EVIDENCE,
probe: the plan reviewer called the real `compute_tile_states` at
`deployments/applications/services/dash/backend/src/dash_app/status.py:101`
with four single-job tiles covering all three rungs and folded the
results:

    per-job statuses: {'registry': 'down', 'registry-ui': 'up',
                       'vault': 'up', 'ghost': 'unknown'}
    fold(registry, registry-ui) = down
    fold(registry-ui, vault)    = up
    fold(registry-ui, ghost)    = unknown

Status resolution is already a pure function of the job NAME, so one
route per job plus a fold is a correct restatement, and the
`JobSource.CONSUL_NAME` branch composes with `judge_all` without
interference.

P16. The card render reads more than R11's first draft named. EVIDENCE:
`deployments/applications/services/dash/frontend/index.html:492` reads
`s.node` and `s.counts`;
`deployments/applications/services/dash/frontend/index.html:588` counts
tiles by a tile-level `status`. With no JS gate (P12), a payload missing
any of the three ships a page with no badges, no border colors and zeroed
counts while every backend test passes. R11 now names the full set.

P17. The `cluster`-marked tests do not run in the gate, so R18 cannot be
enforced by it. EVIDENCE:
`deployments/applications/services/dash/backend/pyproject.toml:37` sets
`addopts = "-m 'not cluster'"`, and P2's probe reports `2 deselected` —
both tests in
`deployments/applications/services/dash/backend/tests/test_cluster.py`.
