---
verdict: pass
plan: e1fa7c5b176001429e0d2d98aaed8df11b00c1f7cd96e5139f4cca0d5a35ed00
---

# Plan review: D7-cli-service-join-consul-catalog (cycle 3)

## Deterministic floor

`loopctl verify-plan D7-cli-service-join-consul-catalog` returns `valid`.
`sha256sum` of the plan is `e1fa7c5b...5ed00`, matching the briefed
fingerprint exactly. Proceeded to falsification.

## Premise verdict

**SOUND.**

Both cycle-2 required fixes land, and I proved each rather than reading it.
Fix A's central claim now survives the exact probe that killed it last cycle:
a keyword-only `catalog` produces ten mypy strict errors at exactly the ten
call sites the plan names. Fix B's three numbers match a live re-measurement
to the unit. Nothing new is load-bearing.

## Cycle-2 fixes, verified

### Fix A — R2 is now enforceable — **HOLDS**, proven

I did not reason about mypy. I copied `cli/src` and `cli/tests` to a
scratchpad, patched `join()` to the exact shape R2 specifies
(`routes, jobs, checks, *, catalog: dict[str, list[str]],
service_names: dict[str, list[str]] | None = None`), and ran the repo's own
invocation, `mypy --config-file cli/pyproject.toml` with `strict = true`
(`cli/pyproject.toml:61-63`).

**(a) Positional is rejected.** Ten errors, `Found 10 errors in 2 files`,
every one `error: Too many positional arguments for "join"  [call-arg]`, at:

    tests/api/test_services.py: 38, 91, 101, 107, 116, 122, 128, 137, 146
    src/localstack_cli/commands/service.py: 100

That is the plan's list from R2 and §7, line for line, with nothing left over.
Contrast cycle 2, where the 4th-positional form produced **zero** errors. The
one-character-class change does exactly what R2 now claims.

**(b) Omission is rejected.** I rewrote `:38` to
`join(ROUTES, JOBS, CHECKS, service_names=NAMES)` — catalog omitted, no
positional overflow — and mypy returned
`error: Missing named argument "catalog" for "join"  [call-arg]`.

**(c) The correct form is clean.** Rewriting `:122` to
`join(ROUTES, JOBS, CHECKS, catalog={...}, service_names=NAMES)` dropped the
count from 10 to 9 with no error at `:122`. So the enforcement is precise, not
a blanket break.

**The ten call sites are exactly ten.** Grepped `cli/src` and `cli/tests`:
nine in `cli/tests/api/test_services.py` at the lines above, plus
`services.join(routes, jobs, checks, names)` at
`cli/src/localstack_cli/commands/service.py:100`. No other caller anywhere in
the package. The mypy run independently confirms the count, since it flagged
every caller and found no eleventh.

**The mechanism that makes this work is worth knowing.** The pre-commit mypy
hook runs over `cli/src cli/tests` (`.pre-commit-config.yaml:60`), not `src`
alone, which is precisely why keyword-only enforcement reaches the nine test
call sites and not just the production one. R2's claim depends on that and the
plan does not say so. Non-blocking, noted below.

### Fix B — Q2's arithmetic — **HOLDS**, re-measured live, not taken from the report

Tokenless `GET https://consul.lab.orangecluster.nl/v1/catalog/services` →
HTTP 200, just now. Counted from the response myself:

| Claim in Q2 / §4 | Plan says | Live | |
|---|---|---|---|
| catalog services | 25 | **25** | matches |
| services carrying `http` | 16 | **16** | matches |
| services carrying `monitoring` | 9 | **9** | matches |
| services carrying `s3` | exactly 1 (`minio`) | **1, `minio`** | matches |

`http`: bifrost, grafana, haproxy, haproxy-stats, hermes, loki, memex, minio,
minio-console, mlflow, nats-exporter, nats-monitor, nomad, nomad-client,
phoenix, prometheus. `minio -> ['http', 's3']` and
`minio-console -> ['http']`, both confirmed. Q2's conclusion follows: a
"resolve only on a unique tag match" rule already answers the `s3` case, and
the follow-up ticket starts from that instead of re-measuring.

My cycle-2 drift note has resolved itself rather than needing a fix: the
catalog is back to **25** (`talat-consumer` is gone, `hermes` has registered),
so §4 and P1's count is right as of today.

### Non-blocking note from cycle 2 — acted on, and the count is right

§7 now says `mock_cluster()` must mock `GET /v1/catalog/services` because
seven existing tests route through it. I counted: exactly **seven** tests
invoke the `service` command through `mock_cluster()` —
`test_service_renders_the_join` (:147), `..._never_prints_the_jobspec_credential`
(:162), `..._json_is_parseable` (:177), `..._open_prints_the_url_before_opening`
(:191), `test_a_denied_job_list_names_list_jobs_not_login` (:397),
`test_a_denied_nomad_read_probes_a_known_job_before_blaming_the_session`
(:453), `test_the_probe_does_not_run_when_the_read_succeeds` (:478). Seven is
exact.

## Per-assumption findings

### P1 — catalog lists `consul`, checks carry no `ServiceName: consul` — HOLDS, exactly

Re-probed live, tokenless: catalog holds `consul`, `nomad`, `vault`; `s3` is
not a service name. `GET /v1/health/state/any` returns **41** checks with
`ServiceName` counts `nomad` 3, `vault` 1, `consul` **0**, and **5** entries
with `ServiceName: ""`. Every number in P1 and §4 matches the wire.

