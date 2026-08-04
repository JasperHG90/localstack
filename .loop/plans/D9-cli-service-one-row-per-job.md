---
epic = "cli"
depends_on = ["D8-cli-service-tag-rung"]
priority = 30
summary = "`localstack service` renders a job's routes adjacently and blanks a cell only when it repeats the cell directly above, so `minio` and `s3` read as one service with two URLs. Rendering only: the join, the dataclass and the JSON are untouched."
---

# Ticket: D9-cli-service-one-row-per-job

## 1. Title

Group a job's routes visually in the `service` table, so two routes into one
job stop reading as two services.

## 2. Size / Effort

**S.** One sort and a per-cell repeat suppression in the renderer. No data
model change, which is the point: an earlier draft moved grouping into
`join()` and failed three plan reviews, each time by making a `JobSource`
member unreachable somewhere.

## 3. Triggered by

Operator, four times on the same row. `s3` renders `job = minio` and prints
`https://s3.lab.orangecluster.nl`, which is not how you reach MinIO;
`minio.lab.orangecluster.nl` is, and it sits on a different row. The two read
as separate services.

## 4. Context (measured live 2026-08-04)

### Two routes, one job

The running edge config routes `minio` to `192.168.2.29:9001` (the console,
`GET /` returns 200) and `s3` to `192.168.2.29:9000` (the S3 API, 403 to a
browser). Both are the `minio` Nomad job:
`deployments/infrastructure/services/minio.hcl:19-23` declares both ports and
`:48-52` the `s3` tag that rung (d) resolves on.

`minio` is the only job reached by more than one route. No absolute row count
is stated: the job list churns, and a new job appeared during the planning
review.

### The renderer prints rows in join order, one line each

`cli/src/localstack_cli/commands/service.py:71-76` renders
`["name", "url", "job", "source", "health", "backend"]` straight from the
list `join()` returns. `join()` emits routes first, sorted by route name
(`cli/src/localstack_cli/api/services.py:125`), then unrouted jobs (`:185`).
So `minio` and `s3` land several rows apart with nothing tying them together.

### The one trap in grouping by the rendered `job` field

`cli/src/localstack_cli/api/services.py:52` defines `AGENT_ENDPOINT` and
`:147` writes that same text into every rung-(b) row, so `vault`, `nomad` and
`consul` all carry the identical `job` value. Grouping naively on that field
collapses the three of them into one group. Verified live: it yields
`no job (agent endpoint): [consul, nomad, vault]`. The same applies to
`NOT_FOUND` (`:51`) on unresolved rows.

## 5. Non-goals / out of scope

- **No change to `join()`, `ServiceRow`, `find()` or `JobSource`.** The
  earlier data-model version of this ticket failed three plan reviews; the
  rendered table is where the complaint lives and where the fix belongs.
- **No change to `--json`.** It keeps emitting one object per row. Grouping
  is a reading aid, and a machine consumer already has `job` to group on.
- **No change to `--open`.** It takes a name and opens that row's URL, which
  is already the route the user asked for.
- **No URL probing and no per-URL label.** Whether an address serves anything
  is a separate ticket, and every rule for labelling one URL "primary" is a
  guess.
- No Terraform, no Ansible, no cluster change.

## 6. Requirements & restrictions

- **R1. Rows reaching the same job render adjacently**, in route-name order
  within the group.
- **R2. A `job`, `source` or `health` cell is blanked ONLY when its value is
  identical to the cell directly above it inside the same group.** The first
  row of a group prints all three, and a value that differs from the row
  above always prints. Stated per cell rather than per group on purpose: a
  "print once per group" rule blanks the `s3` row's `source` and deletes
  `consul-tag` from the table, and blanks its `health`, rendering a group
  whose Consul check is `passing` as `no check`. Measured on the fixtures,
  the `minio` group is `[minio, minio, job-id, no check]` then
  `[s3, minio, consul-tag, passing]`: only `job` repeats. The two health
  values differ because `cli/src/localstack_cli/api/services.py:137` computes
  the `job-id` row's health from the job's registered service names and
  `:168` computes the `consul-tag` row's from the matched service name.
