---
verdict: pass
plan: 928ee323ee93b8f535b79b6dcaf9201fa9dfb4483b20526d34581dd02b58c90e
---

# Plan validator: D8-cli-service-tag-rung (cycle 2)

## Deterministic floor

`loopctl verify-plan D8-cli-service-tag-rung` returns `valid`, exit 0.
`sha256sum` on the plan matches the briefing fingerprint exactly.
Baseline offline suite green before any change: `uv run --project cli pytest
cli/tests` gives 484 passed, 19 deselected.

## Premise verdict

**SOUND.**

Every cycle-1 required fix landed and is accurate against the code. I
re-took the live measurement rather than trusting the previous pass, and it
reproduces §4 row for row. The two defects that made cycle 1 a
`pass-with-required-fixes` (the unaccounted module docstring, the silently
vacuous command test) are now named in §7 with the right anchors and the
right consequence.

## Cycle-1 fixes, verified

### Fix 1. The module docstring. LANDED, anchor exact.

`cli/src/localstack_cli/api/services.py:8-21` is the ladder documentation;
`:16` reads "`s3` is the live example, and rendering it that way is correct
output rather than a bug." §7's first bullet cites `:8-21` and requires both
halves change. Correct.

### Fix 2. The lost live example. LANDED.

Same §7 entry states it outright: after this change no live route is
unresolved. Re-measured live below, and it is true. The docs anchors resolve:
`docs/cli-read-commands.md:43` is the `unresolved` table row naming `s3`, and
`:55-59` is the backend paragraph that uses `s3` as its worked case. §7's docs
bullet covers both, and the docstring bullet's instruction ("describe the
state rather than naming a case that no longer occurs") carries over.

### Fix 3. The vacuous command test. LANDED, and I confirmed it would go vacuous.

`cli/tests/commands/test_read_commands.py:587-604` is
`test_the_table_says_where_an_unresolved_row_points`, asserting only
`"backend" in stdout` and `"10.0.0.29:9000" in stdout`. I resolved the
fixture ladder by running the real parser and the real fixtures rather than
reading them:

    bifrost job-id   consul consul-name  grafana job-id  memex job-id
    minio   job-id   mlflow job-id       nomad   consul-name
    phoenix job-id   s3     unresolved   vault   consul-name

`s3` is the fixture's only unresolved row, and its tag carriers are exactly
`['minio']` (`cli/tests/fixtures/capture/consul_catalog.json`, `minio ->
["s3","http"]`). So after the change the row resolves `consul-tag`, both
assertions still pass (`commands/service.py:73-74` renders the backend
column on every row, and the backend string is unchanged), and the test
covers no unresolved row. §7 now says exactly this and prescribes the remedy.
The remedy is sufficient: a route matching no job id, no catalog key and no
tag falls to the `else:` at `services.py:134` regardless of the new rung.

### Fix 4. The broken cite. LANDED.

`.loop/plans/D7-cli-service-join-consul-catalog.md` exists, and `:266` is
"Q2 — should `s3` resolve to `minio` via the Consul tag?". No D7 directory
under `.loop/archive/`, so the parenthetical about it being merged but not
archived is accurate.

### Fix 5. The silent fork. LANDED as R4a and Q1.

R4a (plan `:87-93`) states both halves of the rule, and §11's Q1 carries it
as an open question with a recommendation rather than claiming nothing is
open. Judgment on the call itself is below.

### Fix 6. Test 5 points at the existing test. LANDED, anchor exact.

`cli/tests/cluster/test_live.py:114-123` is
`test_the_minio_service_still_carries_the_s3_tag`, and `:123` is the
uniqueness assertion `[name for name, tags in catalog.items() if "s3" in
tags] == ["minio"]`. The cite is line-exact and §8's test 5 says extend, not
duplicate.

## Per assumption

### P1. `minio` carries `s3` and is its only carrier. HOLDS.

Re-probed live today, tokenless `GET
https://consul.lab.orangecluster.nl/v1/catalog/services`: 25 services,
`s3` carriers `['minio']`. Declared, not inferred:
`deployments/infrastructure/services/minio.hcl:48-52`.

### P2. No live route name is carried as a tag by more than one service. HOLDS.

Re-measured for all ten route names against the live catalog. Identical to
§4: every list empty except `s3 -> ['minio']` and `memex -> ['memex']`, both
unique. `memex` resolves at rung (a), so one row changes.

### P3. The rung cannot change a row that resolves today. HOLDS.

