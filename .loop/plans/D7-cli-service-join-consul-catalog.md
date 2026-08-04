---
epic = "cli"
depends_on = ["D3-cli-read-commands"]
priority = 30
summary = "`localstack service` resolves its Consul rung from the catalog rather than from health checks, so `consul` stops rendering as unresolved, and the table renders the backend column requirement 5 already mandates, so an unresolved row says where it points."
---

# Ticket: D7-cli-service-join-consul-catalog

## 1. Title

Fix `localstack service`'s Consul rung to read the catalog, and render the
`backend` column the row already carries.

## 2. Size / Effort

**S.** Two defects, one new fetcher, one column. The committed fixtures
already reproduce defect 1: `cli/tests/fixtures/haproxy_cfg.py:35,46` carries
a `consul` route and `consul_health.json` carries no `consul` check, so §8
test 6 goes red against `main` today. The new capture is what lets the join
be tested directly rather than only through the command.

## 3. Triggered by

Operator ran `localstack service` against the live cluster on 2026-08-04 and
asked why `consul` and `s3` render `unresolved`. `consul` is a defect. `s3`
is correct for this ticket's ladder, but the reason first given (that nothing
could resolve it) was wrong: a Consul tag does. See §4 and Q2.

## 4. Context (verified live 2026-08-04)

### Defect 1: the Consul rung reads the wrong endpoint

`cli/src/localstack_cli/api/services.py:89` builds the rung-(b) name set from
health checks:

    consul_services = {check.service for check in checks if check.service}

`cli/src/localstack_cli/api/consul.py:44-58` fetches those from
`GET /v1/health/state/any`, whose elements carry `ServiceName`.

Consul does not register a service-scoped check for itself. Live counts of
`ServiceName` across the 41 checks: `nomad` 3, `vault` 1, and **five entries
with `ServiceName: ""`**, which are node-level `serfHealth` checks. So
`consul` is absent from the set and falls to rung (c) at
`cli/src/localstack_cli/api/services.py:122`.

The catalog does list it. `GET /v1/catalog/services` returns 25 names
including `consul`, `nomad` and `vault`. `vault` and `nomad` resolve today
only because they happen to own service-scoped checks; `consul` does not, and
the rung was never about checks.

### Defect 2: the table drops the backend

`.loop/archive/D3-cli-read-commands/plan.md:449` requires an unresolved row to
"render the hostname and the raw `ip:port` backend".
`cli/src/localstack_cli/api/services.py:57` carries `backend` on the
dataclass and `--json` emits it, but
`cli/src/localstack_cli/commands/service.py:73-74` renders five columns and
`backend` is not among them. The two rows with the least resolved information
therefore show the least on screen.

### `s3` stays unresolved in THIS ticket, and the reason is narrower than it looks

Live edge backends: `minio -> 192.168.2.29:9001`, `s3 -> 192.168.2.29:9000`.
Same host, MinIO's console and S3 API ports. No Nomad job and no catalog
service is named `s3`, so no NAME rung can match it.

An address rung cannot pick it either, but not because the addresses differ.
`GET /v1/catalog/service/minio` returns `ServiceAddress 10.88.0.2` with node
`Address 192.168.2.29`, which DOES match the edge backend host. Two other
things defeat it: `ServicePort` is `0`, so there is nothing to match the port
against, and `minio-console` returns the identical node address and port, so
host-only matching is ambiguous between two candidates for both routes.

**A tag rung would work, and it is deferred rather than impossible.** The
request this ticket adds already carries the answer:
`GET /v1/catalog/services` returns `minio -> ["http", "s3"]`. That tag is
declared by the minio job's own service block on port label `http_api`
(9000), which is exactly the `s3` route's backend port. So resolving `s3` to
`minio` is reading declared data, not guessing.

It is deferred because tags are not unique: `http` covers three services
here, so a tag rung needs a disambiguation rule this ticket has not designed.
Foreclosing it would be wrong, so R1 keeps the tags rather than discarding
them. See Q2.

## 5. Non-goals / out of scope

- **No address rung.** Measured in §4: `ServicePort` is `0` and two services
  share a node address, so it cannot pick one.
