---
type: verdict
title: 'Verdict: bifrost-decision-router reviewer round 2'
description: 'reviewer verdict for round 2 of bifrost-decision-router: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-11-16T08:39:13+00:00'
slug: bifrost-decision-router
pass: reviewer
round: 2
body_schema: verdict/1
---

## Summary

f1 is fixed. The smoke now counts `decisions` entries in
`extra_fields.routing_metadata.calls`. The router check fails when a router
chat makes none, and the Hermes check fails when a Hermes chat makes one. The
stub tests prove both directions. The fix broke nothing nearby. f2 was also
fixed, though it was not sent back.

## Checked

- `loopctl gate stamp` from the worktree: pre_commit pass, cli_tests pass,
  rows r1-r4 pass, "stamp green: 73b23952fdd4...f659".
- `uv run --directory cli pytest tests/test_bifrost_router.py -q`: 9 passed.
- Response shape: spike 1 stdout shows `extra_fields.routing_metadata.calls[]`
  with `request_type: "decisions"` and `routing_info.model` side by side. That
  matches `chat_extra` and `classifier_calls`.
- Vacuity: the Hermes "no call" check could pass if the path were wrong. But
  the router check in the same run requires a non-zero count on that same path,
  so a wrong path fails the smoke instead of passing it.
- Stub tests: the router parametrization covers routed, not-routed and no
  classifier call. The Hermes one covers kept, rerouted and classifier-called.
  Each failing case expects SmokeFailure, so a check that dropped the
  call-count assertion would fail the test.
- ADR 0029 line 63-65 now says the key-refuses claim is not measured.
- `_assert_no_cloud_suffix` scans the decision model, every rule target,
  every provider key's `models`, and every `bifrost_virtual_key` block's
  `allowed_models`, with a floor of more than 10 names.

## Findings

- f1: resolved in `assert_router_routes_by_tier` and
  `assert_hermes_not_rerouted` (scripts/bifrost_smoke.py), with the
  `test_smoke_router_check` and `test_smoke_hermes_check` parametrizations.
- f2: resolved in `_assert_no_cloud_suffix`, called from `test_router_key`.

## Notes

If Bifrost ever sends `"routing_metadata": null`, `classifier_calls` raises
AttributeError instead of SmokeFailure. The smoke still exits non-zero with a
traceback rather than passing, and no spike showed a null, so this asks for
nothing.
