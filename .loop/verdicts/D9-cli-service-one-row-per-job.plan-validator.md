---
verdict: fail
---

# Plan review: D9-cli-service-one-row-per-job (pass `plan-validator`)

## Deterministic floor

`loopctl verify-plan D9-cli-service-one-row-per-job` returns
`valid: warn: 7/8 Context/Requirements claims carry no path:line anchor`,
exit 0. No hard fail, so the deep pass ran.

## Premise verdict

**PARTIALLY SOUND.** The approach is right: the change really is render-only
and the renderer really can deliver the grouping from `ServiceRow` alone. But
R2 as written contradicts R4, and §7 (the section an implementer follows)
states the losing side of that contradiction. Implemented to the letter, this
plan hides `consul-tag` on the `s3` row and hides a `passing` health check.
That is the same defect for the fourth time, in a new place, exactly as
suspected.

## Per assumption

**P1. `minio` and `s3` are two routes into one job. HOLDS.**
`deployments/infrastructure/services/minio.hcl:19-23` declares `http_api`
static 9000 and `http_console` static 9001; `:48-52` is the `service` block
named `minio` on `port = "http_api"` with `tags = ["http", "s3"]`. The live
HTTP probe I could not repeat (no cluster credentials in this worktree), but
the repo side of the claim resolves exactly as stated.

**P2. `minio` is the only job reached by more than one route. HOLDS offline;
live probe UNVERIFIED here.** I reproduced the join against the offline
fixtures (`cli/tests/fixtures/haproxy_cfg.py:31-40`,
`cli/tests/fixtures/capture/consul_catalog.json`): `minio` is the only `job`
value carried by two rows (`minio` at `job-id`, `s3` at `consul-tag`). Every
other route resolves to a distinct job. The existing test
`cli/tests/commands/test_read_commands.py:654` already pins that count at 2.

**P3. Grouping on the rendered `job` field collapses the agent endpoints.
HOLDS.** `cli/src/localstack_cli/api/services.py:52` defines
`AGENT_ENDPOINT = "no job (agent endpoint)"`; `:147` writes it into every
`CONSUL_NAME` row. My render of the fixture join shows `consul`, `nomad` and
`vault` all carrying that identical string, so a naive key merges three
services into one. R3 is the right guard and it is aimed at the right thing.

**P4. Render-only, reading rows in join order. HOLDS.**
`cli/src/localstack_cli/commands/service.py:71-76` builds the table straight
from the list `join()` returns; `cli/src/localstack_cli/api/services.py:125`
sorts routes by name and `:185` appends unrouted jobs after them. Everything
R1 to R6 needs (`name`, `job`, `job_source`, `health`) is already on
`ServiceRow` (`services.py:55-65`), so the requirements are reachable without
touching `join()`, `ServiceRow`, `find()` or `JobSource`. The plan's anchor
`70-78` is loose by a line or two but points at the right call.

**P5. `--json` cannot change. HOLDS.**
`cli/src/localstack_cli/commands/service.py:67-69` is `if as_json:` /
`emit_json(rows)` / `return`, and the `return` precedes the `table(...)` call
at `:71`. So a change confined to the table branch cannot reach the JSON
branch. `find()` and `--open` run at `:56-65`, also before both. One anchor
is wrong: P5 cites `commands/render.py:40` as "the serializer", but `:40` is
`def _plain`; `def emit_json` is `commands/render.py:53`.

**P6. The repo gate is `just pre_commit`. HOLDS.** `.loop/config.json`
`gates` is `["just pre_commit"]`; `justfile:18-19` defines it;
`.pre-commit-config.yaml:37,46,52,66` are the four `cli/` hooks (ruff,
ruff-format, mypy, pytest) inside the cited `37-72` window, and the file is
73 lines. `justfile:44` is `worktree_setup path:`.

**P7 (implicit, and the one that breaks). "R2 and R4 are jointly satisfiable
as written." BREAKS.** See below.

**P8 (implicit). "A `consul-tag` row's `job` cell holds a real job id."
UNCERTAIN.** `services.py:154` binds `tagged` from `_sole_tag_carrier`
(`:79-88`), which returns a **Consul service name** read off the catalog
keys, not a Nomad job id. Here the two coincide (the Consul service is also
named `minio`), which is why `test_read_commands.py:650` passes. But R3's
wording ("carries a real job id") is not what the code carries, and the
catalog also holds `minio-console`; had the `s3` tag been declared on the
console service, the key would be `minio-console` and no group would form.
This does not hide a service, it only fails to group, so it is a wording
defect rather than a trap. Say what the key actually is.

**P9 (implicit). "The live test can render the table." BREAKS.**
`cli/tests/cluster/test_live.py` has no `CliRunner` and no session fixture:
every test there calls the API layer directly and skips on a missing
`NOMAD_TOKEN` (`:25-34`, `:145-160`). Test 7 asks for rendered adjacency, but
§7 places the whole change inline in the `service()` function body, so there
is no importable target and no harness to invoke the command live.

**P10 (implicit). "Rows render one line each, so counting lines counts
rows." UNCERTAIN.** True today offline: I rendered the fixture join through
the real `table()` and got 23 rows in 23 body lines. It is not a property of
the renderer. Columns are built with `overflow="fold"` at a fixed
`Console(width=120)` (`commands/render.py:59-72`), and live hostnames
(`*.lab.orangecluster.nl`) are about 17 characters longer than the fixture's
`*.lab.example`, which pushes the six columns past 120 and folds. Test 5 must
count rows, not stdout lines.

