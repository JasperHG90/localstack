---
type: verdict
title: 'Verdict: aim-to-apm reviewer round 1'
description: 'reviewer verdict for round 1 of aim-to-apm: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-28T10:37:55+00:00'
slug: aim-to-apm
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The migration does what the plan asks. apm.yml pins the 12 skills to the
exact `current.sha` that aim.lock.toml recorded, and the 6 rules and 2
subagents to 1c3dd31. aim.toml, aim.lock.toml and the AGENTS.md markers are
gone, and CLAUDE.md is still a symlink to AGENTS.md. The MCP entries are out
of .mcp.json. Both install recipes copy the 7 rules by name and remove the
two subagents. The pre-commit exclude covers the installer's paths. My own
stamp is green, including r8 on a clean checkout. The three findings are a
test I want stronger and two doc sentences that are now slightly wrong. None
needs another review.

## Checked

- `loopctl gate stamp` from the worktree: "stamp green:
  5644de5fc33e662e53238f80e82da8274e3ad930965a7702de91558264ff464d". Gates
  pre_commit and cli_tests passed, and rows r1 to r8 passed. I read the r8
  log. A real `apm install --frozen` installed 23 dependencies,
  `kmctl plugin patch` ran, then the cp and rm lines ran, and check-install
  exited 0. Because .claude/rules is gitignored, the clean run rebuilds the
  .opencode/rules copies from a fresh install, so a clean git status shows
  that the committed OpenCode rules match what APM installs.
- Pins: compared each skill ref in apm.yml with `[skill.current] sha` in
  `git show HEAD:aim.lock.toml`. All 12 match.
- r1 to r7: read cli/tests/test_agent_tooling.py. Each test asserts its
  row's fails_when, with the gaps noted in f1. The r7 test also checks that
  every `just X` the section names is a real justfile recipe.
- r9 (judgment): ran `diff -r` myself between the snapshot and the
  worktree's .claude/skills for all 12 skills. 11 are empty. python-review
  differs only by a `.DS_Store` in aim's copy. That is macOS Finder
  metadata, ignored by .gitignore, and not skill content, so I count r9's
  skill half as met. The rules and subagents diff is recorded at
  /tmp/claude-1000/-home-vscode-workspace/bb29ac4a-7b6b-458a-a055-0c05909aba19/scratchpad/aim-to-apm-r9-diff.txt.
  It shows the expected front matter changes (name and description dropped,
  `paths: **/*.py` on python-testing) and the newer python-testing body from
  1c3dd31. The scratchpad does not last, so the builder has to pass that
  diff to the operator in its report. r9 passes.
- r10 (judgment): .okf/decisions/0025-the-agent-guidelines-stay-in-agents-md.md
  covers the choice and names moving the guidelines into a rule as the
  rejected option, with the reason. Its claim that "all but five" files in
  .claude/rules are gitignored is true after this change. r10 passes.
- Consistency: grepped the tree for aim, drawio-mcp, excalidraw and caveman.
  Every remaining aim reference is about `_lazy.py` being copied from aim's
  code, which is still true. `kmctl check` reports "all checks passed".

## Findings

- f1 (test-strength, non-blocking): the r5 byte comparison is conditional,
  and nothing stops an extra named rule in the cp line. Make the comparison
  unconditional, or skip with a reason only when .claude/rules was never
  installed. Also assert that the set of `.claude/rules/*.md` names in each
  recipe equals the 7. r8 already covers byte identity on a clean checkout,
  so this is not blocking.
- f2 (docs, non-blocking): extend the .gitignore comment to say why
  slop-scan-for-docs is tracked.
- f3 (docs, non-blocking): reword the README so it says slop-scan-for-docs
  is committed in the repository, or limit "the one thing" to plugins.

## Notes

The primary checkout still has `.claude/plugins/aim-10ae737f6885d841/` and
a caveman entry in `.claude/settings.json`, as well as aim's copies under
`.claude/`. These are local, gitignored files, so the worktree diff does not
show them. Plan step 3 has to happen in the primary checkout at land, before
`just kmctl-install` runs there.
