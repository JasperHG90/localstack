---
verdict: pass
tree: 6da6c67b9d4c5d1ea768470924a831714522ca56
---

# Adversarial review: D8-cli-service-tag-rung (cycle 2)

Re-bind plus regression check. The cycle-1 pass stands, the four claimed
edits are the only delta, all of them are correct, and both guardrails plus
the blast radius still hold under re-execution.

## Deterministic floor

`loopctl verify-eval-substance D8-cli-service-tag-rung` -> `valid`, exit 0.
No grep-only scorer, no stale `depends_on`, no dropped field check.
Proceeded to the semantic pass.

`.loop/stamp.json:2` carries `6da6c67b9d4c5d1ea768470924a831714522ca56`,
the fingerprint I was given, and `loopctl verify` returns `ok`.

## Gates, re-run

| Gate | Result |
| --- | --- |
| `just pre_commit` | 14 hooks passed (ruff lint, ruff format, mypy strict, pytest) |
| `loopctl verify` | `ok` |
| `uv run --project cli pytest cli` | 490 passed, 21 deselected |
| `uv run --project cli pytest cli -m cluster` | 21 passed |

The live run still holds: `s3` resolves to `minio` against the running
cluster and `test_every_live_route_name_has_at_most_one_tag_carrier` is
green, so the premise is measured today, not just planned.

## The delta is exactly the four claimed edits

Both stamped trees are real git objects, so I diffed cycle 1 against cycle 2
directly rather than trusting the hand-off:

```
git diff 475c14cba2b4697974a9f0deca7ad5b0536f97eb 6da6c67b9d4c5d1ea768470924a831714522ca56
  cli/src/localstack_cli/api/services.py   |  5 +++--
  cli/tests/commands/test_read_commands.py | 16 ++++++++++------
  docs/cli-read-commands.md                |  2 +-
```

Nothing else moved. `.loop/ledger.json` is harness bookkeeping only
(`stage`, `attempts`, `review_cycles`, `review_verdict`); no ticket content.

1. **L4 closed.** `test_service_json_is_parseable`
   (`cli/tests/commands/test_read_commands.py:197-212`) now calls
   `mock_edge_job(EDGE_WITH_AN_ORPHAN)` and asserts
   `>= {"job-id", "consul-tag", "no-route", "unresolved"}`.
2. **L1 closed.** `cli/tests/commands/test_read_commands.py:516-519` is back
   to the one-liner. The `ruff format` hook passes on this tree, which is the
   proof that the reflow was never forced there.
3. **L3 closed.** `cli/src/localstack_cli/api/services.py:108-109` now says
   rung (b) resolves against the keys and the tag rung against the values.
   That matches the code: `consul_services = set(catalog)` at `:121` used at
   `:142` is the keys; `_sole_tag_carrier` scans `catalog.items()` for
   `name in tags` at `:87`, which is the values.
4. **Doc grammar closed.** `docs/cli-read-commands.md:57` reads "Two
   services carrying the same tag leave the row unresolved".

## The new assertion is load-bearing, proved by mutation

I shadowed the package via `PYTHONPATH` with mutated copies. No repo file
was touched.

Mutant: drop the unresolved row entirely (`api/services.py:173-183` else
branch replaced with `continue`). This is the mutation the *old* form of the
test would have survived, because under `LIVE_SHAPE` no row is unresolved
after the tag rung. The new form catches it:

```
FAILED cli/tests/commands/test_read_commands.py::test_service_json_is_parseable
E   assert {'consul-name...', 'no-route'} >= {'consul-tag'... 'unresolved'}
E     Extra items in the right set:
E     'unresolved'
```

The added element is exactly the one that reddens. The gap I flagged is
closed, not papered over.

## Both guardrails still bite

**1. Ambiguity (`_sole_tag_carrier`, `api/services.py:79-88`).** Mutating
`len(carriers) == 1` to `>= 1`:

```
FAILED tests/api/test_services.py::test_a_tag_carried_by_two_services_resolves_nothing
E   assert <JobSource.CONSUL_TAG: 'consul-tag'> is <JobSource.UNRESOLVED>
E    +  where ... ServiceRow(name='s3', job='one', job_source=CONSUL_TAG, ...)
```

Same silent first-sorts-wins failure as cycle 1, same single test catching
it.

**2. Rung order (`api/services.py:142-172`).** Two reorderings, both red:

