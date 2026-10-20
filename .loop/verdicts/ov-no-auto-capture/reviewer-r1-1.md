---
type: verdict
title: 'Verdict: ov-no-auto-capture reviewer round 1'
description: 'reviewer verdict for round 1 of ov-no-auto-capture: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T14:48:09+00:00'
slug: ov-no-auto-capture
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The change does what the plan says. Hermes selects an `openviking_tools`
provider that subclasses the upstream plugin with writes forced off, startup
session recovery skipped, empty `prefetch` and a static prompt block. SOUL.md
loses its Session Bootstrap and Auto-Capture sections. The Claude Code how-to
now removes the memory plugin. The tag moves to 0.22.2-2. The gates are green
and the tests fail when the behavior breaks. Row r7 can't run yet: it is a
post-deploy check.

## Checked

- Gates rerun from the worktree: `just pre_commit` passed every hook, and
  `uv run --directory cli pytest` passed (666 passed, 21 deselected).
  `loopctl gate stamp` result: pass on gates pre_commit and cli_tests and on
  rows r1 to r6, "stamp green:
  1d1a3253c8f4df3369d95201d0359b6f7a82251ab7d927bed63e6d1086a44126". The
  gates left no unstaged changes in the tree.
- Upstream source: I pulled plugin 2.1.1 and `agent/memory_manager.py` from
  the local `ghcr.io/jasperhg90/hermes:0.22.2-1` image and checked the
  wrapper against them. `_NON_PRIMARY_AGENT_CONTEXTS` includes `flush`, and
  `_agent_context` affects only `_writes_enabled`. That flag gates
  `sync_turn`, `on_session_end`, every commit path in `on_session_switch`,
  `on_memory_write`, and the atexit safety net (which calls
  `on_session_end`). `queue_prefetch` is already a no-op upstream. Both calls
  to `_recover_pending_sessions` (in `initialize` and in the runtime
  re-attach path) hit the no-op override. Upstream defines no
  `on_pre_compress`. The tool handlers ignore the flag, so the
  `daily-blog-scrape` cron still reaches `viking_add_resource`.
- The `name` override was added after spike 2, which showed
  name='openviking'. In Hermes 0.22.2, a memory provider's `name` is used
  only for logs, the one-external-provider collision check, the unused
  `get_provider`, and telemetry. Upstream never reads `self.name`.
  Overriding it is safe.
- Rows r1 to r6: I read each test against its `fails_when`. To check that
  the tests can fail, I copied the wrapper into the scratchpad and broke it
  four ways, then ran the test file against each copy:
  - without the `initialize` override, r1 fails ([primary]);
  - without the `_recover_pending_sessions` override, r2 fails;
  - without the `prefetch` override, r1 fails;
  - without the `system_prompt_block` override, r1 and the prompt test fail.

  r3 compares schemas to the stand-in's upstream list and checks that a
  `viking_search` request reaches the client. r4 pins the provider line,
  checks that no `openviking:` or `recall_` keys remain, that the one COPY
  line is right and that the tag is 0.22.2-2. r5 checks the SOUL.md
  headings. r6 runs the skeleton check over every how-to plus a new test
  for the page: no install.sh, the uninstall commands present, a Check
  step, and a link to the CLI page.
- r7 (judgment, not yet runnable, post-deploy): the plan can produce the
  evidence. `ov_auth_proxy.py` logs each request line to stderr
  (`log_message`), so after the deploy `nomad alloc logs -stderr -task
  ov-auth-proxy` over a plain Telegram turn followed by `/new` should show
  only the `GET /health` from startup. Then an explicit "search OpenViking
  for X" should show one `POST /api/v1/search/find`. `hermes memory status`
  should name `openviking_tools`. Spike 2 already showed this in the real
  0.22.2-1 image with a stub upstream.
- Consistency: hermes.md, ADR 0020, log.md, the summary ack, the docs
  indexes and the CLI how-to back-link all agree with the code. No doc
  page, okf concept or summary still describes recall budgets, the memory
  plugin install, or the SOUL bootstrap and capture habits. The how-to
  passes the skeleton test.

## Findings

None.

## Notes

- r7 needs the operator. The plan says the agent's Nomad token gets 403 on
  `nomad alloc logs` for `ov-auth-proxy`, and I see no recorded pre-deploy
  baseline. Neither stops the judgment: r7's fails_when is about requests
  seen after the deploy, so no baseline is needed. But someone with log
  access has to read the proxy stderr in a quiet window. A cron run
  (`daily-blog-scrape` at 08:00) or the dashboard could add request lines
  that are not from the chat turn under test.
- I could not run `kmctl check`: no `kmctl` binary in this environment.
- The new test pins exactly one `COPY` line in the Dockerfile. A future
  COPY will need that test updated. That is a deliberate tight pin, not a
  defect.
