---
verdict: pass-with-required-fixes
plan: bee0c327a012bba8efc3fe4f68879d55ae132da0bd8d4352f872e2dfdbfcf843
bound_paths: front-matter, 5, 6, 7, 8, 9, 10, premises
scope: c820101e8ec94a2cd9e350f6426f51e86c78a49077b1502f2ab49b0c630dfc8f
fix_sections: 5, 6, 7, 8, 9, premises
citations:
  deployments/applications/services/dash/tiles.json:42 =     "job": "openviking",
  deployments/applications/services/dash/tiles.json:43 =     "node": "radxa-dragon-q6a",
  deployments/applications/services/dash/tiles.json:51 =     "icon": "<svg width=\"20\" height=\"20\" viewBox=\"0 0 22 22\" fill=\"none\"><path d=\"M11 3 L19 7 L11 11 L3 7 Z\" s […337 more chars]
  deployments/applications/services/dash/tiles.json:53 =     "job": "openviking",
  deployments/applications/services/dash/tiles.json:55 =     "connect": {
  deployments/applications/services/dash/tiles.json:59 =       "example": "curl -H \"X-API-Key: $OV_KEY\" \"https://openviking-api.lab.orangecluster.nl/api/v1/fs/ls?uri=viking://\""
  deployments/applications/services/dash/tiles.json:220 =     "job": "registry",
  deployments/applications/services/dash/tiles.json:222 =     "connect": {
  deployments/applications/services/dash/backend/src/dash_app/tiles.py:88 =     if category == "dashboard":
  deployments/applications/services/dash/backend/src/dash_app/main.py:41 =     }
  deployments/applications/services/dash/backend/src/dash_app/main.py:42 =     if tile.category == "dashboard":
  deployments/applications/services/dash/backend/src/dash_app/live.py:19 = def fetch_tile_states(config: Config, tiles: list[Tile]) -> list[TileState]:
  deployments/applications/services/dash/backend/src/dash_app/live.py:20 =     """Live per-tile status. Raises on a network/auth failure."""
  deployments/applications/services/dash/backend/src/dash_app/services.py:48 = # absence of a check is not evidence of health.
  deployments/applications/services/dash/backend/src/dash_app/status.py:101 = def compute_tile_states(
  deployments/applications/services/dash/backend/tests/test_cluster.py:39 =     assert "tiles" in body
  deployments/applications/services/dash/backend/tests/test_cluster.py:44 =         assert tile["node"]
  deployments/applications/services/dash/backend/tests/test_status.py:90 = def test_an_agent_endpoint_tile_falls_back_to_consul_check_state() -> None:
  deployments/applications/services/dash/backend/tests/test_main.py:116 = def test_connect_info_never_carries_a_credential_value(
  deployments/applications/services/dash/backend/tests/test_tiles.py:130 = def test_rejects_syntactically_invalid_json(tmp_path: Path) -> None:
  deployments/applications/services/dash/backend/pyproject.toml:37 = addopts = "-m 'not cluster'"
  deployments/applications/services/dash/frontend/index.html:416 =       <span class="hint">degraded first, then alphabetical &middot; click to open</span>
  deployments/applications/services/dash/frontend/index.html:437 =   <div class="footnote">Status comes from Nomad job and allocation state, cross-checked against Consul health checks. Va […163 more chars]
  deployments/applications/services/dash/frontend/index.html:474 =   function cardHtml(s, kind) {
  deployments/applications/services/dash/frontend/index.html:492 =         <div class="card-node tabular">${escapeHtml(s.node)}${s.counts ? ' &middot; ' + s.counts : ''}</div>
  deployments/applications/services/dash/frontend/index.html:552 =   function sortTiles(tiles) {
  deployments/applications/services/dash/frontend/index.html:578 =     const tiles = data.tiles || [];
  deployments/applications/services/dash/frontend/index.html:588 =     const counts = tiles.reduce((acc, s) => {
  deployments/applications/services/dash.hcl:122 =       ### contains no dollar-sign characters (confirmed by grep), so
  deployments/applications/services/dash.hcl:126 =         data        = <<-EOH
  deployments/applications/services/dash.hcl:127 =         ${tiles_json}
  deployments/applications/services.tf:586 = ### backend task only -- the frontend has no separate tile-metadata source
  deployments/applications/services.tf:589 =   dash_tiles_json = jsonencode(jsondecode(file("${path.module}/services/dash/tiles.json")))
  deployments/applications/services.tf:599 =       dash_frontend_version = "0.2.1"
  deployments/applications/services.tf:716 = # resource "nomad_job" "memex" {
  deployments/applications/services/registry.hcl:16 =       value     = "ubuntu"
  deployments/applications/services/registry-ui.hcl:8 =       value     = "radxa-dragon-q6a"
  deployments/infrastructure/services/prometheus.hcl:9 =       value     = "ubuntu"
  deployments/infrastructure/services/prometheus.hcl:30 =         name = "prometheus"
  deployments/infrastructure/services/prometheus.hcl:170 =           # Auto-discover any service tagged "prometheus" in Consul
  deployments/infrastructure/services/alloy.hcl:113 =         local.file_match "nomad_alloc" {
  deployments/infrastructure/services/haproxy.hcl:109 =     acl is_registryui hdr(host) -i registry-ui.lab.orangecluster.nl
  deployments/applications/justfile:52 =     #!/usr/bin/env bash
  deployments/applications/justfile:54 =     tag=$(grep -E '^\s*dash_backend_version\s*=' services.tf | head -1 | sed -E 's/.*"([^"]+)".*/\1/')
  deployments/applications/justfile:89 =     tag=$(grep -E '^\s*dash_frontend_version\s*=' services.tf | head -1 | sed -E 's/.*"([^"]+)".*/\1/')
  deployments/applications/justfile:90 =     image="ghcr.io/jasperhg90/dash-frontend:${tag}"
  .pre-commit-config.yaml:5 =     hooks:
  .pre-commit-config.yaml:6 =       - id: check-json
  .pre-commit-config.yaml:12 =       - id: detect-private-key
  .pre-commit-config.yaml:13 =       - id: end-of-file-fixer
  .pre-commit-config.yaml:117 =       # line for line, scoped to its own path. The dash frontend
  .pre-commit-config.yaml:144 =         files: '^deployments/applications/services/dash/(backend/|tiles\.json$)'
  justfile:19 =     pre-commit run --all-files
  docs/dash-landing-page.md:7 = Registry). Dashboard tiles link out. Agent and backend tiles open a modal
  docs/dash-landing-page.md:40 = - `category`: `"dashboard"`, `"agents"`, or `"backend"`.
  docs/dash-landing-page.md:46 = - `"dashboard"` tiles need `url`. `"agents"` and `"backend"` tiles need a
  TODO.md:6 = - dash: we have FE services but they also have a BE -- need instructions for BE and then button to go to FE.
---

rebound-by: JasperHG90 2026-09-06T10:58:42Z (reason: Applied all seven required fixes from the plan-validator verdict: added test_cluster.py, docs/dash-landing-page.md, dash.hcl and TODO.md to the code surface; corrected R12 and risk 1 to the probed heredoc behavior and widened the ban to %{; rewrote R11 to name the full per-tile payload the page reads; repointed the footnote anchor and eight drifted anchors; homed the stale dash.hcl:122 comment. Every edit is inside fix_sections.)

# Premise verdict: PARTIALLY SOUND

The approach is sound and the decomposition is buildable. The plan's core
mechanism claim (P10, which it ranks as its own likeliest failure) is
falsified by probe, and its declared code surface is incomplete by two
files. Both are fixable inside the bound sections without changing the
approach.

Deterministic floor first: `loopctl verify-plan L6-landing-dash-service-groups`
returned `valid` with four warnings, all of them the R14-R17 cross-cutting
warning that lines 229-232 of the plan already pre-empt. No hard fail, so I
proceeded to the falsification.

## Per-assumption findings

### Stated premises

- **P1 — HOLDS.** Probe, `.loop/scratch/L6-landing-dash-service-groups.plan-validator/p1_tiles.py`:

      count 17
      Counter({'dashboard': 9, 'backend': 5, 'agents': 3})
      keys ['phoenix', 'grafana', 'bifrost', 'openviking', 'openviking-api',
            'consul', 'minio', 'nomad', 'vault', 'registry-ui', 'postgres',
            'nats', 'redis', 'hermes', 'memex', 'tempo', 'registry']

  Exactly the plan's numbers. I also checked R2's table against that key
  list: 17 minus memex, openviking-api and registry-ui is 14, and R2 names
  14 existing tiles plus prometheus. No service is silently dropped.

- **P2 — HOLDS.** Re-ran the baseline:
  `uv run --project deployments/applications/services/dash/backend pytest
  deployments/applications/services/dash/backend/tests -q` returned
  `38 passed, 2 deselected, 1 warning in 0.28s`. Same counts as the plan
  claims (0.28s vs its 0.17s wall clock, which is noise). The 2 deselected
  are `test_cluster.py`, which matters below.

- **P3 — HOLDS on the claim, one anchor is off by one.**
  `deployments/applications/services/dash/backend/src/dash_app/tiles.py:88`
  > `    if category == "dashboard":`

  That anchor supports the either/or. The second anchor,
  `deployments/applications/services/dash/backend/src/dash_app/main.py:41`,
  does not:
  > `    }`

  It is the closing brace of the base `body` dict. The payload branch the
  premise means is one line down at `main.py:42`:
  > `    if tile.category == "dashboard":`

- **P4 — BREAKS as written.** The claim is true; neither cited anchor
  carries it. `deployments/applications/services/dash/tiles.json:43`
  > `    "node": "radxa-dragon-q6a",`

  and `deployments/applications/services/dash/tiles.json:51`
  > `    "icon": "<svg width=\"20\" height=\"20\" viewBox=\"0 0 22 22\" fill=\"none\"><path d=\"M11 3 L19 7 L11 11 L3 7 Z\" s […337 more chars]`

  A node value and a 400-character inline SVG. The two lines that actually
  name the shared job are `tiles.json:42` and `tiles.json:53`, both
  > `    "job": "openviking",`

  Repoint them. The premise survives on the corrected anchors.

- **P5 — HOLDS.** `deployments/applications/services/registry.hcl:16`
  > `      value     = "ubuntu"`

  and `deployments/applications/services/registry-ui.hcl:8`
  > `      value     = "radxa-dragon-q6a"`

  Two `nomad_job` resources register them (`services.tf:320`, `:617`), two
  different `constraint` values pin them. Two jobs, two nodes, confirmed.

- **P6 — HOLDS.** `deployments/applications/services.tf:716`
  > `# resource "nomad_job" "memex" {`

  The whole block is commented from 716 through the end of the resource,
  under the "Staged, not dead" comment at `:712`.

- **P7 — HOLDS.** `deployments/infrastructure/services/prometheus.hcl:170`
  > `          # Auto-discover any service tagged "prometheus" in Consul`

  The `regex: ".*,prometheus,.*"` / `action: keep` pair sits at `:176-177`
  under that comment, so the cited line states the contract even though the
  mechanism is six lines below it. The contrast holds:
  `deployments/infrastructure/services/alloy.hcl:113`
  > `        local.file_match "nomad_alloc" {`

  discovers by path glob (`__path__ = "/nomad/alloc/*/alloc/logs/*.std*.[0-9]*"`
  at `:115`) and names no service. Prometheus needs the service author to
  act; Loki does not.

- **P8 — HOLDS.** `deployments/infrastructure/services/prometheus.hcl:9`
  > `      value     = "ubuntu"`

  and `deployments/infrastructure/services/prometheus.hcl:30`
  > `        name = "prometheus"`

  with an HTTP check on `/-/ready` at `:34-40`. I also confirmed R10's "no
  `fe`" half: `grep -n "prometheus" deployments/infrastructure/services/haproxy.hcl`
  returns one hit, `:130` (`http-request use-service prometheus-exporter`),
  which is HAProxy's own exporter, not a route to Prometheus. Prometheus has
  no edge hostname, so a `fe.url` would be unreachable.

- **P9 — HOLDS.** `deployments/applications/services.tf:589`
  > `  dash_tiles_json = jsonencode(jsondecode(file("${path.module}/services/dash/tiles.json")))`

  and `deployments/applications/services/dash.hcl:127`
  > `        ${tiles_json}`

  inside the heredoc opened at `dash.hcl:126`. The config's bytes really do
  become jobspec text.

- **P10 — BREAKS.** Code-form, so I demonstrated it rather than reading it.
  Scratch: I emulated `templatefile()` on `dash.hcl` (unescape `$${`,
  substitute the five vars, splice compact `jsonencode` output) and fed the
  result to the same HCL2 parser the Nomad provider uses,
  `nomad job run -output`. Captured output across eight variants of one
  tile's `desc`:

      bare-dollar            PARSED  identical
      dollar-ident           PARSED  identical
      dollar-nomad-var       PARSED  identical
      dollar-string-expr     FAILED  Error parsing job file
      dollar-invalid-expr    FAILED  Error parsing job file
      dollar-unterminated    FAILED  Error parsing job file
      pct-directive          PARSED  MANGLED -> 'x YES y'
      pct-bare               FAILED  Error parsing job file

  The first half of P10 holds: a bare `$` parses and round-trips byte for
  byte, and `deployments/applications/services/dash/tiles.json:59`
  > `      "example": "curl -H \"X-API-Key: $OV_KEY\" \"https://openviking-api.lab.orangecluster.nl/api/v1/fs/ls?uri=viking://\""`

  survives the render untouched (`has $OV_KEY True`).

  The second half is wrong as stated. `${OV_KEY}` did NOT fail the parse:
  it parsed clean and was preserved verbatim in the template body
  (`has ${OV True`). Nomad's jobspec parser deliberately passes an
  unresolvable `${...}` through so its own runtime interpolation still
  works. Only a `${...}` whose contents are a valid or malformed HCL
  EXPRESSION (`${"literal"}`, `${a b}`, an unterminated `${`) fails. So
  R12's rationale, "`${` opens Nomad's own interpolation ... the failure
  surfaces only at `terraform apply`", and risk 1's identical claim, both
  describe a failure the parser does not produce for the likeliest form,
  which is exactly the form the shipped `$OV_KEY` example would take if
  someone braced it.

  Worse for the guard: `%{ if true }YES%{ endif }` PARSED and silently
  rewrote the tile's text to `x YES y`. That is the failure R12 is really
  protecting against, it corrupts bytes instead of failing loudly, and R12
  bans only `${`.

  The third sub-claim holds. `deployments/applications/services/dash.hcl:122`
  > `      ### contains no dollar-sign characters (confirmed by grep), so`

  is stale: `grep -n '\$' .../tiles.json` returns line 59.

- **P11 — HOLDS on the claim, both anchors miss.**
  `deployments/applications/justfile:52`
  > `    #!/usr/bin/env bash`

  is the recipe's shebang, and `deployments/applications/justfile:90`
  > `    image="ghcr.io/jasperhg90/dash-frontend:${tag}"`

  consumes the tag rather than reading it. The two lines that grep
  `services.tf` are `:54` and `:89`, e.g.
  > `    tag=$(grep -E '^\s*dash_frontend_version\s*=' services.tf | head -1 | sed -E 's/.*"([^"]+)".*/\1/')`

  The CI half holds: `.github/workflows/` holds only `claude-ollama.yaml`
  and `hermes-interactive.yaml`, and `grep -il dash .github/workflows/*`
  returns nothing.

- **P12 — HOLDS.** `.pre-commit-config.yaml:117`
  > `      # line for line, scoped to its own path. The dash frontend`

  The sentence runs to `:119` ("holds no Python at all (L4: static files
  only), so it needs no hooks here"), and no JS linter or test hook exists
  anywhere in the file.

- **P13 — HOLDS.** `.pre-commit-config.yaml:144`
  > `        files: '^deployments/applications/services/dash/(backend/|tiles\.json$)'`

  The pattern covers the tile config, so `dash-backend-pytest` fires on a
  config-only change.

- **P14 — HOLDS.** `git ls-files deployments/applications/services/registry-ui`
  returns tracked backend and frontend sources;
  `deployments/infrastructure/services/haproxy.hcl:109`
  > `    acl is_registryui hdr(host) -i registry-ui.lab.orangecluster.nl`

  and the ledger reports `{'slug': 'L5-landing-registry-tab', 'stage': 'blocked'}`
  while `L4-landing-dash-fe-be-split`, the plan's `depends_on`, is `done`.
  Citing the code rather than declaring the dependency is the right call.

### Implicit premises the plan leans on

- **P15 (implicit) — BREAKS. Section 7's code surface is not complete.**
  Two files the change must touch are neither listed in section 7 nor
  excluded in section 5.

  First, `deployments/applications/services/dash/backend/tests/test_cluster.py:39`
  > `    assert "tiles" in body`

  and `:44`
  > `        assert tile["node"]`

  R11 replaces the top-level `tiles` key with `groups` and moves `node`
  into the per-job objects, so both assertions become false. And nothing
  catches it: `deployments/applications/services/dash/backend/pyproject.toml:37`
  > `addopts = "-m 'not cluster'"`

  which is why the baseline reads `2 deselected`. This test ships broken
  and green, and surfaces only when the operator runs `-m cluster` against
  the deployed job.

  Second, `docs/dash-landing-page.md:40`
  > - `category`: `"dashboard"`, `"agents"`, or `"backend"`.

  and `:46`
  > - `"dashboard"` tiles need `url`. `"agents"` and `"backend"` tiles need a

  and `:7`
  > `Registry). Dashboard tiles link out. Agent and backend tiles open a modal`

  Every one of those sentences is falsified by R1, R3, R5 and R7. This repo
  runs a documentation review pass (`.loop/config.json`), so the omission
  costs a review cycle at best.

  A third, weaker one: P10 itself notices `dash.hcl:122` is stale, but no
  section 7 row homes the fix and no section 5 line excludes it. Editing
  that comment re-registers the job, which this ticket pays for anyway via
  the R13 version bump.

- **P16 (implicit) — BREAKS. R11 does not name every payload field the page
  reads.** R11 says the per-tile JSON carries "`fe` and/or `connect` plus a
  `jobs` array of `{name, node, status}`". The current card render needs
  more than that: `deployments/applications/services/dash/frontend/index.html:492`
  > `        <div class="card-node tabular">${escapeHtml(s.node)}${s.counts ? ' &middot; ' + s.counts : ''}</div>`

  and the badge and inset border key off a tile-level `s.status`, and
  `deployments/applications/services/dash/frontend/index.html:588`
  > `    const counts = tiles.reduce((acc, s) => {`

  counts tiles by that same field. R4 defines the folded tile status, but
  R11 never puts it in the payload and no section 8 test pins it there:
  `test_a_two_job_tile_reports_the_worst_of_the_two` lives in
  `test_status.py`, one layer below the JSON. Section 7's frontend row is
  silent on what the card foot shows once a tile has two jobs on two nodes,
  and `counts` has no home at all in the new shape. With no frontend gate
  (P12 holds), this seam is exactly where a silent regression lands, which
  is the plan's own risk 3.

- **P17 (implicit) — HOLDS. R4's worst-of fold is achievable on today's
  ladder.** This was the sharpest question, so I demonstrated it rather
  than reasoning about it. Scratch `p_fold.py` calls the real
  `compute_tile_states` at
  `deployments/applications/services/dash/backend/src/dash_app/status.py:101`
  with four single-job tiles covering all three rungs, then folds:

      per-job statuses: {'registry': 'down', 'registry-ui': 'up', 'vault': 'up', 'ghost': 'unknown'}
      fold(registry, registry-ui) = down
      fold(registry-ui, vault)    = up
      fold(registry-ui, ghost)    = unknown

  Status resolution is already a pure function of the job NAME, and the
  agent-endpoint rung (`vault`, resolved through `join()`'s
  `JobSource.CONSUL_NAME` branch) composes with the `judge_all` rung
  without interference. So one route per job plus a fold is a correct
  restatement, and it produces exactly what risk 5 wants: a dead `registry`
  behind a healthy `registry-ui` reads `down`. R4's `unknown` over `up`
  choice is well-grounded at
  `deployments/applications/services/dash/backend/src/dash_app/services.py:48`
  > `# absence of a check is not evidence of health.`

  Two mechanical consequences the plan already lists and I confirmed are
  needed: `live.py` must key `service_names` per job rather than per tile
  (today `deployments/applications/services/dash/backend/src/dash_app/live.py:19`
  > `def fetch_tile_states(config: Config, tiles: list[Tile]) -> list[TileState]:`

  builds it from `tile.job`), and `build_routes` must emit one route per
  job. Both are in section 7. Note the field name `jobs` keeps the existing
  overload where an agent endpoint's "job" is really a Consul service name;
  that is pre-existing and documented, but the doc line that documents it
  (`docs/dash-landing-page.md:41-43`) is inside the file P15 flags.

- **P18 (implicit) — BREAKS.** "Banning `${` is a sufficient guard for the
  heredoc splice." Falsified by the same probe as P10: `%{ ... }` passes
  the ban, passes the parse, and silently rewrites the config the job
  actually reads.

- **P19 (implicit) — BREAKS.** Section 7 asks the implementer to "Update
  the footnote (`:437`), which promises a sort order the page will no
  longer have."
  `deployments/applications/services/dash/frontend/index.html:437`
  > `  <div class="footnote">Status comes from Nomad job and allocation state, cross-checked against Consul health checks. Va […163 more chars]`

  The footnote says nothing about sorting; it describes where status comes
  from and stays true after this change. The line that promises the order
  is `deployments/applications/services/dash/frontend/index.html:416`
  > `      <span class="hint">degraded first, then alphabetical &middot; click to open</span>`

  which is inside the section block at `:413` that the same row already
  deletes. So the row asks for an edit that is not needed, on a false
  reading, while the real promise is removed incidentally.

## Most dangerous assumption

**P16** — that R11's payload contract names everything the page reads. If
it is wrong, `just pre_commit` goes green, every backend test passes, and
the operator gets a landing page with no status badges, no border colors
and zeroed summary counts. Nothing in this repo can catch that: P12 holds,
there is no JS gate, and the one end-to-end check that touches the payload
(`test_cluster.py`) is both deselected and, per P15, already broken by the
same change. P10 is the more surprising falsification; P16 is the one that
ships.

## Required fixes

1. **Section 7 — add `deployments/applications/services/dash/backend/tests/test_cluster.py`.**
   R11 falsifies `test_cluster.py:39` and `:44`. Add a section 8 line for
   the updated assertions too, and say plainly that the file is deselected
   (`pyproject.toml:37`) so the gate will not catch a miss.
2. **Section 7 — add `docs/dash-landing-page.md`,** or exclude it in
   section 5 with a reason. `:7`, `:40`, `:41-43` and `:46` all document
   the schema this ticket removes.
3. **Section 6 R12 and section 9 risk 1 — correct the mechanism.** A
   `${IDENT}` does not fail the parse; it is preserved verbatim. Say what
   the probe found: `${` whose body is an HCL expression fails the parse,
   `${IDENT}` passes through to the deployed template, and `%{` either
   fails or silently rewrites the text. Widen R12 and its section 8 test to
   ban `%{` as well as `${`, since `%{` is the form that corrupts rather
   than shouts.
4. **Section 6 R11 — state the whole per-tile payload.** Name the
   tile-level folded `status`, decide what happens to `counts`, and say
   what the card foot renders for a two-job tile. Add a `test_main.py` case
   in section 8 that pins the folded status IN the payload, not only in
   `compute_tile_states`.
5. **Section 7 — repoint the frontend footnote anchor** from `:437` to
   `:416`, or drop the clause since `:416` dies with the section block.
6. **Repoint the drifted anchors** in the bound sections: R8
   `tiles.json:53` to `:55`; R9 `tiles.json:220` to `:222`; R13, risk 2 and
   P11 `justfile:52`/`:90` to `:54`/`:89`; P3 `main.py:41` to `:42`; P4
   `tiles.json:43`/`:51` to `:42`/`:53`; section 8 `.pre-commit-config.yaml:5`
   to `:6` and `:12` to `:13`; section 7 `live.py:20` to `:19`. Each
   resolves, which is why `verify-plan` passed, and none carries the claim
   attached to it.
7. **Decide the `dash.hcl:122` stale comment** — either a section 7 row or
   a section 5 non-goal. Do not leave it noticed and unhomed.

## Contract hygiene, secondary

- **Gates: discovered, correct.** `.loop/config.json` names `just pre_commit`
  and `justfile:19`
  > `    pre-commit run --all-files`

  matches. Every dash hook section 8 names exists with the stated behavior,
  modulo the two off-by-one anchors above.
- **Non-goals: explicit and specific.** Section 5 names the four copied-down
  modules, the memex teardown boundary, the deploy step and the CLI copy.
- **Tests homed:** every named test carries its file, except the
  `test_cluster.py` gap in fix 1.
- **Requirements reachable by a measurement:** R1-R13 each have a producer
  in section 7. R5 and R6 are checked only by hand, and the plan declares
  that openly in section 8 rather than pretending to a gate, which is the
  `declared-proxy` shape. R14-R17 are declared cross-cutting at lines
  229-232, which answers `verify-plan`'s four warnings.
- **Observation, not a refusal:** the open questions are the right two
  forks and both carry a recommendation. Two smaller decisions were settled
  silently and are worth an operator glance rather than a fix: R10 repurposes
  `connect.auth`/`connect.example`, whose dataclass docstring at
  `tiles.py:23` reads "How to connect to an agent- or backend-row service",
  to carry "how to get SCRAPED by prometheus" instead, and no `address` is
  named for a service with no edge hostname; and R1's optional per-group
  `hint` has no text specified for any of the six groups, while the three
  hints it replaces are load-bearing today (`index.html:416` is one of them).
- **Section 3 cites `TODO.md:6`**
  > `- dash: we have FE services but they also have a BE -- need instructions for BE and then button to go to FE.`

  This ticket closes that item. Section 7 does not list `TODO.md`.
  Advisory only; section 3 is outside the bound set.

## Scratch

Scratch created at `.loop/scratch/L6-landing-dash-service-groups.plan-validator/`.
Probe artifacts (the rendered jobspec variants and the three probe scripts)
removed at end of pass. The findings ledger
`.loop/scratch/L6-landing-dash-service-groups.plan-validator/findings.json`
is retained by the reviewer-brief contract so the next cycle inherits the
eight settled findings.