- **No tag rung in this ticket, deferred not refused.** `minio` carries the
  tag `s3`, so the data exists. What does not exist yet is a disambiguation
  rule for a tag several services share, and designing one is its own
  ticket. R1 keeps the tags so that ticket has them.
- **No change to `s3`'s verdict here.** It stays `unresolved` until the tag
  rung lands.
- **No new Consul token.** The catalog read is tokenless like the health
  read (`cli/src/localstack_cli/api/consul.py:1-18`).
- **No change to the other three commands**, to `api/haproxy.py`, or to the
  health rules.
- No Terraform, no Ansible, no policy change.

## 6. Requirements & restrictions

- **R1. Rung (b) resolves from the catalog.** Add `list_services()` over
  `GET /v1/catalog/services` to `cli/src/localstack_cli/api/consul.py`,
  returning `dict[str, list[str]]` (service name to its tags), and key rung
  (b) on its keys. Health checks stay the source for the health COLUMN; they
  were never the source for existence. The tags are kept rather than
  discarded so the deferred tag rung (Q2) stays open instead of being
  foreclosed by a return type.
- **R2. `catalog` is a REQUIRED KEYWORD-ONLY parameter of `join()`**, declared
  after a bare `*`. Required, because any default is either empty (silently
  resolving nothing at rung (b)) or check-derived (this ticket's defect,
  preserved as a fallback). Keyword-only, because merely required is not
  enforceable: `catalog: dict[str, list[str]]` and the existing
  `service_names: dict[str, list[str]] | None` at
  `cli/src/localstack_cli/api/services.py:76` are positionally
  interchangeable, so a positional `catalog` would let today's call sites
  bind their names dict to it and type-check clean, shipping the bug green
  AND degrading every `job-id` row's health to `no check`. Keyword-only
  makes mypy strict reject exactly that. There are ten call sites, not one:
  `cli/src/localstack_cli/commands/service.py:100` and nine in
  `cli/tests/api/test_services.py` that pass `NAMES` positionally, all of
  which must be updated.
- **R3. The table renders `backend`**, satisfying
  `.loop/archive/D3-cli-read-commands/plan.md:449`. An unresolved row shows its
  `ip:port`; a resolved row may show it too.
- **R4. The `api/` layer keeps its contract**: dataclasses out, no `typer`,
  no `rich`, no literal address or port
  (`cli/tests/test_read_guardrails.py:55-77`).
- **R5. Every change ships a test** (`.claude/rules/python-testing.md:6-10`),
  and the fixture must be able to reproduce the bug: a capture holding only
  health checks cannot.
- **R6. Live-cluster tests carry the `cluster` marker**
  (`.claude/rules/python-testing.md:26-32`); the default run stays offline
  (`cli/tests/conftest.py:53-92`).
- **R7. Dependencies via `uv add`** if any are needed
  (`.claude/rules/uv-installer.md:6-8`). None is expected.
- **R8. Plain language in rendered strings**
  (`.claude/rules/plain-language.md`).
- **R9. Pre-existing failures get fixed, not skipped**
  (`.claude/rules/pre-existing-issues.md`).

## 7. Code surface

- `cli/src/localstack_cli/api/consul.py`: add `list_services()` over
  `GET /v1/catalog/services`, returning `dict[str, list[str]]` (name to
  tags). Tokenless, same `HEALTH_READ` capability name for the 403 message
  (`:25`).
- `cli/src/localstack_cli/api/services.py:72-89`: `join()` gains a
  REQUIRED `catalog: dict[str, list[str]]` parameter; `:89` stops deriving names from
  checks; `:110` keys rung (b) on the catalog.
- `cli/src/localstack_cli/commands/service.py:73-74`: add the `backend`
  column. `:91` also fetches the catalog and passes it to `join()`.
- `cli/tests/fixtures/scrub_capture.py:87`: add `consul_catalog` to the
  hardcoded capture list, which is the only way the new fixture is produced.
- `cli/tests/fixtures/capture/consul_catalog.json` **(new)**: the live
  `GET /v1/catalog/services` response, scrubbed by
  `cli/tests/fixtures/scrub_capture.py`. It must contain `consul` while
  `consul_health.json` contains no check with `ServiceName: "consul"`, which
  is what makes the regression reproducible.
