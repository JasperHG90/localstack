---
slug: skills-prompt-decisions-via-qa
blockers: []
friction: [other:claude-rules-gitignored-not-a-home, other:incomplete-reference-update-on-relocate]
worked: [adversarial-review]
harness_change:
---

## What worked

The adversarial pass earned its keep on a non-obvious defect the gates could
never catch: the new `.claude/rules/decision-prompts.md` was a gitignored,
aim-vendored orphan that would never commit, silently defeating the durable
home the DoD asked for. Moving the convention to `AGENTS.md` (tracked,
symlinked as `CLAUDE.md`) fixed it. The core behavioral change (convert only
discrete forks, keep free-form authoring prose) went in cleanly and held
across all three cycles.

## What worked less well

This took the full three review cycles. Two were self-inflicted: (1) the
ticket's own premise that `.claude/rules/` is a viable local home was wrong
(that whole tree is aim-vendored from external repos and gitignored), and
(2) when I relocated the file I updated Q2 but missed a dangling reference in
the section-Q preamble, so the next pass bounced on the stale path. Lesson:
on any file relocation, grep the whole repo for the old path before
re-stamping, not just the obvious call site.