- Tag block moved above the catalog-name block: `FAILED
  test_a_catalog_name_match_beats_a_tag_match`.
- Tag block moved to the head of the chain (`if`, with the job-id block
  demoted to `elif`): `FAILED test_a_job_id_match_beats_a_tag_match` AND
  `FAILED test_a_catalog_name_match_beats_a_tag_match`.

Both halves of eval row 3 stay load-bearing.

## Blast radius re-measured, not assumed

The only source change since cycle 1 is a docstring, but I re-ran the full
row diff anyway: `join()` over the fixture set (`LIVE_SHAPE` routes,
`jobs_statuses.json`, `consul_health.json`, `consul_catalog.json`) under
`HEAD`'s `services.py` and under this tree's, every row compared.

```
old rows: 23   new rows: 23
-s3	not found	unresolved	not found	10.0.0.29:9000
+s3	minio	consul-tag	passing	10.0.0.29:9000
```

One row, unchanged from cycle 1. No row that resolved before resolves
differently, no row appears or disappears.

## Eval rows

All eight still satisfied at this tree. Row 6 in particular: the repaired
test's subject is the `orphan` route, which is genuinely unresolved, and
`test_haproxy.py` is untouched and green (its ten-route pin on the shared
`LIVE_SHAPE` still holds, because the orphan lives in
`test_read_commands.py`'s own copy at `:77-88`). Row 7: neither the module
docstring nor `docs/cli-read-commands.md` still names `s3` as the live
unresolved example.

## Findings

All low. None blocks the commit. Three carry over from cycle 1 unchanged;
one is new and cosmetic.

**L2 (low, stale doc, still open).**
`cli/src/localstack_cli/api/consul.py:74-77` still reads "so a later rung
COULD resolve that route from data rather than a guess. A `list[str]` return
would foreclose it." That rung shipped in this diff, so the conditional
tense is now wrong. This was in my cycle-1 findings and the hand-off does
not mention it either way. One-line tense fix.

**L5 (low, redundancy, carried).**
`test_a_route_matching_nothing_at_all_still_renders`
(`cli/tests/api/test_services.py:261`) asserts a strict subset of
`test_a_route_in_neither_the_catalog_nor_the_jobs_stays_unresolved`
(`:173`) on the same fixture. Eval row 4 demands the row, so it is in scope;
it is noise, not a defect.

**L6 (low, style, carried).** `cli/tests/cluster/test_live.py:148` imports
`services` inside the function while every other `api` module is imported at
`:15`.

**L7 (low, redundancy, carried).**
`test_every_live_route_name_has_at_most_one_tag_carrier:143` re-asserts
`ambiguous["s3"] == ["minio"]`, already pinned by
`test_the_minio_service_still_carries_the_s3_tag:123`. The all-routes sweep
is the new part; the `s3` line duplicates.

**L8 (low, new, cosmetic).**
`cli/src/localstack_cli/api/services.py:110` is a ragged half-line
("Required and keyword-only, both") left by the L3 fix. The paragraph wants
one rewrap. Ruff does not touch docstring fill, so nothing catches it.

## R4a: I agree with deferring it

Your reading of my cycle-1 note is right, and so is the call. The `job`
column naming a Consul service on a tag match is misleading in the general
case (`otlp` would render `job = phoenix-grpc`, and `phoenix-grpc` is not a
Nomad job), and it breaks the invariant rung (b) keeps by writing `no job
(agent endpoint)` at `api/services.py:147`. But the ticket freezes it at §6
R4a, and eval row 5 scores "a tag match reports the matched service" as
built. Changing it here would put the diff out of contract with its own
signed eval, which is a worse failure than the one it fixes. A follow-up
ticket is the right home, and the fix is one expression
(`tagged if tagged in by_id else f"{tagged} (consul service)"`), so it is
cheap to carry.

## Scope

Every changed line traces to the ticket. The cycle-2 delta touches three
files and closes three review findings. No Terraform, no Ansible, no job
change, matching §5.

## Verdict

**pass.** The four edits are correct and complete, the new assertion was
seen red under the mutation it exists to catch, both guardrails were seen
red under reordering and relaxation, the blast radius is still one row
measured across the full fixture set, and every gate including `-m cluster`
is green at this tree. The five remaining findings are documentation tense,
docstring fill and test redundancy; none changes what the code does.
