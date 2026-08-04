---
verdict: pass
tree: bb0be2425282b212212e10fa3c23a5b239511380
---

# Documentation freshness: D7-cli-service-join-consul-catalog (cycle 2)

**Pass.** The cycle-1 required fix is applied and the rewritten passage is
still true line by line. Advisories 1 and 2 were both handled the way the
verdict asked. No new drift appeared, and the slop scan on the changed prose
is clean.

## Cycle-1 findings: disposition

### R1 (required) — RESOLVED

`docs/cli-read-commands.md:55-59` now reads:

> The `backend` column shows the `ip:port` the edge sends a hostname to. It
> is blank for a `no-route` row, which has no backend to show. On an
> `unresolved` row it is the piece that lets you place the service yourself:
> `s3` points at `192.168.2.29:9000`, which is recognizably MinIO's S3 API
> even though nothing in Nomad or Consul is named `s3`.

"actionable" is gone (tier-1 scan on the whole file returns zero hits), and
the "the only thing" overstatement is gone with it. Every clause re-verified
against code:

- "the `ip:port` the edge sends a hostname to" — `backend =
  f"{route.backend_host}:{route.backend_port}"`,
  `cli/src/localstack_cli/api/services.py:106`.
- "blank for a `no-route` row" — the `no-route` branch at
  `cli/src/localstack_cli/api/services.py:150-158` omits `backend`, so it
  takes the dataclass default `""` (`:57`). All three routed branches pass
  `backend=backend` (`:118`, `:130`, `:142`), so `no-route` is still the
  only blank case. Rendered at
  `cli/src/localstack_cli/commands/service.py:73-74`, asserted at
  `cli/tests/commands/test_read_commands.py:601-604`.
- "On an `unresolved` row it is the piece that lets you place the service
  yourself" — the `unresolved` branch does carry `backend`
  (`cli/src/localstack_cli/api/services.py:142`) while `job` and `health`
  are both `not found` (`:139-141`), so the claim that it is what is left to
  go on is accurate, and it no longer excludes the `url` column.
- "`s3` points at `192.168.2.29:9000`" — `deployments/infrastructure/
  services/haproxy.hcl:131` (`server s3_1 192.168.2.29:9000 check`).
