---
epic = "cli"
depends_on = ["D7-cli-service-join-consul-catalog"]
priority = 30
summary = "`localstack service` resolves a route to a Consul service that carries a tag of the same name, when exactly one service carries it. `s3` stops rendering as unresolved and resolves to `minio`."
---

# Ticket: D8-cli-service-tag-rung

## 1. Title

Add the unique-tag rung to `localstack service`, so `s3` resolves to `minio`
instead of rendering unresolved.

## 2. Size / Effort

**S.** One rung, one branch, one `JobSource` member. The measurement that
makes it safe is already taken (see §4) and the fetcher already returns tags.

## 3. Triggered by

Operator, twice. `s3` is MinIO and rendering it as `not found` is wrong.
D7 deferred this in its Q2 citing tag non-uniqueness; §4 shows that objection
does not apply to any route on this cluster.

## 4. Context (verified live 2026-08-04)

### The data is already fetched

`cli/src/localstack_cli/api/consul.py:74` returns
`dict[str, list[str]]`, name to tags, and D7 kept the tags rather than
discarding them for exactly this. `cli/src/localstack_cli/api/services.py:101`
consumes only the keys.

### The ambiguity D7 worried about does not occur

D7's Q2 deferred a tag rung because `http` is carried by 16 services and
`monitoring` by 9. Neither is a route name. Measured across the ten live
routes, asking which catalog services carry a tag equal to the route name:

    minio -> []          s3      -> ['minio']    vault   -> []
    nomad -> []          consul  -> []           phoenix -> []
    memex -> ['memex']   grafana -> []           mlflow  -> []
    bifrost -> []

Two routes have carriers and both are unique. `memex` already resolves at
rung (a) by job id, so the tag rung never sees it. Exactly one row changes:
`s3`.

### Why the tag is trustworthy

It is declared by the job, not inferred. `minio` registers the service
`minio` with tags `["s3", "http"]` on the port label the `s3` route's backend
points at (`192.168.2.29:9000`, MinIO's S3 API; `:9001` is the console and is
the `minio` route). Reading it is reading what the job said about itself.

### Where it slots in

`cli/src/localstack_cli/api/services.py:122` is rung (b) (catalog name) and
`:134` is the unresolved fallback. The tag rung goes between them: it runs
only after a job-id and a catalog-name match have both failed, so it cannot
change any row that resolves today.

## 5. Non-goals / out of scope

- **No resolution on an ambiguous tag.** Two or more carriers means the row
  stays `unresolved`. Picking one would be the guess this ticket exists to
  avoid.
- **No alias map, no address matching, no config.** The tag is the only
  source.
- **No change to rungs (a) or (b)**, to the health column, or to any other
  command.
- No Terraform, no Ansible, no job change. The `s3` tag already exists.

## 6. Requirements & restrictions

- **R1. A fourth rung, `consul-tag`, between the catalog-name rung and the
  unresolved fallback.** It resolves only when exactly one catalog service
  carries a tag equal to the route name.
- **R2. Ambiguity resolves nothing.** Zero carriers or two-plus carriers
  leaves the row `unresolved` with its backend, exactly as today.
- **R3. The row says which rung answered.** A new `JobSource.CONSUL_TAG`
  member with value `consul-tag`, so the source column stays honest about
  how the match was made. It is not `consul-name`: the name did not match.
- **R4. Health follows the matched service**, not the route name, since the
  route name is a tag rather than a service.
- **R4a. The `job` column shows the matched SERVICE name, and the rung does
  not mark any job as routed.** A tag match identifies a Consul service, not
  necessarily a Nomad job, so the column reports what actually matched.
  Leaving `routed_jobs` alone matters: `minio` is already routed by the
  `minio` route at rung (a), and adding it again here would be a no-op
  today but would suppress a job's own `no-route` row in the case where a
  tag is the ONLY thing pointing at it. That job should still appear.
- **R5. Every change ships a test**
  (`.claude/rules/python-testing.md:6-10`), including one that a
  two-carrier tag does NOT resolve.
- **R6. Live-cluster tests carry the `cluster` marker**
  (`.claude/rules/python-testing.md:26-32`).
- **R7. The `api/` layer keeps its contract**: dataclasses out, no `typer`,
  no `rich`, no literal address (`cli/tests/test_read_guardrails.py:47-77`).
- **R8. Plain language in rendered strings**
  (`.claude/rules/plain-language.md`).

## 7. Code surface

- `cli/src/localstack_cli/api/services.py:8-21`: the module docstring
  documents a three-rung ladder and names `s3` as the live `unresolved`
  example. It gains the fourth rung, and `unresolved` loses that example:
  after this change no live route is unresolved. Describe the state rather
  than naming a case that no longer occurs.
- `cli/src/localstack_cli/api/services.py:31-38`: add `CONSUL_TAG` to
  `JobSource`.
- `cli/src/localstack_cli/api/services.py:122-144`: add the tag rung between
  the catalog-name branch and the unresolved fallback.
- `cli/tests/api/test_services.py`: the unique-tag match resolves; a
  two-carrier tag does not; a zero-carrier tag does not; the rung runs only
  after (a) and (b) fail.
- `cli/tests/commands/test_read_commands.py`: `s3` renders `consul-tag` with
  job `minio` against the fixtures. **And
  `test_the_table_says_where_an_unresolved_row_points` goes vacuous**: `s3`
  is the fixture's only unresolved row, so after this change that test still
  passes while exercising no unresolved row at all. Give it a route that
  stays unresolved (a hostname in the edge fixture matching no job, no
  catalog name and no tag) so it keeps testing what it claims.
