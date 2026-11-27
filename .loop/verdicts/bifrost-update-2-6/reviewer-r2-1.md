---
type: verdict
title: 'Verdict: bifrost-update-2-6 reviewer round 2'
description: 'reviewer verdict for round 2 of bifrost-update-2-6: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-27T12:49:01+00:00'
slug: bifrost-update-2-6
pass: reviewer
round: 2
body_schema: verdict/1
---

## Summary

The change is ready to commit. Bifrost is pinned to 2.7.0, the pin test moved
with it, and the component page records the operator's no-dump decision and
the correct one-way migrations for both steps. The gates pass and the live
gateway runs 2.7.0 and passes the smoke checks. Both round-1 findings are
resolved. The one new finding is a readiness race that was already there
before this change. It does not block.

## Checked

- Diff: the worktree changes are uncommitted against HEAD 0ee1dc51, and HEAD
  matches main outside `.loop/`. I read all three changed files.
  `services.tf` changes one line (`bifrost_version = "2.7.0"`).
  `providers.tf` is untouched (`~>0.1.0`).
- Gates: `loopctl gate stamp` printed `pass gate pre_commit`, `pass gate
  cli_tests`, `pass eval-row r1`, `stamp green:
  9bba4978b031c123e4b6123ee54190f475ed65c046c364479614ad87c67e197c`.
- r1: the test asserts the pin list equals exactly `["2.7.0"]`, the
  `~>0.1.0` provider constraint, and that the smoke script still expects
  `access_not_found` and no longer expects `virtual_key_not_found`. Every
  clause of fails_when would fail it.
- r2 (judgment): the page says the operator chose no dump, that there is no
  restore point to 2.3.1, that 2.6.0 to 2.7.0 adds eight migrations, six of
  which can be undone, and it names both one-way migrations. It says there is
  no way back to 2.6.0 without a dump. It claims no rollback path. The names
  match plan step 3 and the plan-review round 4 check against the release
  notes. Passes.
- r3 (judgment): I re-ran `scripts/bifrost_smoke.py` against
  192.168.2.50:8080. It printed gateway "v2.7.0" and ok on all five checks.
  `nomad job inspect` shows image `docker.io/maximhq/bifrost:v2.7.0`, and
  deployment 78c9f536 is successful. I accept the implementer's recorded
  evidence for the rerank (200, [0.999, 0.024]), the Gemini chat (200) and the
  second plan (only `nomad_job.hermes`, no `bifrost_virtual_key`). That hermes
  diff comes from hermes-update-0-23 being live from its own worktree and not
  yet on main. Passes.
- r4 (judgment): the page's lead names v2.7.0 and the latency note is
  present. A grep of `docs/` and `.okf/` turns up 2.3.1 only in history
  (hermes.md, ADR 0029, a handoff, log.md). No page names 2.3.1 or 2.6.0 as
  current. Passes.
- The readiness observation: I read `null_resource.bifrost_ready` and
  `nomad_job.bifrost`. See f3.

## Findings

- f1: resolved. The operator re-signed r2 under grant g10 to record the
  no-dump choice. The page at `.okf/components/bifrost.md` (new
  version-history paragraph) now states that choice and the fact that neither
  2.3.1 nor 2.6.0 can be restored.
- f2: resolved. The spike paragraph now says the x509 result was "seen from
  the devcontainer rather than the cluster nodes", and that only Gemini was
  called live after the apply. The latency sentence no longer uses a
  semicolon. One semicolon is left before "after the apply Gemini answered".
  The slop rule treats that as low confidence, so I leave it to the author.
- f3: open, hardening, not blocking. The gate can see the old allocation
  because the bifrost job is not applied with `detach = false`. The fix is to
  add `detach = false` to `nomad_job.bifrost`, as `nomad_job.openviking`
  already has, or to have the gate check the version the gateway reports.
  Either fix also makes the gate's comment true. This was already broken
  before this ticket. No virtual key changed this round, so nothing was harmed
  here. It belongs in a follow-up ticket.

## Notes

The pin test's docstring names only the 2.3.1 to 2.6.0 migrations as one-way.
That is still true, but the pin is now 2.7.0, whose two one-way migrations it
does not mention. I am not asking for a change.

The minute of refused connections during the restart is what a
single-allocation job does on redeploy, and the plan accepts it. The only
problem is the gate reporting ready too early, which is f3.