- "which is recognizably MinIO's S3 API" — 9000 is MinIO's API port and 9001
  its console (`deployments/infrastructure/services/minio.hcl:20,23,68`,
  `--console-address :9001`). Independently labeled the same way at
  `docs/haproxy_reverse_proxy.md:16` ("9000 (API)") versus `:15` ("9001
  (console)").
- "nothing in Nomad or Consul is **named** `s3`" — still exactly right on
  both halves. No job id `s3` among the 19 in
  `cli/tests/fixtures/capture/jobs_statuses.json`; no key `s3` among the 25
  in `cli/tests/fixtures/capture/consul_catalog.json`. `minio` carries `s3`
  as a **tag**, and the sentence says "named", so it neither misstates today
  nor forecloses the deferred tag rung documented at
  `cli/src/localstack_cli/api/consul.py:74-78`.

The live-versus-scrubbed address gap stands as judged at cycle 1: the doc
describes the live cluster (`192.168.2.29:9000`), the offline fixture uses
the scrubbed `10.0.0.29:9000` (`cli/tests/fixtures/haproxy_cfg.py:61`).
Literal LAN addresses are the established convention in this docs tree
(`docs/haproxy_reverse_proxy.md:15-20`).

### A1 (advisory) — RESOLVED

The `consul-name` cell (`docs/cli-read-commands.md:42`) went from 293
characters to 157, and is now one definition sentence plus the
agent-endpoint gloss. 157 puts it inside the repo's normal band for table
rows (`docs/cluster-roles.md:574` is 200, `docs/cli-deps.md:235` is 196), so
it is no longer the outlier. The `unresolved` cell at `:43` is 143.

**Nothing was lost in the split.** The moved text is now
`docs/cli-read-commands.md:50-53`, and it is more precise than the cell
version, not less:

> The `consul-name` rung reads Consul's catalog, not its health checks. That
> distinction is load-bearing: Consul registers itself as a service, but its
> only check is node-level and carries no service name, so a rung keyed on
> checks reports `consul` as unresolved.

Each claim re-verified against the committed fixtures:

- "reads Consul's catalog" — `consul_services = set(catalog)`
  (`cli/src/localstack_cli/api/services.py:101`), tested by `route.name in
  consul_services` (`:122`), fed from `list_services()` over
  `GET /v1/catalog/services` (`cli/src/localstack_cli/api/consul.py:79`) at
  `cli/src/localstack_cli/commands/service.py:93,102`.
- "Consul registers itself as a service" — `consul` is a key in
  `cli/tests/fixtures/capture/consul_catalog.json`.
- "its only check is node-level and carries no service name" — zero checks
  in `cli/tests/fixtures/capture/consul_health.json` carry `ServiceName:
  "consul"`, and every check with an empty `ServiceName` has `CheckID:
  serfHealth`, which is node-level.
- "so a rung keyed on checks reports `consul` as unresolved" — this clause
  is new relative to the cell version and it holds: a `consul_services`
  built from check service names would not contain `consul`, so the `consul`
  route falls to the `else` at
  `cli/src/localstack_cli/api/services.py:134-144`, which sets
  `JobSource.UNRESOLVED`. The live behavior it replaces is pinned the other
  way by `cli/tests/commands/test_read_commands.py:581-584`, which asserts
  `consul-name` for `consul`, `vault` and `nomad`.

The table cell that remains ("No such job, but Consul's catalog lists a
service by that name") still matches `:101,122`, and the `unresolved` cell
("matching no job and no catalog service") still matches the `else` branch.
`s3` is absent from the catalog fixture, so it still renders `unresolved`.

### A2 (advisory) — HANDLED AS RECOMMENDED

"reads Consul's catalog, not its health checks" is kept, relocated to
`docs/cli-read-commands.md:50`. My cycle-1 reasoning stands: the contrast is
load-bearing because the checks *were* the source before this commit, and
naming what it is no longer is what stops a reader re-deriving the old
behavior. `.claude/rules/slop-scan-for-docs.md` keeps a contrastive form
"when the contrast is load-bearing". Recorded again so a later scanner run
does not re-litigate it.

### A3 (advisory) — STILL OPEN, and I still say leave it

`ROADMAP.md:201` cites `.loop/plans/D2-cli-login-broker-tokens.md`, which
does not exist (D2 is archived at
`.loop/archive/D2-cli-login-broker-tokens/plan.md`). **Do not sweep it into
this ticket.** It predates the diff, sits in a file this change does not
touch, and fixing it would put an unrelated line in a CLI commit. It is
worth its own one-line ticket alongside a sweep of the other `.loop/` cites,
since the archiving pattern will keep producing them.

Full sweep of `.loop/` paths cited from docs, at this tree: two references,
one dead (`ROADMAP.md:201`, above) and one live
(`docs/postgres-vault-dynamic-creds-spike.md:141` to
`.loop/plans/R3-rollout-postgres-vault-db-creds.md`, present). This
session's archiving created no new broken reference.

## New drift: none

- `list_services()` still has exactly one production caller,
  `cli/src/localstack_cli/commands/service.py:93`. `localstack monitor` and
  `localstack status` reach Consul only through `list_checks`
  (`cli/src/localstack_cli/tui/monitor.py:56`,
  `cli/src/localstack_cli/api/status.py:89`), so `docs/monitoring.md`
  describes nothing that moved.
- The four table rows at `docs/cli-read-commands.md:41-44` are still exactly
  the four `JobSource` members at
  `cli/src/localstack_cli/api/services.py:34-38`, with matching strings.
- `docs/cli-read-commands.md:17` ("`--json` ... emits the command's own
  data") still holds: `emit_json(rows)` serializes the same `ServiceRow`
  that renders `backend`. `:117` ("Consul data is read with no token") still
  holds: `list_services()` calls `get_json(...)` with no token, same shape as
  `list_checks()`.
- No other doc in the repo describes the `service` table's columns or the
  Consul rung. `README.md` lists command names only. No `SKILL.md` and no
  `cli/README.md`.

## Slop scan on the changed prose: clean

Run over `docs/cli-read-commands.md` at this tree. Zero em-dashes, zero
` -- ` substitutions, zero unicode smart quotes, zero prose semicolon
splices, zero British spellings, zero tier-1 words, zero identity leaks,
zero `TODO`/`FIXME`/`XXX`/`HACK`, zero prose arrows, zero self-narration,
zero participial tails, zero "not just / not only", zero spatial copulas,
zero emphasis crutches, zero unbacked quality claims. Every backticked
identifier and every cited path in the changed lines resolves. Prose lines
wrap under 80; the only two lines over 80 are the two table rows, which
cannot be wrapped and are within the repo's normal band.

"load-bearing" at `:51` is established vocabulary here, not a metaphor to
strip: `docs/breakglass.md`, `docs/workload-identity.md`,
`docs/postgres-vault-dynamic-creds-spike.md` and
`cli/src/localstack_cli/commands/breakglass.py:8` all use it.

## Verdict

**pass.** A reader following `docs/cli-read-commands.md` at this tree is
right about how the `consul-name` rung resolves, why `s3` stays
`unresolved`, and what the new `backend` column shows and when it is blank.
Nothing is required. The one open item, `ROADMAP.md:201`, is pre-existing,
outside this diff, and better handled as its own sweep.