- `cli/tests/test_api_consul.py`: `list_services()` parses the catalog,
  sends no token, and degrades on 403.
- `cli/tests/commands/test_read_commands.py`: `consul` renders
  `consul-name`; the table carries the backend for an unresolved row. Its
  `mock_cluster()` helper must also mock `GET /v1/catalog/services`, since
  seven existing tests route through it and the command now calls that
  endpoint.
- `cli/tests/api/test_services.py`: nine `join(..., NAMES)` call sites pass
  their names dict positionally and must move to keyword form (R2).
- `cli/tests/cluster/test_live.py`: the live catalog contains `consul`, and
  no live check carries `ServiceName: "consul"`.

Read, do not edit:

- `.loop/archive/D3-cli-read-commands/plan.md:445-451`: the three-rung ladder and
  the backend-rendering requirement this ticket satisfies.
- `cli/tests/test_read_guardrails.py:55-88`: the guardrails the new fetcher
  must not trip.

## 8. Tests & validation gates

Repo gate: `just pre_commit` (`.loop/config.json` `gates`, `justfile:18-19`),
which runs ruff lint, ruff format, mypy strict and pytest scoped to `^cli/`
(`.pre-commit-config.yaml:37-72`). Worktree prerequisite: `just
worktree_setup <path>` (`justfile:41-44`).

Offline suite: `uv run --project cli pytest`. Live: `-m cluster`.

The scored acceptance rows live in
`.loop/evals/D7-cli-service-join-consul-catalog.md`.

Tests to add, each homed in §7:

1. **The regression, and it must fail against today's code.** `join()` with
   a route named `consul`, a catalog containing `consul`, and checks
   containing no `ServiceName: "consul"` resolves `consul-name`, not
   `unresolved`. (`cli/tests/api/test_services.py`)
2. A route in neither the catalog nor the job list stays `unresolved`, with
   its backend populated. (`cli/tests/api/test_services.py`)
3. `list_services()` parses the catalog response and sends no token.
   (`cli/tests/test_api_consul.py`)
4. `list_services()` on 403 raises `MissingCapability`, so a tightened ACL
   degrades rather than crashes. (`cli/tests/test_api_consul.py`)
5. The rendered table carries the backend `ip:port` for an unresolved row.
   (`cli/tests/commands/test_read_commands.py`)
6. `localstack service` renders `consul` as `consul-name` against the
   fixtures. (`cli/tests/commands/test_read_commands.py`)
7. Live, `cluster`-marked: the catalog contains `consul`, and no health
   check carries `ServiceName: "consul"`. This pins the premise the whole
   ticket rests on, so a future Consul that DOES register a self-check makes
   the row go red rather than silently making the fix pointless.
   (`cli/tests/cluster/test_live.py`)

## 9. Risk assessment

- **Blast radius: one command's table.** Read-only HTTP GET. No cluster
  state changes.
- **Reversibility: high.** Revert the two files.
- **Likeliest failure mode: a green-first test.** Test 1 cannot be run
  against `main` as a red-first check, because `join()` there takes no
  `catalog` argument and the call raises `TypeError`, which proves nothing
  about the defect. **Test 6 is the red-first one**: it goes through the
  command against the committed fixtures, which already contain a `consul`
  route and no `consul` check. Run test 6 against `main`, see it fail, and
  only then change the join.
- **Second: one more request per `service` run.** `GET /v1/catalog/services`
  is one tokenless call against a five-node cluster, on a command that
  already issues one per routed job. Negligible, and it replaces no call.
- **Third: a 403 on the new endpoint takes down a command that worked.** The
  catalog read is tokenless like the health read, so it is denied only if
  the agent's `tokens.default` is removed, which would take the health read
  with it. R1 keeps the typed error so it degrades rather than crashes.

## 10. Subtickets (ordered)

1. Capture the live `GET /v1/catalog/services` into
   `cli/tests/fixtures/capture/consul_catalog.json` via `scrub_capture.py`,
   and assert against the existing `consul_health.json` that `consul` is in
   one and not the other.
2. Write test 6 and watch it fail against the current code. It is the only
   one of the two that can: test 1 calls `join()` with an argument `main`
   does not accept.
