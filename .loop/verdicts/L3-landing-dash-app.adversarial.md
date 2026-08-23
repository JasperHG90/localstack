---
verdict: pass
tree: 0eb318b976f808889f953340b1405b2f65196cac
---

# Adversarial review: L3-landing-dash-app (cycle 2)

No scope digest was included in this cycle's briefing either (only the tree
fingerprint), so per the reviewer-brief scope-binding rule the
`bound_paths:`/`scope:`/`citations:` header lines are omitted here and this
verdict falls back to whole-tree binding, same as cycle 1. The 25 files
under review (`git diff --cached --name-only` from the worktree root, one
more than cycle 1's 24 — the new `test_cluster.py`):
`deployments/applications/justfile`, `.pre-commit-config.yaml`,
`deployments/applications/services/dash/app/.gitignore`,
`deployments/applications/services/dash/app/pyproject.toml`,
`deployments/applications/services/dash/app/src/dash_app/{__init__.py,config.py,live.py,main.py,status.py,tiles.py,frontend/index.html}`,
`deployments/applications/services/dash/app/tests/{__init__.py,test_main.py,test_status.py,test_tiles.py,test_cluster.py}`,
`deployments/applications/services/dash/app/uv.lock`,
`deployments/applications/services/dash/Dockerfile`,
`deployments/applications/services/dash.hcl`,
`deployments/applications/services/dash/tiles.json`,
`deployments/applications/services.tf`,
`deployments/infrastructure/{nomad_dash_read_role.tf,services.tf,services/oauth2-proxy.hcl}`,
`docs/dash-landing-page.md`.

## Deterministic floor

`loopctl verify-eval-substance L3-landing-dash-app` reports bare `valid`,
no `warn:` lines, exit 0 — same clean result as cycle 1. No hard-fail, no
advisories fired (no positional-row citation, no un-narrowed grep scorer, no
undeclared `depends_on` row, no plan-drift, no
`assessed-statically-not-executed` annotation). `loopctl verify` reports
`ok` for tree `0eb318b976f808889f953340b1405b2f65196cac` both before and
after I independently re-ran `just pre_commit` (all 18 hooks passed,
matching `.loop/stamp.json`'s recorded `gate_exit: 0` for this exact tree).
Clean bill — proceeded to the semantic re-attack.

## Verdict: PASS

Both blocking defects from cycle 1 are now resolved by direct reproduction.
The one high-confidence-but-sandbox-unverifiable concern (AR2) is disclosed
plainly below rather than presented as proven, per this cycle's own
instruction, and does not on its own justify a fail: its evidence is
stronger this cycle than last (executable code, not just a comment, and a
repo-wide cross-check finding zero counterexamples), and its failure mode —
if it is still wrong — is the plan's own named, accepted "safe, visible
failure" risk category, not a crash or a silent leak.

### AR1 — RESOLVED, confirmed by direct reproduction: the container now imports `localstack_cli` and starts cleanly

`deployments/applications/services/dash/Dockerfile:28` now reads
`RUN uv sync --frozen --no-dev --no-editable`, up from cycle 1's `RUN uv
sync --frozen --no-dev`. I did not trust the diff or the new explanatory
comment (`Dockerfile:17-19`, "`--no-editable` installs cli as a real copy
inside `.venv` instead, so the final stage is self-contained") — I rebuilt
the exact Dockerfile from the current diff and ran the resulting image, the
same way I did in cycle 1:

    docker build --no-cache -f deployments/applications/services/dash/Dockerfile \
      -t dash-review-probe-c2:test .        # from the worktree root, current diff

The build log itself is the first piece of evidence: `uv sync` now reports
`Building localstack-cli @ file:///build/cli` /
`Built localstack-cli @ file:///build/cli` /
`+ localstack-cli==0.1.0 (from file:///build/cli)` — a real package build
and install, not an editable `.pth` redirect. I then ran, inside the built
image:

    docker run --rm --entrypoint python dash-review-probe-c2:test \
      -c "import localstack_cli; print(localstack_cli.__file__)"
    # -> /app/.venv/lib/python3.12/site-packages/localstack_cli/__init__.py

    docker run --rm --entrypoint python dash-review-probe-c2:test \
      -c "from localstack_cli.api.consul import list_checks, list_services"
    # -> succeeds (this is the exact import that raised ModuleNotFoundError
    #    in cycle 1's reproduction)

Finally I ran the actual entrypoint the way Nomad would (`CMD ["python",
"-m", "dash_app.main"]`, `Dockerfile:31`), with the four required env vars
set (`CONSUL_HTTP_ADDR`, `DASH_TILES_PATH`, `NOMAD_ADDR`,
`NOMAD_TOKEN_FILE`) and a stub `tiles.json`/token file mounted:

    INFO:     Started server process [1]
    INFO:     Application startup complete.
    INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)

No `ModuleNotFoundError`, no crash — Uvicorn bound the port cleanly.
Cleaned up (`docker rmi dash-review-probe-c2:test`, removed the `/tmp`
scratch fixtures); nothing in the repo tree was touched. AR1 is fully
resolved.

### AR2 — DOWNGRADED from blocking to disclosed, high-confidence-but-unverified: the Vault template field-path fix is well-supported but still cannot be proven from this sandbox

`deployments/applications/services/dash.hcl:69` now reads
`{{ with secret "nomad/creds/dash_read" }}{{ .Data.secret_id }}{{ end }}`,
dropping the extra `.data` hop cycle 1 flagged. I re-verified the cited
evidence myself rather than trusting the new comment
(`dash.hcl:58-67`, which itself cites "AR2"):

- `cli/src/localstack_cli/auth/broker.py:1-4` states, in its own words,
  "measured against the live cluster on 2026-08-02:
  `nomad/creds/deploy data.secret_id data.accessor_id`" — single-nested.
  Critically, this isn't just a comment: `broker.py:75-79` reads it that way
  in executable code — `data = response.get("data")`, then
  `token = data.get(token_field)` where `token_field` is `"secret_id"` for
  both `nomad` and `nomad_manage` engine rows in `_FIELDS` (`broker.py:32-36`).
  That code path is exercised by `cli`'s own test suite (part of the green
  `just pre_commit` run), so it is not merely asserted — it is a
  passing-tested claim about the shape Vault's `nomad` secrets engine
  actually returns.