- `cli/tests/cluster/test_live.py`: live, `s3` resolves to `minio`, and no
  route name is carried as a tag by more than one service.
- `docs/cli-read-commands.md`: the `job_source` table gains the `consul-tag`
  row; the `unresolved` row and the backend paragraph stop using `s3` as
  their example.

Read, do not edit:

- `.loop/plans/D7-cli-service-join-consul-catalog.md` Q2: the deferral this
  ticket closes, with its evidence. (D7 is merged but not yet archived.)

## 8. Tests & validation gates

Repo gate: `just pre_commit` (`.loop/config.json` gates, `justfile:18-19`),
running ruff, ruff-format, mypy strict and pytest scoped to `^cli/`
(`.pre-commit-config.yaml:37-72`). Worktree prerequisite: `just
worktree_setup <path>` (`justfile:41-44`).

Offline: `uv run --project cli pytest`. Live: `-m cluster`.

Tests to add, each homed in §7:

1. A route whose name is carried as a tag by exactly one catalog service
   resolves `consul-tag`, with job and health from that service.
   (`cli/tests/api/test_services.py`)
2. A route whose name is carried by two services stays `unresolved`.
   (`cli/tests/api/test_services.py`)
3. The tag rung never pre-empts rung (a) or rung (b): a route matching a job
   id AND carried as a tag elsewhere still resolves `job-id`.
   (`cli/tests/api/test_services.py`)
4. `s3` renders `consul-tag` with job `minio` through the command.
   (`cli/tests/commands/test_read_commands.py`)
5. Live, `cluster`-marked: `s3` resolves to `minio`. The uniqueness half is
   already asserted by `cli/tests/cluster/test_live.py:114-123`, which D7
   added to pin this ticket's premise, so extend rather than duplicate it.
   (`cli/tests/cluster/test_live.py`)

The scored acceptance rows live in `.loop/evals/D8-cli-service-tag-rung.md`.

## 9. Risk assessment

- **Blast radius: one row today.** The rung runs only where (a) and (b) both
  failed, so no resolving row can change. Measured: `s3` is the only
  unresolved route with a tag carrier.
- **Reversibility: high.** Delete the branch and the enum member.
- **Likeliest failure mode: resolving on an ambiguous tag.** If the
  "exactly one" check is written as "at least one", a future tag shared by
  two services silently picks whichever sorts first. Test 2 exists for that
  and must be seen red against a `>= 1` implementation.
- **Second: the rung placed too early.** Above rung (b) it would beat a real
  name match. Test 3 pins the order.
- **Third: the tag disappears upstream.** If MinIO stops declaring `s3`, the
  row returns to `unresolved`, which is the honest answer. Test 5 says so
  out loud rather than leaving it a mystery.

## 10. Subtickets (ordered)

1. Add `CONSUL_TAG` and the rung, with tests 1 to 3. Watch test 1 fail first.
2. Test 4 through the command.
3. Test 5, live.
4. Docs.
5. `just pre_commit`, then the review passes.

## 11. Open questions

D7 left one fork (resolve on a unique tag, or not at all) and the operator
settled it: resolve. R2's ambiguity rule is the conservative branch of that
same decision, with no live instance, so it needs no separate call.

- **Q1 — what does the `job` column show for a tag match, and is the matched
  job then "routed"?** A tag identifies a Consul service, which may or may
  not be a Nomad job, so this is a real second choice rather than a
  restatement.
  *Recommendation:* R4a. Show the matched service name, and do not add it to
  `routed_jobs`. Today `minio` is already routed by its own route so nothing
  changes either way; the rule matters for the case where a tag is the only
  pointer at a job, where suppressing that job's own row would lose it.

## Premises / assumptions

- **P1.** `minio` carries the Consul tag `s3`, and it is the only service
  that carries it.
  `probe:` `GET /v1/catalog/services` returns `minio -> ["s3", "http"]`;
  filtering all 25 services for the tag `s3` yields `["minio"]`. Probed live
  2026-08-04.

- **P2.** No live route name is carried as a tag by more than one service,
  so the rung is unambiguous for every route today.
  `probe:` for each of the ten route names, the list of catalog services
  carrying that tag is empty except `s3 -> ["minio"]` and
  `memex -> ["memex"]`. Probed live 2026-08-04.

- **P3.** The tag rung cannot change a row that resolves today, because it
  runs after both existing rungs.
  `Evidence:` `cli/src/localstack_cli/api/services.py:110` is the job-id
  branch, `:122` the catalog-name branch, `:134` the fallback the new rung
  precedes.

- **P4.** The tags are already fetched, so no new request is added.
  `Evidence:` `cli/src/localstack_cli/api/consul.py:74` returns name to
  tags; `cli/src/localstack_cli/api/services.py:101` currently uses only the
  keys.

- **P5.** `9000` is MinIO's S3 API and `9001` its console, so the `s3` route
  and the `minio` route are two ports of one job.
  `Evidence:` the running edge config routes `s3` to `192.168.2.29:9000` and
  `minio` to `192.168.2.29:9001`; `deployments/infrastructure/services/minio.hcl`
  declares both.

- **P6.** The repo gate is `just pre_commit`, which runs
  `pre-commit run --all-files`.
  `Evidence:` `.loop/config.json` names it in `gates`; `justfile:18-19`
  defines the recipe; `.pre-commit-config.yaml:37-72` carries the four
  `cli/` hooks it runs.