3. Add `list_services()` and its tests (3, 4).
4. Rekey rung (b) on the catalog; make tests 1, 2 and 6 pass.
5. Add the backend column; test 5.
6. The live test (7).
7. `just pre_commit`, then the review passes.

## 11. Open questions

- **Q1 — should the backend column show for every row, or only unresolved
  ones?** A column that is blank on 21 of 23 rows is noise; one that is
  always populated is four extra characters per row and no branching.
  Measured: 23 rows today, 13 of them `no-route` with `backend` empty, so
  the column is blank on 57% of rows rather than always populated.
  *Recommendation:* show it for every row anyway, and accept the blanks. The
  blank is meaningful (a job the edge does not serve has no backend), the
  data is on the dataclass already, and a column whose presence varies by
  row is harder to read than one that does not. Setting `backend` on the
  `no-route` branch is the alternative, but there is nothing true to put
  there.

- **Q2 — should `s3` resolve to `minio` via the Consul tag?** It can:
  `GET /v1/catalog/services` returns `minio -> ["http", "s3"]`, declared by
  the minio job on the port label behind the `s3` route. This is declared
  data, not an alias map, so the objection first raised against it was
  wrong.
  Measured live 2026-08-04 across the 25 catalog services: `http` is carried
  by 16 of them and `monitoring` by 9, so a tag rung needs a rule for the
  ambiguous case. But the tag `s3` is carried by **exactly one** service,
  `minio`, so a "resolve only on a unique tag match" rule already answers the
  case that prompted this ticket. The follow-up does not need to re-measure
  that.
  *Recommendation:* not in this ticket, and not because it is impossible.
  Choosing the disambiguation rule is a design fork, and this ticket's scope
  is two defects that are already understood. R1 returns the tags so the
  follow-up has them without another API change. If the operator wants it
  now, say so and this ticket grows a fifth requirement rather than the
  follow-up being lost.

## Premises / assumptions

- **P1.** Consul's catalog lists `consul`; its health checks do not carry a
  `ServiceName` of `consul`.
  `probe:` `GET /v1/catalog/services` returns 25 names including `consul`,
  `nomad`, `vault`. `probe:` across the 41 elements of
  `GET /v1/health/state/any`, `ServiceName` counts are `nomad` 3, `vault` 1,
  `consul` 0, and 5 entries with `ServiceName: ""`. Probed live 2026-08-04.

- **P2.** `vault` and `nomad` resolve today only because they own
  service-scoped checks, so the current rung is right by accident.
  `Evidence:` `cli/src/localstack_cli/api/services.py:89` derives the set
  from `check.service`; P1's counts show which names that yields.

- **P3.** `s3` cannot be resolved by ADDRESS, but can be by TAG.
  `probe:` `GET /v1/catalog/service/minio` returns `ServiceAddress
  10.88.0.2`, `ServicePort 0`, node `Address 192.168.2.29`. The node address
  matches the `s3` edge backend host, so the two are not in different
  address spaces; what defeats an address rung is the zero port plus
  `minio-console` returning the identical node address, leaving two
  candidates. `probe:` `GET /v1/catalog/services` returns
  `minio -> ["http", "s3"]`, so a tag rung would resolve it. Deferred per
  Q2, not refused. Probed live 2026-08-04.

- **P4.** The `backend` field exists and is already serialized, so rendering
  it is a display change and not a data change.
  `Evidence:` `cli/src/localstack_cli/api/services.py:57` declares it;
  `cli/src/localstack_cli/commands/service.py:73-74` omits it from the
  table.

- **P5.** The Consul catalog read needs no token, for the same reason the
  health read does not: the agent's `tokens.default` is set to the agent
  token.
  `Evidence:` `bootstrap/roles/consul_server/templates/consul.hcl.j2:29-32`.
  `probe:` tokenless `GET /v1/catalog/services` returns 200 with 25 names.
  Probed live 2026-08-04.

- **P6.** The repo gate is `just pre_commit`
  (`.loop/config.json` gates; `justfile:18-19`), running
  `.pre-commit-config.yaml`, whose `cli/` hooks are ruff, ruff-format, mypy
  strict and pytest (`.pre-commit-config.yaml:37-72`).
