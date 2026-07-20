---
slug: loop-doc-writer-and-custom-stages
cycles: 0
gates_red: 0
blockers: []
friction: [other:ticket-section-mismatch]
worked: [other:docs-verified-against-code]
harness_change: the repo could now dogfood its own new passes (enable the documentation review pass on itself)
---

## What worked

Zero cycles, zero red gates on the docs-heaviest ticket. The doc hallucination
risk was the real hazard, and I defused it by cross-checking every config key,
agent name, and behavior claim in the README, DECISIONS, and SKILL against the
shipped `config.py`/`hooks.py` and the on-disk agent files BEFORE the review,
and by running the slop scan on all four markdown files. The reviewer found no
hallucinations and no new slop, so the doc ticket passed first try.

## What worked less well

The §7-vs-§8 scope gap recurred: the ticket's Code surface listed only
`tests/test_manifest.py`, but §8 required an integration test with no declared
home. This is the third ticket where the same authoring defect surfaced, which
is exactly the signal `loopctl distill` should catch: the `ticket-planner`
should learn to list, in §7, a file for every test §8 names. Placing it in
`test_ctl.py` (mirror-the-source) was the right call each time, but the
implementer should not have to make it repeatedly.