### P2 — `vault` and `nomad` resolve by accident — HOLDS

`cli/src/localstack_cli/api/services.py:89` builds the rung-(b) set from
`{check.service for check in checks if check.service}`, and `:110` is the
`elif route.name in consul_services:` branch. P1's counts are what that set
yields, so `consul` cannot reach rung (b) and falls to `:122`.

### P3 — `s3` not resolvable by address, resolvable by tag, deferred — HOLDS

The measurement that was wrong in cycle 2 is now right (Fix B above). The
framing was already honest and is unchanged: §4 names the two real defeaters
(`ServicePort 0`, `minio-console` returning the identical node address),
states the tag rung "would work, and it is deferred rather than impossible",
and R1 keeps `dict[str, list[str]]` so no return type forecloses it.

### P4 — `backend` exists and is already serialized — HOLDS

`api/services.py:57` is `backend: str = ""`. `commands/service.py:73-74`
renders `["name", "url", "job", "source", "health"]` with `backend` absent.
Display-only change, as claimed. `.loop/plans/D3-cli-read-commands.md:445-451`
carries the requirement and names `consul` explicitly as a rung-(b) case,
which is the same defect from the other end.

### P5 — the catalog read needs no token — HOLDS

Tokenless catalog GET returned 200 on this pass.
`bootstrap/roles/consul_server/templates/consul.hcl.j2:29-32` sets both
`agent` and `default` to the agent token. `api/consul.py:25` is
`HEALTH_READ = "service:read"`, the capability name §7 reuses, and `:44-46` is
the existing tokenless `list_checks` over `/v1/health/state/any`.

### P6 — the gate is `just pre_commit` — HOLDS

`.pre-commit-config.yaml:37-72` runs ruff, ruff-format, mypy strict
(`--config-file cli/pyproject.toml cli/src cli/tests`) and pytest, all scoped
`files: '^cli/'`.

### P7 — test 6 is red-first against `main` — HOLDS, re-confirmed

I re-checked that the fixtures still reproduce the defect rather than
trusting last cycle's run. `parse_routes(LIVE_SHAPE)` yields a route named
`consul` (`cli/tests/fixtures/haproxy_cfg.py:35,46`), and
`consul_health.json` contains no element with `ServiceName == "consul"`. So
rung (b) keyed on `check.service` still cannot resolve it, and today's
`join()` signature is `(routes, jobs, checks, service_names)` with no
`catalog`. §9's reasoning holds unchanged: test 1 cannot run red against
`main` (a keyword-only `catalog=` raises `TypeError: unexpected keyword
argument` there), test 6 can, and §10 orders it that way.

## Most dangerous assumption

**R2's enforceability, again — and it now holds.** It was the one thing that
could still send an implementer to a signature where the wrong argument binds
silently and ships the bug green. The keyword-only form closes it, and I have
the mypy output rather than an argument. With that settled, the residual risk
in this plan is ordinary implementation risk, not a false premise.

## Contract hygiene

Clean. Non-goals explicit (§5, four of them, each with its measured reason).
Gates discovered, not assumed (§8 cites `.loop/config.json`, `justfile:18-19`
and the four hooks). Every named test homed in a file that exists: verified
`cli/tests/api/test_services.py`, `cli/tests/test_api_consul.py`,
`cli/tests/commands/test_read_commands.py`, `cli/tests/cluster/test_live.py`.
Both forks live in Open Questions with a recommendation. Anchors re-resolved
exact this cycle: `api/services.py:57`, `:72-76`, `:89`, `:110`, `:122`;
`commands/service.py:73-74`, `:91`, `:100`; `api/consul.py:25`, `:44-46`;
`tests/fixtures/scrub_capture.py:87` (the hardcoded
`("jobs_statuses", "nodes", "seal_status", "consul_health")` tuple);
`tests/api/test_services.py:34`; `tests/fixtures/haproxy_cfg.py:35,46`;
`.loop/plans/D3-cli-read-commands.md:445-451`;
`bootstrap/.../consul.hcl.j2:29-32`; `.pre-commit-config.yaml:37-72`.

## Required fixes

None.

## Notes (not blocking, for the implementer)

- R2 and §7 say the nine test call sites "pass `NAMES` positionally". Seven
  do; `:101` passes `renamed` and `:107` passes `{}`. All nine pass a names
  dict as the 4th positional argument and all nine are caught by mypy, so the
  substance is right and only the label is loose.
- §7's `services.py` bullet says the parameter is "REQUIRED" without
  repeating "keyword-only"; R2 carries the full shape. Worth aligning when
  the file is touched.
- R2 is enforceable across all ten call sites only because the mypy hook
  checks `cli/src cli/tests`, not `src` alone
  (`.pre-commit-config.yaml:60`). Stating that would make the requirement
  self-supporting.
- §9's third risk still names the wrong degradation: a tightened ACL yields a
  filtered 200, not a 403, and `CONSUL_FILTER_FOOTER`
  (`commands/render.py:26-31`) already renders on this table. Carried from
  cycle 1, not required then, not required now.
- §4 and P1's raw count of 25 catalog services is correct today but drifts
  (it read 24 yesterday). The load-bearing halves, `consul` in and `s3` out,
  do not drift.
