---
type: verdict
title: 'Verdict: ov-no-auto-capture plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of ov-no-auto-capture: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-20T14:27:03+00:00'
slug: ov-no-auto-capture
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

No open risk could break this plan. Spike 2 settles the one listed risk. It
ran in the real 0.22.2-1 image: the wrapper loads and activates, and the six
viking_* tools reach the model. Startup sends only `GET /health`. A plain
turn, `/new`, a built-in memory write and shutdown send nothing, and an
explicit viking_search reaches OpenViking. Spike 1 shows why the plan needs
the `_recover_pending_sessions` override, and the plan now includes it. I
checked the claims the spikes did not cover against the image source and
found nothing that breaks the plan.

## Checked

- Spikes 1 and 2: README outcome, stdout, stderr, run.json. Spike 1 exits 1
  only on the stale-session commit at init. Spike 2 adds the override,
  exits 0 and passes every check.
- Renaming `name` to `openviking_tools` was not in the spikes, which kept
  `name='openviking'`. In agent/memory_manager.py in the image, `provider.name`
  is used only for logs, the one-external-provider check, `get_provider`
  lookup and prefetch thread keys. Nothing outside the plugin compares it to
  the literal "openviking". The rename is safe.
- Dropping the `memory.openviking` recall block: `_tool_search` and the other
  tool handlers use the client's default `_TIMEOUT = 30.0`, not
  `recall_request_timeout_seconds`. So explicit searches, which take 3.5-7s,
  do not fall back to the 3s recall budget.
- `queue_prefetch` upstream is already a no-op, and `on_turn_start` only sets
  the sender peer. Overriding just `prefetch` covers recall.
- The upstream `initialize` sets `_writes_enabled` from `agent_context` and
  gates `sync_turn`, `on_session_end`, `on_session_switch` commits and
  `on_memory_write`. `_tool_remember` and `_tool_add_resource` do not check
  it, so the daily-blog-scrape and daily-reflect crons (both use
  viking_remember or viking_add_resource) keep working.
- daily-reflect reads `viking://user/jasper/memories` and runs searches. It
  does not read Hermes session uploads, so losing session commits gives it
  less input, as the plan says, and does not break it.
- The SOUL.md "Session Bootstrap" and "Auto-Capture Protocol" sections exist
  as named. `test_recall_fits_inside_hermes_prefetch_limit` exists and
  asserts the block being dropped, so removing it is in scope.

## Findings

None.

## Notes

Spike 2 drove AIAgent directly with platform=telegram. It did not use a live
gateway, and compression was not exercised. Compression goes through
`on_session_switch`, which the same `_writes_enabled` flag gates. The plan's
deploy outcome check (proxy stderr after a real Telegram turn and `/new`)
covers the gateway path, so this is no reason for another spike.