`services.py:122` is `elif route.name in consul_services:`, `:134` is the
`else:`. An `elif` between them runs only after both miss. The `:110` cite
for the job-id branch is still one line loose (the branch head is `:108`,
`if job is not None:`), which is the same nit as cycle 1 and does not affect
the claim.

### P4. Tags are already fetched. HOLDS.

`cli/src/localstack_cli/api/consul.py:74` returns `dict[str, list[str]]`;
`services.py:101` is `consul_services = set(catalog)`, keys only.

### P5. 9000 is the S3 API, 9001 the console. HOLDS.

`minio.hcl` declares both ports and registers `minio` on `http_api` with
`["http","s3"]`. The command fixture agrees: route `minio` backs onto
`10.0.0.29:9001`, route `s3` onto `10.0.0.29:9000`.

### P6. The repo gate is `just pre_commit`. HOLDS.

`.loop/config.json` gates, `justfile:18-19`, `.pre-commit-config.yaml:37-72`.

### P7 (cycle 1). D7's shipped tests. NOW COVERED.

Both the api-level staleness and the command-level vacuity are in §7 with
the consequence spelled out. The unit fixture at
`cli/tests/api/test_services.py:39` still carries no `s3` tag, so those tests
stay green as before.

### P8 (cycle 1). `unresolved` loses its only live example. NOW STATED.

### P9 (cycle 1). The `job` column and `routed_jobs` rule. NOW SPECIFIED (R4a, Q1).

## The judgment you asked for: is R4a right?

**The `routed_jobs` half is right and the reasoning is sound.** Not adding
the matched service to `routed_jobs` is verifiably harmless today (`minio` is
already routed by the `minio` route at rung (a), so no duplicate `no-route`
row appears either way, confirmed against `services.py:146-148`), and the
stated reason for the rule is the correct one: a tag may be the only pointer
at a job, and suppressing that job's own row would lose it.

**The `job`-column half is defensible but is not the choice I would make.**
The module already has a vocabulary for "the thing that matched is not a
job": rung (b) writes `AGENT_ENDPOINT` (`services.py:127`) precisely so the
column never asserts a job that does not exist. R4a breaks that pattern: when
the matched Consul service is not a Nomad job (`minio-console`,
`postgres-db`, `nats-monitor` and six others are live catalog services with
no same-named job), a column headed `job` would carry a name that is not one.

I am not requiring a change, for three reasons, all checked:

1. It has no live instance. The only tag match today is `minio`, which IS a
   Nomad job id (present in `jobs_statuses`), so the column is truthful on
   every row that will actually render.
2. The row disambiguates itself. `commands/service.py:73` renders `source`
   next to `job`, so the row reads `job=minio, source=consul-tag`: the reader
   is told the match came from a tag, not from a job id.
3. It is surfaced, not decided in the dark. §11's Q1 carries it with a
   recommendation, which is what the create-ticket contract asks of a fork.

Worth the implementer's attention at review time, not worth another planning
cycle.

## Most dangerous assumption

**P2**, that no live route name has two tag carriers. It carries §4, the
"exactly one row changes" claim and the whole case for reopening D7's Q2. I
re-measured it live today and it holds exactly as written.

## Contract hygiene

Anchors resolve (`services.py:8-21`, `:31-38`, `:122-144`;
`test_read_commands.py:587-604`; `test_live.py:114-123`;
`docs/cli-read-commands.md:43` and `:55-59`; the D7 plan and its Q2). Gates
are discovered, not assumed. Non-goals are explicit. All five tests are homed
in §7. The one fork left is in §11 with a recommendation.

## Note, not a required fix

Fix 3's remedy says to give the test "a route that stays unresolved (a
hostname in the edge fixture...)". If the implementer reads "the edge
fixture" as the shared `LIVE_SHAPE` constant
(`cli/tests/fixtures/haproxy_cfg.py:18`), an eleventh route turns
`cli/tests/api/test_haproxy.py:14-29` red: it asserts `len(routes) == 10` and
an exact name set, and the fixture docstring at `haproxy_cfg.py:3-4` says
"ten routes". Neither file is in §7. I am not requiring it because the
failure is loud and immediate under `just pre_commit`, unlike the silent
coverage loss it fixes, and because the cheaper move is available: the edge
mock is built inline at `test_read_commands.py:79-97`, so the test can pass
`LIVE_SHAPE` plus one extra backend block without touching the shared
constant. Either path is fine; the second leaves less mess.