- I extended cycle 1's cross-check: grepped every `secret "..."` template
  read across all 16 `.hcl` job specs in both `deployments/applications/`
  and `deployments/infrastructure/`. Every other `.Data.data.x` read
  resolves to a KV2 path (`redis_admin_secret`, `postgres_secret`,
  `minio_secret`, `telegram_secret`, `oidc_secret`, `cookie_secret`,
  `gcs_secret`, `transip_secret`, `grafana_secret`, `bifrost_admin_secret`,
  `bifrost_key_secret`, `memex_*_secret`, `phoenix_secret`). The only other
  `vault { role = ... }`-scoped stanza in the repo besides `dash.hcl` is
  `acme.hcl:73-75`, and its template still reads a KV2 path
  (`transip_secret`) via `.Data.data.x` — so it is not a counterexample to
  the KV2-vs-dynamic-secrets-engine distinction, it corroborates it.
  `nomad/creds/dash_read` remains the only non-KV2 dynamic-secret template
  read in this repo's job specs, and I found zero contradicting evidence
  anywhere in the tree.
- The plan itself (`.loop/plans/L3-landing-dash-app.md:507-509`) names
  exactly AR2's failure mode as an accepted risk, not a blocking one:
  "Getting the new Nomad ACL grant wrong is a two-sided risk. Too narrow:
  the status backend 403s and every tile reads UNKNOWN — a safe, visible
  failure." A wrong field path produces the same outcome class (an empty or
  failed template render → `config.read_nomad_token()` returns `None` →
  every tile reports `unknown`), which the plan's own author already
  weighed and accepted as the safe failure direction, distinct from a
  crash or a credential leak.

I could not reproduce this against a live Vault server — none is reachable
from this sandbox, the same disclosed limitation already accepted for the
ticket's missing live `terraform plan` (cycle 1's AR11). Per this cycle's
instruction, I am saying so plainly rather than presenting the fix as fully
proven: the evidence is strong (an executable, tested code path plus a
repo-wide absence of counterexamples) but it is still evidence by strong
analogy, not a live confirmation of `nomad/creds/dash_read`'s actual
response shape. Given the strength of the evidence, the total absence of
contradicting evidence, and that the plan's own risk framework already
accepts this failure mode as safe if the fix is somehow still wrong, this
does not block the ticket — but an operator should run `vault read
nomad/creds/dash_read` (or otherwise watch the dash tiles immediately after
the first real deploy) to close this out for certain, the same way the
disclosed `terraform plan` gap asks for a live check before fully trusting
the infra change.

### AR3 — RESOLVED, confirmed by running the test suite: the cluster-marked test exists, is excluded by default, is selected by `-m cluster`, and skips gracefully

`deployments/applications/services/dash/app/tests/test_cluster.py` is new:
`pytestmark = pytest.mark.cluster` (line 18) applies the marker to both
tests in the module, and each catches `httpx.TransportError` and calls
`pytest.skip(...)` rather than letting the request error propagate.  I ran
all three checks myself from inside the app's own project:

    uv run pytest -q
    # -> 18 passed, 2 deselected

    uv run pytest -m cluster -v
    # -> tests/test_cluster.py::test_status_endpoint_answers_with_live_tiles SKIPPED
    # -> tests/test_cluster.py::test_a_known_dashboard_tile_reports_a_real_status SKIPPED
    # -> 2 skipped, 18 deselected, exit code 0

