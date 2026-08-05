---
verdict: pass
plan: 40eb9f011da201b7a100bb7a233b0e488468a6dc99b1c33496b93b83a5c475ce
---

# Plan review: D9-cli-service-one-row-per-job (pass `plan-validator`, cycle 3)

## Deterministic floor

`loopctl verify-plan D9-cli-service-one-row-per-job` prints `valid`, exit 0.
`sha256sum` of the plan on disk equals the fingerprint I was given.

## Premise verdict

**SOUND.** The design is unchanged from cycle 2, where I measured the premise
sound. The diff since then is exactly the three test-precision fixes I
required and nothing else (13 added lines, 6 removed, in R1, test 3 and test
6). All three landed and all three are accurate against the code. Nothing new
is load-bearing.

## The three required fixes

**Fix 1 (inter-group order). APPLIED and coherent.** R1 (`:76-79`) now reads:
"Groups keep their existing relative order: a group sits where its first row
sat, so the table stays sorted as it is today and only the strays move up to
join their group." That is a deterministic rule, and it is the recommendation
I gave. I implemented it literally over the fixture join: the `minio` group
anchors at index 4, where the `minio` row sits today
(`cli/src/localstack_cli/api/services.py:125` sorts routes by name), and `s3`
moves up from index 8 to index 5. Every other row keeps its position. The
previously UNCERTAIN P12 now HOLDS.

**Fix 2 (test 3's second orphan). APPLIED and accurate.** Test 3 (`:164-168`)
now names `ORPHAN_ROUTE` at `cli/tests/commands/test_read_commands.py:80-88`
and says to build a second and pass it through `mock_edge_job(config)`
(`:91`). Both anchors resolve: `ORPHAN_ROUTE` is defined at `:80-86` with
`EDGE_WITH_AN_ORPHAN = LIVE_SHAPE + ORPHAN_ROUTE` at `:88`, and
`def mock_edge_job(config: str | None = None)` is at `:91`, already taking the
argument. I also confirmed the underlying claim by probe: bare `LIVE_SHAPE`
yields ZERO unresolved rows, `+ ORPHAN_ROUTE` yields exactly one
(`['orphan']`), and a second built orphan yields two. Under R1 to R3 the two
land adjacent and each keeps its own `not found` `job` and `health` cells, so
the test has a real target and a real red.

**Fix 3 (test 6 scoped to the no-name path). APPLIED and accurate.** Test 6
(`:178-185`) scopes the identity assertion to the no-name path, citing
`cli/src/localstack_cli/commands/service.py:56-61`. That window is
`if name is not None:` through `rows = [row]`, which is exactly the rebind
that breaks identity, and the early `return` at `:69` sits before the
`table(` call at `:71`. All three anchors resolve.

## Per assumption

P1 to P11 all HOLD as measured in cycle 2; none of their text changed. P12
("inter-group order does not matter") is now moot: R1 states the order, and I
verified the stated order is what falls out.

Re-measured this cycle over the fixture join, in all three shapes (bare, one
orphan, two orphans), with the empty service-name map the tests' respx mocks
actually produce (`test_read_commands.py:170-172` returns
`{"TaskGroups": []}` for every non-haproxy job, so `job_service_names` is
empty and `_check_state([], checks)` at `services.py:137` returns `no check`):

    minio | minio | job-id     | no check
    s3    |       | consul-tag | passing

That is R2's stated measurement verbatim (`:86-88`). In every shape
`len(grouped) == len(rows)`, no `name` cell is blanked, and no distinct
`job`, `source` or `health` value disappears from the table. `consul-tag`
survives, so the canary at `test_read_commands.py:167-179` stays green, and
test 1's "both health values present" holds under the mock shape the tests
use.

## Most dangerous assumption

Still P7, that R2 and R4 are jointly satisfiable, and it still holds. R2 is
untouched this cycle and I re-measured it rather than carrying the old result
forward.

## Minor, not required

- R1's anchor row and R1's within-group order can be different rows. The
  group sits where its first row sat in join order, but renders its members in
  route-name order, so in a tag-only-reach shape the anchor (`s3`) is not the
  row printed first (`minio`). Deterministic and harmless; not worth a
  sentence unless the output surprises you.
- The three minors from cycle 2 stand and remain optional: `justfile:41-44`
  covers the recipe header at `:44`; test 1's both-health assertion is
  fixture-specific and correctly not carried into live test 7; §10's
  "tests 3 to 5" puts test 3 one subticket late.

Ready for `ready`.