## Most dangerous assumption

**P7: that R2 and R4 can both be met as written.** They cannot, and §7 picks
the wrong one.

R2 sentence 1: "The `job`, `source` and `health` cells print once per group,
on its first row."
R4: "`source` still shows every rung ... so `consul-tag` stays visible on the
`minio` group."

I rendered the actual join over the offline fixtures. The `minio` group is:

    name   | job   | source     | health
    minio  | minio | job-id     | no check
    s3     | minio | consul-tag | passing

Sorted by route name inside the group (R1), `minio` is first. R2 sentence 1
therefore blanks the `s3` row's `source`, deleting `consul-tag` from the
table, which is precisely what R4 forbids. It also blanks the `s3` row's
`health`, so a group with a live passing Consul check renders as `no check`,
and nothing in the plan guards that at all: R4 protects `source` only. The
two health values differ because `services.py:137` computes the `job-id` row's
health from the job's own registered service names while `:168` computes the
`consul-tag` row's from the matched service name.

This is not hypothetical. `cli/tests/commands/test_read_commands.py:179`
asserts `"consul-tag" in result.stdout` against the **table**, and `s3` is the
only tag-resolved row in the fixture (of the ten route names, only `s3` has a
tag carrier in `consul_catalog.json`). R2-as-written turns that existing test
red, and §7 of the plan does not list it.

The plan does contain the correct rule, twice, in weaker positions: R2
sentence 2 ("a repeated identical value across adjacent rows") and §9's second
risk ("blanking a cell that was not actually repeated"). But §2 says "one
repeated-cell suppression", and §7, the code surface, says "blanked after the
first row of each group". An implementer follows §7.

## Required fixes

1. **Rewrite R2 as a per-cell rule and make §7 agree.** State it as: a `job`,
   `source` or `health` cell is blanked only when its value is identical to
   the cell directly above it inside the same group; the first row of a group
   prints all three; a value that differs from the row above always prints.
   Then R4 is a consequence rather than a contradiction. Delete "print once
   per group, on its first row" and "blanked after the first row of each
   group" (§7). Evidence: measured `minio` group above;
   `cli/src/localstack_cli/api/services.py:137` vs `:168`.
2. **Extend the R4 guard to `health`.** R4 names only `source`. The measured
   fixture blanks a `passing` health under R2-as-written. Either fold it into
   the R2 rewrite or say explicitly that a differing `health` stays on screen.
3. **Add the existing canary to §7 and §8.**
   `cli/tests/commands/test_read_commands.py:167-179` asserts `consul-tag`
   appears in the rendered table and must stay green. It is the test the last
   three cycles lacked. Name it.
4. **Restate R3's key in the code's own terms.** A `CONSUL_TAG` row's `job`
   holds a Consul service name from `services.py:79-88`, not a Nomad job id.
   Define the key as "the rendered `job` string, taken only from rows whose
   `job_source` is `job-id`, `consul-tag` or `no-route`", and note that the
   grouping of `s3` with `minio` depends on the Consul service being named
   `minio` (already pinned live by `cli/tests/cluster/test_live.py:113-122`).
5. **Make test 6 testable.** "`--json` is identical before and after" cannot
   be asserted inside one run; as written an implementer compares the output
   to itself and proves nothing. Replace it with either a committed baseline
   compared against, or a structural assertion that the list handed to
   `emit_json` is the unmodified `join()` return. The real proof is the early
   `return` at `commands/service.py:69`, which the plan should cite in test 6.
6. **Give test 7 a target, or drop it.** `cli/tests/cluster/test_live.py` has
   no `CliRunner` and no session fixture. Either name an importable pure
   helper in `commands/service.py` (for example `_grouped(rows)` returning the
   table's row lists) that tests 1 to 5 and 7 can call, or restate test 7 as a
   join-level adjacency check on live data, matching the file's existing
   shape.
7. **Fix test 5 to count rows, not lines.** Columns fold at
   `Console(width=120)` (`commands/render.py:59-72`); the fixture does not
   fold today but live hostnames are ~17 characters longer and will. Count
   body rows (for example lines with a non-empty `name` cell, which is never
   blanked) or compare the built row list.
8. **Fix two anchors.** P5 cites `commands/render.py:40` for the serializer;
   `emit_json` is at `:53` (`:40` is `_plain`). §4 and §7 cite
   `commands/service.py:70-78`; the `table(...)` call is `:71-76`.
9. **Minor.** §8 points at `.loop/evals/D9-cli-service-one-row-per-job.md`,
   which does not exist yet (D7 and D8 have theirs). Not a blocker if the
   eval pass writes it, but nothing else currently catches defect 1.

## What is genuinely settled

- Render-only is achievable: `ServiceRow` carries every field R1 to R6 need,
  and `join()`, `find()`, `JobSource` and `--json` can all stay untouched.
- `--json` cannot change: `commands/service.py:67-69` returns before the
  table is built.
- R3's exclusion targets the right two sentinels (`AGENT_ENDPOINT`
  `services.py:52`, `NOT_FOUND` `:51`) and prevents the three-agent-endpoint
  merge.
- No existing test asserts row ORDER. `cli/tests/api/test_services.py` keys
  everything by name, and the command tests are substring or dict lookups
  (`test_read_commands.py:605`, `:627`, `:648`). Reordering breaks nothing.
- §9's blast-radius and reversibility claims are accurate.

The premise is close to sound and the approach is the right one. Fix R2 and
§7 so they state the same rule, and this is ready.
