---
verdict: pass
tree: bb0be2425282b212212e10fa3c23a5b239511380
---

# Adversarial review: D7-cli-service-join-consul-catalog (cycle 2)

Re-bind plus regression check against cycle 1
(`tree: bccbdeccd885776cf427ba38f4ae1d2499e918e8`,
`pass-with-required-fixes`). The substance was proved by execution last
round; this pass re-runs the deterministic floor, every gate, and every
mutation probe against the new tree, then checks the three edits.

## Deterministic floor

`loopctl verify-eval-substance D7-cli-service-join-consul-catalog` returns
`valid` (exit 0). No mechanical eval defect, so the semantic pass ran.

## Gates, re-run independently

| Gate | Result |
| --- | --- |
| `just pre_commit` | 14 hooks, all Passed (ruff lint, ruff format, mypy strict, pytest) |
| `loopctl verify` | `ok` — stamp tree matches `bb0be24`, re-checked after all probing |
| `uv run pytest` (cli) | 484 passed, 19 deselected |
| `uv run pytest -m cluster` (cli) | 19 passed |

## Cycle-1 findings: status

### F1 (was required) — fixed, and the replacement is factually correct

`docs/cli-read-commands.md:55-59` no longer says "actionable" and no longer
claims the backend is "the only thing". Scans over the whole file are clean:
0 em dashes in 884 words, no ` -- `, no tier-1 slop, no semicolon splice, no
British spellings, no prose line over 80 chars.

I checked the new paragraph's claims against the live cluster rather than
taking them on trust, because the replacement text introduced a concrete IP
the fixtures do not carry (`cli/tests/fixtures/haproxy_cfg.py:61` has the
scrubbed `10.0.0.29:9000`). `localstack service --json` against the real
cluster:

```
{'name': 's3',    'backend': '192.168.2.29:9000', 'job_source': 'unresolved'}
{'name': 'minio', 'backend': '192.168.2.29:9001', 'job_source': 'job-id'}
```

So `192.168.2.29:9000` is the live `s3` backend, and MinIO's console on
`:9001` of the same host is what makes "recognizably MinIO's S3 API" true.
The other new claim, "blank for a `no-route` row", also holds: the distinct
set of `no-route` backends live is `{''}`.

The `consul-name` table cell dropped from 293 to 157 characters
(`docs/cli-read-commands.md:42`), with the catalog-not-checks explanation
moved into prose at `:50-53`.

### F2 (advisory) — fixed

`cli/tests/test_api_consul.py:96-98` now compares
`set(services["minio"]) == {"s3", "http"}`. Order-insensitive, still exact on
membership, so eval row 3's "`minio` must come back carrying `s3`" is
covered and a fixture recapture cannot flip it for a non-behavioral reason.

### F3 (advisory) — fixed

`import pytest` is at `cli/tests/api/test_services.py:3`. No function-local
import remains in the file. Ruff format and lint pass with the new ordering.

### F4 (advisory) — accepted, no change wanted

You asked whether an unmapped row is worse than a lost premise. It is not.
Keep the test. Three reasons:

1. The eval is a floor on what must be true, not a ceiling on what may be
   tested. Nothing in the eval or the ticket forbids a row it does not name.
2. The cost is zero offline. It carries the `cluster` marker and `addopts`
   deselects it, so the default `uv run pytest` never sees it.
3. The second assertion I flagged
   (`cli/tests/cluster/test_live.py:121`, `[name for name, tags in
   catalog.items() if "s3" in tags] == ["minio"]`) is sharper than I gave it
   credit for on re-reading. A tag rung that resolves the `s3` route needs
   exactly one candidate carrying the tag. Uniqueness is not decoration on
   the premise, it is the premise. If a second service gains an `s3` tag the
   follow-up ticket needs to know before it is written, not after.

The one thing to watch: if Q2 is ever dropped rather than implemented, this
test outlives its reason and should go with it.

## Regression probes, re-run against this tree

I rebuilt an isolated copy without `.venv`
(`tar --exclude=.venv --exclude=__pycache__`, fresh `uv sync`) and confirmed
`localstack_cli.__file__` resolves into the copy, so nothing was measured
against the fixed editable install. Nineteen tests fail there for want of
the repo root (`test_breakglass_runbook_facts.py`, `test_devcontainer_path.py`,
`test_versions.py`); none are in this ticket's files, and the three files
that are (`tests/api/test_services.py`, `tests/test_api_consul.py`,
`tests/commands/test_read_commands.py`) baseline at 61 passed.

