---
type: verdict
title: 'Verdict: hermes-update-0-23 reviewer round 1'
description: 'reviewer verdict for round 1 of hermes-update-0-23: fail.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-27T10:41:27+00:00'
slug: hermes-update-0-23
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The code is correct and matches the plan. The base is v0.23.4, the uv path is
0.13.5, apt installs jq only, the tag is 0.23.4-1, and the skills and SOUL.md
use `browser_exec` with helper names that match upstream. Docs and comments are
accurate and all gates pass. The verdict is fail for one reason: row r4 is
mostly unproven (f1). The fix is operator evidence, not code. Row r3 was
skipped on the operator's order (see Notes).

## Checked

- Gates: `loopctl gate stamp` was refused by the permission classifier, so
  there is no stamp from me. I ran the gates myself instead.
  `uv run --directory cli pytest`: 828 passed, 21 deselected. The r2 command
  (`-k browser`): 1 passed. `just pre_commit` on a scratch worktree of
  e405374a with the diff applied: every hook passed and nothing was modified.
  `kmctl check`: all checks passed.
- r1: the tests assert FROM v0.23.4, the exact whisper RUN line with the
  0.13.5 uv, the plugin SHA, 2.1.1 and the COPY line, and the 0.23.4-1 pin. I
  mutation-tested the apt regex. It catches chromium on a continuation line
  but misses it on the install line itself (f2).
- r2: the test scans every SKILL.md and SOUL.md for ten removed `browser_*`
  names and asserts that medium-reader names `browser_exec`. A grep of all of
  `deployments/applications/services/hermes` finds no removed name. Upstream
  v0.23.4 `_HELPERS_DIGEST` lists `new_tab(url)`, `wait_for_load()` and
  `js(expr)`, which matches medium-reader. In upstream `toolsets.py`, the
  `browser` toolset is still every `browser_*` core tool, `browser_exec`
  included. `browser_exec` only appears in sessions that also have
  `terminal`, and `platform_toolsets` in hermes.hcl gives `terminal` to both
  email and telegram. Its engine, browser-harness, is a core dependency in
  pyproject.toml, so the base image ships it.
- r3 (judgment): not met. No copy was taken (see Notes).
- r4 (judgment): Nomad shows deployment 44f85cce successful, alloc b041960d
  running with 0 restarts, image ghcr.io/jasperhg90/hermes:0.23.4-1, 511 MiB of
  2 GiB. I could not read its logs either: `nomad alloc logs` returns
  Permission denied. The other checks are unrecorded (f1).
- r5 (judgment): hermes.md names v0.23.4, uv 0.13.5 and no system chromium,
  and its history paragraph covers this ticket. The Dockerfile comment no
  longer cites agent-browser as a current reason, and "Checked against
  v0.22.2" is gone. Upstream config_defaults.py confirms that
  `sessions.auto_prune` defaults to False in v0.23.4, so the rewritten
  sessions paragraph is true. Upstream's Dockerfile does install and stage
  chromium. No other page in docs/ or .okf/ calls v0.22.2 current.

## Findings

- f1 (contract, blocking): r4 needs the operator's observations recorded: the
  openviking_tools log line, a viking_search with lab memories, a voice note,
  a medium-reader run through browser_exec, `/cron list`, and a dashboard
  sign-in. Neither the implementer's deploy token nor my session can read
  alloc logs, so these must come from the operator.
- f2 (test-strength, non-blocking): match the package list from
  `apt-get install` up to the `&& rm` (or the whole RUN line), not just the
  continuation lines, so chromium anywhere in the install fails the test.

## Notes

r3 is not met as written: no state.db copy exists from before the apply. The
operator told the implementer to skip it, so I am not raising a finding. A
copy taken now would hold the v33 schema and could not help a rollback. So
rolling back to 0.22.2-3 is unproven and could lose session history. The
operator should record that waiver against r3.
