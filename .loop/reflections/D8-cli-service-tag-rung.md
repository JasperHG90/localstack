---
slug: D8-cli-service-tag-rung
blockers: []
friction: [vacuous-tests, other:deferred-what-the-operator-asked-for-twice]
worked: [other:mutation-proved-every-guardrail, other:measured-the-ambiguity-instead-of-assuming-it]
cycles: 2
gates_red: 0
harness_change:
---

## What worked

Measuring the ambiguity instead of arguing about it. D7 deferred this rung on
the grounds that Consul tags are not unique, and that is true in general:
`http` is carried by 16 services here and `monitoring` by 9. But the question
is not whether tags are unique, it is whether any ROUTE NAME is carried by
more than one service. Asked that way across all ten routes, the answer is
no: only `s3` and `memex` have carriers, both single, and `memex` already
resolves higher up the ladder. One measurement turned a design fork into a
one-branch change with a known blast radius of exactly one row.

Every guardrail was proved by mutation rather than asserted. The reviewer
relaxed `len(carriers) == 1` to `>= 1` and watched the ambiguity test go red,
moved the tag branch above each of the two existing rungs and watched the
order tests go red, and dropped the unresolved branch entirely to check the
repaired coverage test still bites. A guardrail nobody has seen fail is a
comment.

## What worked less well

I deferred something the operator had already asked for. Told twice that `s3`
is MinIO, I shipped D7 with `s3` still rendering `not found` and wrote a
paragraph explaining why resolving it would need a disambiguation rule I had
not designed. The rule turned out to be one line, the data was already being
fetched by the request D7 itself added, and the measurement that made it safe
took one command. "Deferred with the evidence recorded" reads as rigor and
was, here, a way of not doing the thing that had been asked for. The right
move was to spend five minutes measuring before writing the deferral.

The fixtures had exactly one unresolved row, and it was the row this ticket
resolves. Three tests used `s3` as their `unresolved` example, so after the
change all three would have passed while covering nothing: not a red test, a
silently empty one. The plan reviewer caught it before implementation. The
repair is an eleventh route in a module-local edge config rather than in the
shared `LIVE_SHAPE`, which `test_haproxy.py` pins at exactly ten routes by
name. The general lesson: when a change makes a category empty, every test
that used a member of that category as its example is now vacuous, and
nothing goes red to tell you.

Two open items, both non-blocking and both named by the reviewers at the
final cycle. `api/consul.py:74-77` still says a tag rung "could" resolve a
route, in the past tense of a thing that has now shipped; and
`api/services.py:110` carries a ragged half-line left by a docstring edit.
Fixing either would invalidate two passing verdicts and cost a third review
cycle for a tense and a rewrap, so they ship open.

One finding deliberately not fixed here: R4a puts the matched SERVICE name in
the `job` column, while rung (b) writes "no job (agent endpoint)" precisely so
that column never names a job that does not exist. Both reviewers agree it is
misleading in the general case (a route named `otlp` would render
`job = phoenix-grpc`), and both agree it should not be fixed in this diff,
because the ticket froze it at R4a and the signed eval scores the as-built
behavior. Changing it here would put the diff out of contract with its own
eval. It wants a follow-up ticket, and the fix is one expression.