**Red-first still red (eval rows 1 and 5).** Reverting only the three source
files to `git show HEAD:` and keeping the shipped tests:

```
test_consul_resolves_from_the_catalog_not_from_health_checks
  AssertionError: assert 'unresolved' == 'consul-name'
test_the_table_says_where_an_unresolved_row_points
  AssertionError: assert 'backend' in 'services ... ┏━━━ ...'
```

Both fail on the assertion, not on an exception; the command still exits
`<Result okay>`. Restoring the three files returns 61 passed.

**Guardrail row 6 still bites.** Reintroducing the fallback at
`cli/src/localstack_cli/api/services.py:101`
(`set(catalog) | {check.service for check in checks if check.service}`):

```
tests/api/test_services.py:195 test_the_join_never_derives_names_from_checks
  assert <JobSource.CONSUL_NAME> is <JobSource.UNRESOLVED>
```

**Guardrail row 7 still bites, both halves.** Rewriting the single
production call site to the positional form:

```
src/localstack_cli/commands/service.py:102: error: Too many positional
  arguments for "join"  [call-arg]
```

I also probed the shape I had not tried at cycle 1: actually removing the
keyword-only marker. Because `service_names` carries a default, deleting the
bare `*` at `cli/src/localstack_cli/api/services.py:77` is a hard
`SyntaxError`, so the only way to reach a positional `catalog` is to reorder
it ahead of `service_names`. That shape is caught even harder: mypy strict
reports `"join" gets multiple values for keyword argument "catalog"` at all
ten call sites, and 19 of 19 tests in the file go red. The keyword-only
guarantee is stronger than my cycle-1 note credited.

## Scope

The changed file set is unchanged from cycle 1 (nine modified files plus the
new `cli/tests/fixtures/capture/consul_catalog.json`), so no new surface
crept in with the fixes. `.loop/ledger.json` moves stage `ready` to
`adversarial-review` and records the two verdict paths: harness bookkeeping.

## Findings

### A1 (advisory, pre-existing, not introduced here) A hard count in the doc has drifted

`docs/cli-read-commands.md:44`:

> | `no-route` | A job the edge does not serve. Thirteen exist. |

Live today the table renders 14 `no-route` rows out of 24 (I counted them
from `localstack service --json`; at cycle 1 the same command returned 23
rows, so the cluster gained a job between the two passes). The eval's row 5
carries the same number ("the 13 `no-route` rows").

Not a defect in this diff: the line is untouched context in
`git diff HEAD -- docs/cli-read-commands.md`, and the drift came from the
cluster, not from the change. Raising it because the repo's
pre-existing-issues rule asks the noticing agent to name it. The durable fix
is to drop the count rather than re-pin it, since it is state that changes
without anyone editing the doc. Out of scope for D7 either way.

### Informational: eval row 5's expected value names the live IP, not the fixture's

Row 5's input is "`localstack service` rendered against the fixtures" but its
expected value is "the `s3` row shows `192.168.2.29:9000`". The fixtures
carry the scrubbed `10.0.0.29:9000` (`cli/tests/fixtures/haproxy_cfg.py:61`),
which is what `cli/tests/commands/test_read_commands.py:604` asserts. The
Scorer column governs and says "`s3` row shows its `ip:port`", which is
satisfied. Noting it for the record: the eval is signed off and unchanged by
this diff, and no assertion depends on the mismatch.

### Informational: one contrastive construction kept, correctly

`docs/cli-read-commands.md:50`, "reads Consul's catalog, not its health
checks", is the bare trailing contrastive the slop rule flags. It is the one
case the rule says to keep: reading the checks is the defect this ticket
removes, so the contrast is load-bearing and does not survive removal.
Flagging only so the documentation pass does not treat it as an oversight.

## Verdict

`pass`. The required fix landed and its replacement text is verified against
the live cluster rather than asserted. Both advisories the author chose to
act on are correctly applied. The advisory the author chose to keep is the
right call, and I withdraw it. Every gate is green including `-m cluster`,
and every guardrail and red-first probe reproduces against this tree.
Bound to `bb0be2425282b212212e10fa3c23a5b239511380`.
