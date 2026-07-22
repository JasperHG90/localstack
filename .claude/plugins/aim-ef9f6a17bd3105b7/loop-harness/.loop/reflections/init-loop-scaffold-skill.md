---
slug: init-loop-scaffold-skill
blockers: []
friction: [other:skill-creator-eval-loop-overkill]
worked: [eval-as-spec, tests-first, surgical-doc-repoint]
harness_change:
---

## What worked

The eval marker and the plan's §7 code-surface list made this nearly
mechanical: every doc anchor to repoint was named, so the four edits
traced cleanly and no competing setup story was left behind. Writing the
red manifest test first (mirroring `test_create_eval_skill_is_present`)
gave a concrete done-signal before the skill existed. Both review passes
returned pass on the first tree; the only note was informational and
shared by both reviewers.

## What worked less well

The plan (§6) mandated authoring via the `skill-creator` skill, but that
skill is an interactive draft-test-benchmark-iterate harness built for a
live operator evaluating outputs, not for an autonomous single-ticket
loop. I invoked it and followed its writing conventions (front matter,
description-as-trigger, house style), then deliberately skipped its
eval-benchmark loop, which §8 itself confirms is inapplicable (the skill
is prose with no unit-testable output). A future ticket mandating
skill-creator inside the loop should say up front which parts apply:
its authoring conventions, not its quantitative eval machinery.
