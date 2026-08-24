---
verdict: pass
plan: 9a22afb5ed1058a8f0b9d0f4dfc2f499fe1368debcc92ea18ad2525f7df46100
bound_paths: front-matter, 5, 6, 7, 8, 9, 10, premises
scope: e5f38a68063b84484538af78a1654076b407cf1112b95c04124de5dcbdc6760f
citations:
deployments/applications/services/dash/app/src/dash_app/status.py:25-31 = from localstack_cli.api.consul import Check / from localstack_cli.api.haproxy import Route / from localstack_cli.api.health import Health / from localstack_cli.api.health import judge_all as judge_all / from localstack_cli.api.nomad import Job, Node / from localstack_cli.api.services import JobSource / from localstack_cli.api.services import join as join
deployments/applications/services/dash/app/src/dash_app/live.py:9-16 = from localstack_cli.api.consul import list_checks, list_services / from localstack_cli.api.nomad import job_service_names, job_statuses, list_nodes
cli/src/localstack_cli/api/health.py:25 = from localstack_cli.api.nomad import Job, Node
cli/src/localstack_cli/api/nomad.py:22 = from localstack_cli.api._http import TIMEOUT_SECONDS, get_json
cli/src/localstack_cli/api/services.py:30-32 = from localstack_cli.api.consul import Check / from localstack_cli.api.haproxy import Route / from localstack_cli.api.nomad import Job
cli/src/localstack_cli/api/consul.py:22 = from localstack_cli.api._http import TIMEOUT_SECONDS, get_json
cli/src/localstack_cli/api/haproxy.py:22 = from localstack_cli.api.errors import ClusterError
cli/src/localstack_cli/api/haproxy.py:46-53 = class Route: / """One hostname the edge serves, and where it sends it.""" / name: str / hostname: str / backend_host: str / backend_port: int
cli/src/localstack_cli/api/_http.py:32 = ) -> tuple[Any, httpx.Headers]:
cli/src/localstack_cli/api/_http.py:12-18 = from localstack_cli.api.errors import ( MissingCapability, NotAuthenticated, NotFound, Timeout, Unreachable, )
deployments/applications/services/dash/app/src/dash_app/main.py:60 = except Exception as err:  # noqa: BLE001
deployments/applications/services/dash/app/src/dash_app/main.py:26 = FRONTEND_DIR = Path(__file__).parent / "frontend"
deployments/applications/services/dash/app/src/dash_app/main.py:77-79 = Route("/api/status", status_endpoint), / Mount("/", app=StaticFiles(directory=FRONTEND_DIR, html=True), name="static"),
deployments/applications/services/dash/app/pyproject.toml:7 = "localstack-cli",
deployments/applications/services/dash/app/pyproject.toml:58-59 = [tool.uv.sources] / localstack-cli = { path = "../../../../../cli", editable = true }
deployments/applications/services/dash/app/pyproject.toml:54-56 = [[tool.mypy.overrides]] / module = "localstack_cli.*" / ignore_missing_imports = true
deployments/applications/services/dash/Dockerfile:14-26 = "The path dependency in pyproject.toml is relative to this directory ... --no-editable is required. pyproject.toml declares the cli dependency editable ... found in adversarial review, AR1"
deployments/infrastructure/nomad_dash_read_role.tf:76-79 = bound_claims = { nomad_namespace = "default" nomad_job_id = "dash" }
deployments/infrastructure/nomad_dash_read_role.tf:84-88 = claim_mappings = { nomad_namespace = "nomad_namespace" nomad_job_id = "nomad_job_id" nomad_task = "nomad_task" }
deployments/infrastructure/services/nats.hcl:12-24 = network { port "client" { static = 4222 ... } port "monitor" {...} port "metrics" {...} }
deployments/infrastructure/services/postgres.hcl:12-21 = network { port "db" { static = 5432 ... } port "exporter" {...} }
deployments/infrastructure/services/postgres.hcl:70 =       vault {}
deployments/infrastructure/services/postgres.hcl:96 =       vault {}
deployments/infrastructure/services/acme.hcl:73 =       vault {
deployments/infrastructure/services/acme.hcl:154 =       vault {
deployments/applications/services/memex.hcl:44 =       vault {}
deployments/applications/services/memex.hcl:114 =       vault {}
deployments/infrastructure/services/backup-postgres.hcl:32,59 =       vault {} (task "pgdump" and task "upload", both vaulted)
deployments/infrastructure/services/oauth2-proxy.hcl:54 = OAUTH2_PROXY_UPSTREAMS="${dash_upstream}"
deployments/infrastructure/services/oauth2-proxy.hcl:10-13 = UPSTREAMS are PLURAL in env form though their flags are singular (--email-domain, --upstream)
deployments/infrastructure/services/oauth2-proxy.hcl:81 = image        = "quay.io/oauth2-proxy/oauth2-proxy:v7.13.0"
deployments/infrastructure/services.tf:415 =       dash_upstream = "http://127.0.0.1:8000"
deployments/applications/services.tf:94-104 = Dash (landing page) on radxa-dragon-q6a (L3) ... "allow from 192.168.2.50 to any port 8000 proto tcp"
deployments/applications/services.tf:187-206 = locals { dash_tiles_json = jsonencode(jsondecode(file(...))) } / resource "nomad_job" "dash" { jobspec = templatefile(...) }
deployments/applications/services/dash.hcl:1-90 = full file: task "dash", network port "http" 8000, vault { role = "dash" }, two template stanzas, service/check on /api/status
deployments/applications/services/dash.hcl:33 = image        = "ghcr.io/jasperhg90/dash:${dash_version}"
deployments/applications/services/dash.hcl:48-53 = comment block naming the dash-read Nomad token / Vault nomad secrets engine provenance
deployments/applications/services/dash.hcl:58-72 = Single-nested `.Data.secret_id` comment + template block
deployments/applications/services/dash/app/src/dash_app/frontend/index.html:561 = const response = await fetch('/api/status', { cache: 'no-store' });
deployments/applications/services/dash/app/tests/test_cluster.py:24 = return os.environ.get("DASH_ADDR", "http://192.168.2.50:8000")
deployments/applications/services/dash/app/tests/test_tiles.py:1-6 = import json / from pathlib import Path / import pytest / from dash_app.tiles import TileConfigError, load_tiles
deployments/applications/services/dash/app/src/dash_app/config.py:1-9 = Runtime config module, no cli import anywhere in the file
deployments/applications/services/dash/app/src/dash_app/tiles.py:1-14 = Tile config module, no cli import anywhere in the file
deployments/applications/justfile:54,61 = rebuild_dash: / cd "$(git rev-parse --show-toplevel)"
deployments/applications/justfile:35-43 = rebuild_hermes: single-directory recipe, no repo-root cd
.pre-commit-config.yaml:78-101 = four dash-app-* hooks, files: '^deployments/applications/services/dash/app/'
justfile:18-19 = pre_commit: / pre-commit run --all-files
cli/tests/test_api_nomad.py:11,27,37,46,63 = from localstack_cli.api.nomad import MAX_PAGES, NEXT_TOKEN_HEADER, job_statuses, list_nodes / def test_job_statuses_parses_the_live_capture / def test_the_token_is_sent_in_nomads_own_header / def test_pagination_is_followed / def test_pagination_passes_the_token_back
cli/pyproject.toml:5-12 = dependencies = [ "click>=8.0", "httpx>=0.28.1", "pyyaml>=6.0.3", "rich>=15.0.0", "textual==8.2.8", "typer>=0.27.0", ]
.loop/ledger.json (entries.L3-landing-dash-app) = stage "done", commit_sha "2bb164153540da78cda1c34cfd24c13d697e833b"
probe: docker run --rm quay.io/oauth2-proxy/oauth2-proxy:v7.13.0 --help (run this pass) = --upstream strings   the http url(s) of the upstream endpoint, file:// paths for static files or static://<status_code> for static response. Routing is based on the path
probe: uv sync --help (uv 0.11.16, this environment, run this pass) = --no-editable / Install any editable dependencies, including the project and any workspace members, as non-editable [env: UV_NO_EDITABLE=]
---

# Plan-validator verdict: L4-landing-dash-fe-be-split

## Deterministic floor

`loopctl verify-plan L4-landing-dash-fe-be-split` reports `valid`, with only
non-blocking "ambiguous file basename" warnings for `status.py`, `main.py`,
`pyproject.toml`, `services.tf` (each exists at more than one path in this
repo, which the tool flags but does not fail on). No broken anchor, no
hallucinated symbol, no dropped contract section, no orphaned test, no
unresolved `depends_on`, no bare premise. Proceeding to falsification.

## Premise verdict: SOUND

This plan's single most safety-critical claim — that the "narrow subset"
copy genuinely severs every runtime dependency on `cli` — is not just
cited, it is TRUE by direct trace of all five `cli` source files this
ticket names, function body by function body. Every other explicit
premise (P1-P16) resolves to `HOLDS` against the live repo, several
re-confirmed by a fresh probe I ran myself this pass rather than trusting
the plan's own captured probe text. One premise (P10) is honestly marked
`UNCERTAIN` by the plan itself and correctly kept out of the load-bearing
path for the decision it feeds. One minor, non-blocking inaccuracy in §7's
prose (not a premise) is noted below.

## Per-assumption findings

- **P1 — HOLDS.** `deployments/applications/services/dash.hcl:1-90` (full
  file read).
  > task "dash" { driver = "podman" ... network { port "http" { static = 8000 } } ... vault { role = "dash" } ...
  One task, `network_mode = "host"` (`:34`), one static port 8000
  (`:12-14`), `vault { role = "dash" }` (`:54-56`), two `template` stanzas
  (`:67-72` token, `:79-82` tiles), one `service`/`check` on `/api/status`
  (`:20-30`). Every sub-anchor matches exactly.

- **P2 — HOLDS.** `deployments/applications/services/dash/app/src/dash_app/status.py:25-31`
  > from localstack_cli.api.consul import Check
  > from localstack_cli.api.haproxy import Route
  > from localstack_cli.api.health import Health
  > from localstack_cli.api.health import judge_all as judge_all
  > from localstack_cli.api.nomad import Job, Node
  > from localstack_cli.api.services import JobSource
  > from localstack_cli.api.services import join as join
  Five source files (`consul`, `haproxy`, `health`, `nomad`, `services`),
  and `haproxy.Route` is real and load-bearing (`build_routes`,
  `status.py:80-87`, constructs a synthetic `Route` per tile). The
  operator's own verbal enumeration in §3 omitted `haproxy` — the plan's
  correction is accurate, not invented.

- **P3 — HOLDS.** `deployments/applications/services/dash/app/src/dash_app/live.py:9-16`
  > from localstack_cli.api.consul import list_checks, list_services
  > from localstack_cli.api.nomad import job_service_names, job_statuses, list_nodes
  No `cli.api.services`/`cli.api.haproxy` import here — confirmed, those
  two only appear in `status.py`.

- **P4 — HOLDS.** `deployments/applications/services/dash/app/pyproject.toml:6-9`
  > dependencies = [
  >     "localstack-cli",
  >     "starlette>=1.6.0",
  >     "uvicorn>=0.52.4",
  > ]
  No `httpx`. And `cli/src/localstack_cli/api/_http.py:10`
  > import httpx
  is where it actually arrives today, transitively. Dropping the `cli`
  path dependency drops `httpx` with it.

- **P5 — HOLDS.** `deployments/infrastructure/services/nats.hcl:12-24`
  > network {
  >   port "client" { static = 4222 ... }
  >   port "monitor" { static = 8222 ... }
  >   port "metrics" { static = 7777 ... }
  > }
  and `deployments/infrastructure/services/postgres.hcl:12-21`
  > network {
  >   port "db" { static = 5432 ... }
  >   port "exporter" { static = 9187 ... }
  > }
  Both group-level, both multi-task jobs. I grepped every `task "` block
  across every `.hcl` file in the repo (`deployments/**`, plus
  `tests/wi-vault-probe.nomad.hcl` and `rescue-ssh.nomad.hcl` for good
  measure) and found no `network { port ... }` nested inside any `task {}`
  block anywhere.

- **P6 — HOLDS.** `deployments/infrastructure/services/postgres.hcl:70,96`
  > vault {}
  (task "postgres"), and the same at `:96` (task "postgres-exporter") —
  both vaulted, task-scoped. Same shape confirmed at
  `deployments/infrastructure/services/acme.hcl:73,154` (task "issue" /
  task "store", both `vault { role = "${vault_role}" }`) and
  `deployments/applications/services/memex.hcl:44,114` (task "db-migrate"
  / task "memex", both `vault {}`). I ran my own repo-wide grep,
  `grep -rn "vault {" deployments --include="*.hcl"`, and it returns
  exactly the same set of task-nested-only hits the plan's own sweep
  claims — no group-level `vault {}` anywhere.

- **P7 — HOLDS.** Same sweep as P6, extended to `deployments/infrastructure/services/backup-postgres.hcl:32,59`
  > vault {}
  (task "pgdump", task "upload" — both vaulted) and
  `deployments/applications/services/hermes.hcl:40,396` (two `vault {}`
  hits, both tasks). Every multi-task job I found in the repo (`nats`,
  `postgres`, `acme`, `memex`, `backup-postgres`, `hermes`) either vaults
  every task or none — `nats` is the only all-none job. No job vaults one
  sibling task and not another. The claim holds across the whole repo, not
  just the four files the plan itself cites.

- **P8 — HOLDS.** `deployments/infrastructure/nomad_dash_read_role.tf:76-79`
  > bound_claims = {
  >   nomad_namespace = "default"
  >   nomad_job_id    = "dash"
  > }
  No `nomad_task` key. `:84-88`
  > claim_mappings = {
  >   nomad_namespace = "nomad_namespace"
  >   nomad_job_id    = "nomad_job_id"
  >   nomad_task      = "nomad_task"
  > }
  `claim_mappings` copies a claim value into the resulting token's
  metadata; it is not what a Vault JWT auth role gates authentication on
  — `bound_claims` is. This is standard, documented `vault_jwt_auth_backend_role`
  semantics, not something this file's text alone proves about a live
  Vault, and the plan's own §9 already discloses that risk honestly
  ("not independently probed against a live Vault"). I did not stand up a
  live Vault+Nomad JWT flow to probe this end-to-end (out of the
  reasonable bound for this pass and already disclosed as residual risk
  by the plan) — the static-text claim HOLDS; the live-behavior claim is
  UNCERTAIN in exactly the way the plan itself already says it is. See
  "Most dangerous assumption" below.

- **P9 — HOLDS, independently reproduced.** I ran my own probe rather than
  trusting the plan's captured text:
  `docker run --rm quay.io/oauth2-proxy/oauth2-proxy:v7.13.0 --help`
  (this pass, network available in this environment), captured:
  > --upstream strings   the http url(s) of the upstream endpoint, file:// paths for static files or static://<status_code> for static response. Routing is based on the path
  This matches the plan's quoted text and the exact deployed image tag
  (`deployments/infrastructure/services/oauth2-proxy.hcl:81`:
  `image = "quay.io/oauth2-proxy/oauth2-proxy:v7.13.0"`), so the probe was
  run against the same version this repo actually deploys, not a
  different one that happens to share a flag name.

- **P10 — UNCERTAIN, and correctly so.** The plan marks this UNCERTAIN
  itself and I found nothing in the `--help` output (or in a `grep -i
  upstream` sweep of the full text) that specifies prefix-vs-exact
  match or precedence between two upstreams. The plan's own honesty
  holds: it does not overclaim precision it does not have. Separately
  assessed: resolving §11 Q1 to option (a) on P9 alone, while leaving
  P10 open, is a SOUND basis for the DECISION (which upstream mechanism
  to build), not premature — because the decision only needs the
  capability to exist, the exact upstream values are deferred to
  implementation-time verification named explicitly at subticket 11, the
  file this touches is high-reversibility (§9: "a one-line diff back to
  the single-upstream form"), and a wrong path-match choice fails loudly
  (the browser gets a 404/wrong response) rather than silently. It would
  be unsound to trust EXACT upstream values on P9 alone; the plan does
  not do that — it only decides the MECHANISM on P9 and explicitly defers
  the values.

- **P11 — HOLDS.** `deployments/applications/services/dash/app/src/dash_app/frontend/index.html:561`
  > const response = await fetch('/api/status', { cache: 'no-store' });
  Grep for `fetch(` across the file returns exactly this one hit.

- **P12 — HOLDS, and its extension is independently confirmed.**
  `deployments/applications/services/dash/Dockerfile:14-26` (full text
  read):
  > The path dependency in pyproject.toml is relative to this directory
  > (../../../../../cli), so the copy above preserves the same relative
  > depth from the repo root as the source tree.
  >
  > --no-editable is required. pyproject.toml declares the cli dependency
  > editable (the right mode for local development against a live checkout),
  > but an editable install lands as a .pth file pointing at this stage's
  > absolute /build/cli path ... found in adversarial review, AR1
  The comment names only the `cli` path dependency as the flag's cause. I
  probed the extension claim ("becomes a no-op once that dependency is
  gone") myself: `uv sync --help` (uv 0.11.16, this environment), captured:
  > --no-editable
  >     Install any editable dependencies, including the project and any
  >     workspace members, as non-editable [env: UV_NO_EDITABLE=]
  This confirms the flag only acts on editable/path/workspace
  dependencies. Once `starlette`/`uvicorn`/`httpx` (ordinary PyPI
  packages) are all that remain, the flag genuinely has nothing left to
  act on.

- **P13 — HOLDS.** `deployments/applications/services.tf:94-104`
  > # Dash (landing page) on radxa-dragon-q6a (L3), colocated with
  > # oauth2-proxy. oauth2-proxy reaches it over loopback
  > # (127.0.0.1:8000), which never crosses this firewall; ...
  > dash = {
  >   host     = "192.168.2.50"
  >   ssh_user = "radxa"
  >   rules    = ["allow from 192.168.2.50 to any port 8000 proto tcp"]
  > }
  Matches the plan's paraphrase exactly.

- **P14 — HOLDS.** `cli/tests/test_api_nomad.py:27,37,46,63` — all four
  named tests exist verbatim:
  > def test_job_statuses_parses_the_live_capture() -> None:
  > def test_the_token_is_sent_in_nomads_own_header() -> None:
  > def test_pagination_is_followed() -> None:
  > def test_pagination_passes_the_token_back() -> None:
  all `@respx.mock`-decorated, no real network.

- **P15 — HOLDS.** `deployments/applications/services/dash/app/src/dash_app/main.py:29-52`
  (`_tile_json`, full function read) builds every field the plan claims
  (`key/name/desc/color/icon/category/node/status/counts` plus
  `url`/`connect`) from `Tile` + `TileState` alone. No separate
  frontend-local tile-metadata source exists.

- **P16 — HOLDS.** `cli/pyproject.toml:5-12`
  > dependencies = [
  >     "click>=8.0",
  >     "httpx>=0.28.1",
  >     "pyyaml>=6.0.3",
  >     "rich>=15.0.0",
  >     "textual==8.2.8",
  >     "typer>=0.27.0",
  > ]
  and L3's own dependency-bloat bullet exists at
  `.loop/plans/L3-landing-dash-app.md:526-527,621`. Requirement 2 (zero
  `cli` dependency) genuinely retires this risk rather than merely
  deferring it.

- **P17 (added, implicit) — HOLDS.** The plan's Decision 2 ("no `cli`
  dependency, at all") stands or falls on whether the five copied `cli`
  source modules have any import that escapes the enumerated copy list.
  I read all five files in full
  (`cli/src/localstack_cli/api/health.py`, `nomad.py`, `services.py`,
  `consul.py`, `haproxy.py`) and traced every function actually named in
  Requirement 3:
  - `health.py` imports only `nomad.Job`/`Node` (already in the copy) and
    stdlib.
  - `nomad.py`'s `job_statuses`/`list_nodes`/`get_job` import only
    `_http.get_json`/`TIMEOUT_SECONDS` — Requirement 4 supplies a local
    replacement, so this resolves cleanly, not silently.
  - `services.py`'s `join`/`_check_state`/`_sole_tag_carrier` reference
    only `Check` (consul, copied), `Route` (haproxy, copied), `Job`
    (nomad, copied), and stdlib.
  - `consul.py`'s `list_checks`/`list_services` import only `_http`
    (replaced) and stdlib; `Check.failing` is a property on the copied
    dataclass itself, no separate import needed.
  - `haproxy.py:46-57`'s `Route` dataclass imports only
    `dataclasses.dataclass` — critically, `haproxy.py:22`'s
    `from localstack_cli.api.errors import ClusterError` is used ONLY by
    `HaproxyParseError`/`parse_routes`, which Requirement 3 explicitly
    excludes ("never `parse_routes`/`HaproxyParseError`/the regexes").
  The one place a naive full-module copy WOULD have dragged in
  `cli/src/localstack_cli/api/errors.py` (`ClusterError`,
  `NotAuthenticated`, `MissingCapability`, etc. — see
  `cli/src/localstack_cli/api/_http.py:12-18`) is `_http.get_json`'s own
  typed-error raises, and Requirement 4 explicitly and correctly declines
  to replicate that taxonomy, citing `main.py:60`'s broad
  `except Exception` as the reason it is not behaviorally load-bearing.
  Every escape hatch a naive copy could have missed is accounted for.
  The narrow-subset copy, exactly as enumerated, is genuinely complete
  and genuinely severs the `cli` dependency at runtime, not just at the
  two call sites the operator originally named.

## Minor observations (non-blocking, no fix required)

- §7's tests bullet says "import-path edits only for the first two
  [`test_status.py`, `test_tiles.py`]"
  (`deployments/applications/services/dash/app/tests/test_tiles.py:1-6`):
  > import json
  > from pathlib import Path
  > import pytest
  > from dash_app.tiles import TileConfigError, load_tiles
  `test_tiles.py` has no `localstack_cli` import at all, so there is
  nothing to edit there — only `test_status.py` needs the import rewire.
  Harmless (the implementer opens the file, finds nothing to change,
  moves on); not worth a required fix.
- §7's "single-directory build context model" cites
  `hermes/Dockerfile` as precedent for the new backend Dockerfile's
  narrowed context. `deployments/applications/services/hermes/Dockerfile`
  doesn't actually `COPY` any local source tree at all (it extends a base
  agent image and installs from released wheel URLs), so it is a weaker
  analogy than the plan implies — it never needed repo-root context in
  the first place, unlike dash's current Dockerfile. Cosmetic; the
  §7 CREATE bullet is explicitly marked "indicative" and binds nothing.
- §7's "(Requirement 8's finding, P12)" attribution for dropping the
  justfile's `cd "$(git rev-parse --show-toplevel)"` line
  (`deployments/applications/justfile:61`) is more directly a consequence
  of Requirement 2 (dropping `cli`, hence dropping the repo-root
  `COPY cli` need — see the Dockerfile's own comment at
  `deployments/applications/services/dash/Dockerfile:1-5`) than of
  Requirement 8 (`--no-editable`). The underlying reasoning is sound and
  fully supported by the anchors; only the cross-reference label is
  slightly loose.

## Most dangerous assumption

**P8** — that `nomad_dash_read_role.tf`'s `bound_claims` (job-scoped, not
task-scoped) really does let any task in the `dash` job authenticate under
role `"dash"` on a LIVE Vault, not just in the HCL text. The static claim
is well supported by the file itself and by standard, documented Vault JWT
auth-backend-role semantics (`bound_claims` gates; `claim_mappings` only
copies values into token metadata). It was not independently probed
against a running Vault this pass — the plan's own §9 already discloses
this honestly as an unconfirmed risk with a named fallback (a
`nomad_task` addition to `bound_claims`). If it is wrong, Requirement 6's
explicit "zero Terraform edit" claim breaks, but the failure mode is loud
and cheap to detect (`terraform plan` showing an unexpected diff, or the
backend task failing to broker a Nomad token) rather than silent, so the
blast radius stays contained to this one requirement.

## Contract hygiene

- Every requirement in §6 (13 items) names a producer in §7: verified by
  walking each requirement against the code-surface bullet that builds it
  (dash.hcl edits for 1/5/6/7/11, the five CREATE modules for 3/4, the
  Dockerfile edit for 8, the pre-commit edit for 12, the docs edit for
  13, and the unchanged `_tile_json`/ported tests for 9/10). No
  `unmeasurable-requirement` gap.
- Non-goals (§5), Tests-homed-in-surface (§8 tests all listed in §7),
  and the resolved fork (§11 Q1, surfaced with both options and a
  recommendation before being resolved) all meet the create-ticket
  contract.
- Gates discovered from the repo, not assumed: `justfile:18-19`
  (`pre_commit: pre-commit run --all-files`) matches exactly;
  `scripts/tf_validate.sh` exists; `pyproject.toml:29-36`'s
  `cluster`-marker/`addopts` pair matches (`deployments/applications/services/dash/app/pyproject.toml:33-36`
  confirmed as the actual line range, not 29-36 — see note below).

One small citation-range nit found while checking gates: the plan's own
restrictions bullet cites `pyproject.toml:29-36`'s
"existing `markers`/`addopts` pair" for the cluster-marker convention.
Reading the file, line 29 is `[tool.pytest.ini_options]`, line 30 is
`testpaths = ["tests"]`, lines 31-32 are a comment, and only lines 33-35
are `markers = [...]` with `addopts` at line 36 — the cited range (29-36)
fully contains the actual pair, just with four unrelated lines ahead of
it. This resolves and supports the claim; it is not a `BREAKS`, just a
slightly loose range worth an implementer's second glance.

## Summary

SOUND. Every explicit premise (P1-P16) holds against the live repo, most
re-verified independently rather than trusting the plan's own quoted
evidence, and two (P9, P12's extension) were re-probed fresh this pass
with matching captured output. The single UNCERTAIN premise (P10) is
honestly marked and correctly kept out of the load-bearing path for the
decision it feeds. The one implicit premise most worth adding (P17: does
the narrow copy genuinely avoid every transitive `cli` import, including
`errors.py`) holds under a full line-by-line trace of all five source
modules. No required fixes.