Both cluster tests are excluded from the default run (matching
`pyproject.toml:36`'s `addopts = "-m 'not cluster'"`), both are selected by
`-m cluster`, and both skip cleanly (not error, not fail) against the
default unreachable address `http://192.168.2.50:8000` — which is the only
reproducible outcome available in this sandbox (no route to the real
cluster), exactly as expected. AR3 is fully resolved.

**Minor, non-blocking observation:** `test_cluster.py` imports `httpx`
directly, but `deployments/applications/services/dash/app/pyproject.toml`
never lists `httpx` as a direct dependency — it arrives only as a
transitive dependency of `localstack-cli` (which does declare
`httpx>=0.28.1` in `cli/pyproject.toml`), and it is pinned in `uv.lock`.
This works today and is reproducible, but it is an implicit rather than
declared dependency of the file that imports it by name. Not weighted into
the verdict; worth a follow-up nit if this bothers a future maintainer.

### AR4 — unchanged, minor, non-blocking: a dead field

`status.py`'s `compute_tile_states` still sets `TileState.checks` on every
tile, but `main.py`'s `_tile_json` still never reads it, and the frontend
still never requests it. Untouched by this diff. Noted for completeness,
not weighted into the verdict.

## Cycle-1 findings this diff did not touch — re-confirmed by scope check, not re-run in full

Per the reviewer-brief re-attach rule, I diffed the current staged tree
against cycle 1's reviewed diff before writing this section: the only files
that differ are `Dockerfile` (the `--no-editable` flag plus a comment),
`dash.hcl` (the template field path plus a comment), and the new
`test_cluster.py` (63 lines). Everything else — including every file each
of the following findings depends on — is byte-for-byte identical to what
cycle 1 already reviewed:

- **AR5 (Nomad ACL policy exactly minimal).** `nomad_dash_read_role.tf` is
  unchanged (still 94 lines, all additions in the current diff, identical
  content to cycle 1). Absence claim: nothing in this diff touches it.
- **AR6 (no credential-value leak).** `main.py`, `tiles.py`, `status.py`,
  `live.py`, `config.py`, and `tiles.json` are all unchanged. Absence
  claim: nothing in this diff touches any of them.
- **AR7 (no `haproxy.hcl` diff; `oauth2-proxy.hcl` and infra-root
  `services.tf` each carry exactly their one prior narrow edit).**
  Re-ran `git diff --cached --name-only`: still no `haproxy.hcl` entry.
  Re-ran `git diff --cached -- deployments/infrastructure/services/oauth2-proxy.hcl`:
  still exactly one line changed
  (`OAUTH2_PROXY_UPSTREAMS="static://200"` → `"${dash_upstream}"`).
- **AR9 (four `dash-app-*` pre-commit hooks fire).** `.pre-commit-config.yaml`
  is unchanged. Re-ran the full `just pre_commit` gate at this tree myself
  (not just trusted the stamp): all 18 hooks passed, including
  `Ruff (lint, dash app)`, `Ruff (format, dash app)`,
  `Mypy (strict, dash app)`, `Pytest (dash app)`.
- **AR10 (image tag pinned).** `dash.hcl:33` (`image = "ghcr.io/jasperhg90/dash:${dash_version}"`)
  and `services.tf:195` (`dash_version = "0.1.0"`) both unchanged.
- **The status-reuse / HAProxy-avoidance rationale.** `status.py` and
  `live.py` unchanged; nothing to re-verify.
- **The disclosed no-live-terraform-plan gap.** Unchanged limitation,
  still disclosed, still not scored as a defect — now joined by AR2's
  analogous, equally-disclosed live-Vault-verification gap above.

## Scope

Every changed file traces to the ticket's stated surface. The only
additions since cycle 1 are the `--no-editable` Dockerfile fix, the
`dash.hcl` template field fix, and the new `test_cluster.py` — each maps
directly to AR1, AR2, and AR3 respectively. No unrelated or drive-by
changes found.

## Why pass rather than pass-with-required-fixes

There is no further code change to request. AR1 is fixed and reproduced.
AR3 is fixed and reproduced. AR2's fix is the best this sandbox can verify
— stronger evidence than cycle 1 had (an executable, tested code path
rather than only a docstring, plus a repo-wide cross-check that found zero
counterexamples), it is contradicted by nothing in the repository, and its
own worst case is a failure mode the ticket's plan already named and
accepted as safe. Demanding a further diff change here would be asking for
proof this sandbox cannot produce, not a fix this sandbox can verify was
missed. Recommend the operator confirm AR2 with `vault read
nomad/creds/dash_read` (or by watching the dash tiles right after the first
real deploy) before fully trusting the token-read path in production —
noted here for the record, not blocking.