- **R3. The group key is the rendered `job` string, taken ONLY from rows
  whose `job_source` is `job-id`, `consul-tag` or `no-route`.** Rows with
  `consul-name` carry the shared `AGENT_ENDPOINT` text
  (`cli/src/localstack_cli/api/services.py:52`) and `unresolved` the shared
  `NOT_FOUND` text (`:51`), so neither may group; without the exclusion
  `vault`, `nomad` and `consul` become one group. This is the ticket's one
  real trap. Noted precisely: a `consul-tag` row's `job` holds a Consul
  SERVICE name from `_sole_tag_carrier` (`:79-88`), not a Nomad job id, so
  `s3` groups with `minio` only because the Consul service happens to be
  named `minio`. That coincidence is already pinned live by
  `cli/tests/cluster/test_live.py:113-122`.
- **R4. `source` and `health` still show every distinct value in a group**,
  which follows from R2 rather than fighting it. So `consul-tag` stays
  visible on the `minio` group instead of being replaced by the first row's
  `job-id`, and a `passing` health is not hidden behind the row above's
  `no check`. Three plan reviews failed on variants that silently retired a
  rendered value; this is the guard, and
  `cli/tests/commands/test_read_commands.py:167-179` is the existing test
  that already catches the `source` half.
- **R5. Every route and every job still appears.** Grouping reorders and
  blanks repeated cells; it removes nothing.
- **R6. Ungrouped rows render exactly as today**, so a one-route job is
  unchanged on screen.
- **R7. Every change ships a test**
  (`.claude/rules/python-testing.md:6-10`); live-cluster tests carry the
  `cluster` marker (`:26-32`).
- **R8. Plain language in rendered strings**
  (`.claude/rules/plain-language.md`).

## 7. Code surface

- `cli/src/localstack_cli/commands/service.py:71-76`: the `table(...)` call.
  Sort the rows into groups and build each row's cells per R2, blanking a
  `job`, `source` or `health` cell only when it equals the cell directly
  above it within the same group.
- `cli/src/localstack_cli/commands/service.py`: add a pure helper
  `_grouped(rows) -> list[list[str]]` returning the table's row lists, so the
  ordering and blanking are testable without parsing rendered output. Tests 1
  to 5 and 7 call it.
- `cli/tests/commands/test_read_commands.py`: grouping, the agent-endpoint
  trap, both rungs visible on the `minio` group, and that no row is lost.
- `cli/tests/cluster/test_live.py`: live, `minio`'s two routes render
  adjacently.
- `docs/cli-read-commands.md`: a short paragraph saying a job's routes are
  grouped and a cell is blanked when it repeats the one above.

Read, do not edit:

- `cli/src/localstack_cli/api/services.py:51-52`: the two shared sentinel
  strings R3 excludes.
- `cli/src/localstack_cli/api/services.py:125`: the current row order.

## 8. Tests & validation gates

Repo gate: `just pre_commit` (`.loop/config.json` gates; `justfile:18-19`;
`.pre-commit-config.yaml:37-72` carries the four `cli/` hooks). Worktree
prerequisite: `just worktree_setup <path>` (`justfile:41-44`).

Offline: `uv run --project cli pytest`. Live: `-m cluster`.

Tests to add:

1. `_grouped()` puts `minio` and `s3` on consecutive rows, with the `job`
   cell printed on the first and blank on the second, and BOTH `source`
   values present (`job-id`, `consul-tag`) and both `health` values present.
   Red against today's code, which puts them several rows apart.
   (`cli/tests/commands/test_read_commands.py`)
2. **The trap.** `vault`, `nomad` and `consul` do NOT group: each keeps its
   own `job` and `health` cells, because they share the `AGENT_ENDPOINT` text
   rather than a real job. Red against an implementation that groups on the
   raw `job` string.
   (`cli/tests/commands/test_read_commands.py`)
3. Unresolved rows do not group with each other, for the same reason.
   (`cli/tests/commands/test_read_commands.py`)
4. Both rungs stay visible: the `minio` group's rendered output contains
   `job-id` AND `consul-tag`.
   (`cli/tests/commands/test_read_commands.py`)
5. No row is lost or duplicated: `len(_grouped(rows)) == len(rows)`, and the
   `name` cell is never blanked so every row stays identifiable. Counted off
   the built row list rather than rendered lines, because columns fold at
   `Console(width=120)` (`cli/src/localstack_cli/commands/render.py:59-72`)
   and live hostnames are longer than the fixtures'.
   (`cli/tests/commands/test_read_commands.py`)
6. `--json` is untouched, asserted structurally: the list handed to
   `emit_json` is the same object `join()` returned. The real guarantee is the
   early `return` at `cli/src/localstack_cli/commands/service.py:69`, which
   runs before the table is built at `:71`, so no grouping code executes on
   the JSON path.
   (`cli/tests/commands/test_read_commands.py`)
7. Live, `cluster`-marked: `_grouped()` over the live join puts `minio` and
   `s3` adjacent and does not group the agent endpoints. A join-level
   adjacency check, matching the shape of the tests already in that file,
   which has no `CliRunner` and no session fixture. SKIPS rather than fails
   when Consul is not advertising `minio`, which it briefly stopped doing
   during the planning review when a node left the catalog.
   (`cli/tests/cluster/test_live.py`)

Existing test that must stay green, and is the canary the last three cycles
lacked: `cli/tests/commands/test_read_commands.py:167-179` asserts
`consul-tag` appears in the RENDERED table. `s3` is the only tag-resolved row
in the fixtures, so any rule that blanks its `source` reds this test.

The scored acceptance rows live in
`.loop/evals/D9-cli-service-one-row-per-job.md`.

## 9. Risk assessment

- **Blast radius: one command's table layout.** No dataclass, no JSON, no
  API. `--json` is unchanged by construction and test 6 proves it.
- **Reversibility: high.** Revert one function.
- **Likeliest failure mode: grouping the agent endpoints.** They share the
  `AGENT_ENDPOINT` string, so a naive key merges `vault`, `nomad` and
  `consul` into one group and hides two services. R3 and test 2 exist for it,
  and it is reproducible live today.
- **Second: blanking a cell that was not actually repeated.** If the sort and
  the blanking use different keys, a row can lose its `job` cell to an
  unrelated neighbour. Use one key for both.
- **Third: losing a row.** Reordering is where rows go missing. Test 5
  counts.

## 10. Subtickets (ordered)

1. Write test 1 and watch it fail.
2. The group key (R3) and the sort, with test 2 as the guard.
3. Repeated-cell blanking, tests 3 to 5.
4. Test 6, pinning `--json` unchanged.
5. Live test 7.
6. Docs.
7. `just pre_commit`, then the review passes.

## 11. Open questions

- **Q1 — should the grouped rows carry a visual marker**, a brace or an
  indent, beyond the blanked cells?
  *Recommendation:* no. Blank cells under a filled one already read as
  continuation in every table people meet, and rich draws a row separator for
  free. Add one only if the output still reads as two services.

## Premises / assumptions

- **P1.** `minio` and `s3` are two edge routes into one Nomad job.
  `probe:` the running job's `local/haproxy.cfg` routes them to
  `192.168.2.29:9001` and `192.168.2.29:9000`; `GET /` over the edge returns
  200 and 403. `Evidence:`
  `deployments/infrastructure/services/minio.hcl:19-23` declares both ports,
  `:48-52` the `s3` tag. Probed live 2026-08-04.

- **P2.** `minio` is the only job reached by more than one route, so exactly
  one group forms.
  `probe:` grouping the live join by resolved job yields
  `minio: ['minio', 's3']` and no other job with more than one route. Probed
  live 2026-08-04.

- **P3.** Grouping on the rendered `job` field would collapse the three agent
  endpoints.
  `Evidence:` `cli/src/localstack_cli/api/services.py:52` defines
  `AGENT_ENDPOINT`; `:147` writes it into every rung-(b) row. `probe:`
  grouping the live join on that field yields
  `no job (agent endpoint): [consul, nomad, vault]`. Probed live 2026-08-04.

- **P4.** The renderer is the only thing this ticket touches, and it reads
  rows in join order.
  `Evidence:` `cli/src/localstack_cli/commands/service.py:71-76` builds the
  table directly from `join()`'s return;
  `cli/src/localstack_cli/api/services.py:125` sets that order.

- **P5.** `--json` cannot change, because it serializes the dataclass list
  and this ticket does not touch it.
  `Evidence:` `cli/src/localstack_cli/commands/render.py:53` is `emit_json`;
  `cli/src/localstack_cli/commands/service.py:67-69` hands it the unmodified
  rows and RETURNS, before the `table(...)` call at `:71`.

- **P6.** The repo gate is `just pre_commit`.
  `Evidence:` `.loop/config.json` names it in `gates`; `justfile:18-19`
  defines it; `.pre-commit-config.yaml:37-72` carries the `cli/` hooks.
