---
type: plan
title: 'Plan: ov-no-auto-capture'
description: Stop Hermes and Claude Code from recalling from and capturing into OpenViking on their own, so OpenViking is read and written only when the user or a skill asks.
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T13:54:50+00:00'
slug: ov-no-auto-capture
epic: ov-reset
depends_on: []
priority: 1
---

# ov-no-auto-capture

<!-- This template was registered in planning. To capture an idea as a stub
instead (intent for later, promoted by the operator), write the plan with
`status: draft` in its front matter before running loopctl ticket register.
A hand-written plan's front matter needs type: plan, title, description and
slug; loopctl ticket register fills in generated. Optional: epic, depends_on,
priority, status, strictness and blocking. -->

Relayed from: none
<!-- When this ticket carries a finding raised while building another ticket,
replace "none" with that ticket's slug and the finding, in one line (ADR 0001). -->

## Intent

Hermes and Claude Code both talk to OpenViking on every turn without being
asked. The operator wants OpenViking read and written only when they, or a
skill they run, ask for it ("Tools only" for Hermes).

**Hermes today.** `memory.provider: "openviking"` in
`deployments/applications/services/hermes.hcl` selects catalog plugin 2.1.1,
which the image copies into `/opt/hermes/plugins/memory/openviking`
(`deployments/applications/services/hermes/Dockerfile`, ADR 0019). On every
turn its hooks run a recall search and a session-start profile read
(`prefetch`), upload the turn to an OpenViking session (`sync_turn`),
commit that session at session end, `/new` and compression (`on_session_end`,
`on_session_switch`), and mirror built-in `memory` tool writes
(`on_memory_write`). Neither Hermes v0.22.2 nor the plugin has a setting
that turns these off. The plugin reads only `recall_*`,
`commit_token_threshold`, `profile_token_budget` and similar keys.

The plugin already has a writes-off mode. It clears `_writes_enabled` for
cron, subagent and flush contexts, and that one flag gates `sync_turn`,
`on_session_end`, the commit in `on_session_switch`, and `on_memory_write`.
The tool handlers (`viking_search`, `viking_read`, `viking_browse`,
`viking_remember`, `viking_forget`, `viking_add_resource`) ignore it. That
is the path the 08:00 `daily-blog-scrape` cron uses today to call
`viking_add_resource`. Hermes takes provider tools from `get_tool_schemas()`
at registration (hermes-agent's agent/memory_manager.py, `add_provider` and
`inject_memory_provider_tools`), apart from prefetch and sync, behind the
`memory` toolset that `platform_toolsets` already enables.

**Hermes change.** A small memory provider `openviking_tools` that
subclasses the upstream `OpenVikingMemoryProvider`:

- source in
  `new:deployments/applications/services/hermes/openviking_tools/__init__.py`
  and `new:deployments/applications/services/hermes/openviking_tools/plugin.yaml`;
- the Dockerfile copies it to `/opt/hermes/plugins/memory/openviking_tools`
  beside the upstream copy;
- it imports the upstream class as `plugins.memory.openviking`, the module
  name Hermes gives a bundled provider;
- it defines `register(ctx)`. Without it, Hermes's fallback scan of the
  module's attributes would find the imported upstream class first and
  build that instead.

It runs the upstream `initialize` with writes forced off and overrides
`_recover_pending_sessions` as a no-op: upstream `initialize` calls it
without checking `_writes_enabled`, so forcing writes off alone still
commits a stale pending session at start (spike:ov-no-auto-capture/1). It
overrides `name` to `openviking_tools` so logs name the provider that runs. It returns no recall from
`prefetch`. It replaces `system_prompt_block` with a static block that lists
the six tools and says to use them when the user or a skill asks. The
upstream block makes an `fs/ls` call each time and tells the model to search
before asking the user. Tool schemas and `handle_tool_call` stay upstream's.

`config.yaml` sets `memory.provider: "openviking_tools"` and drops the
`memory.openviking` recall block, which is moot without recall.

`deployments/applications/services/hermes/SOUL.md` drops its "Session
Bootstrap" section (a `viking_search` and `viking_browse` on every
conversation's first message) and its "Auto-Capture Protocol" (a
`viking_remember` after every substantive reply). Those make the model do by
itself what the hooks did. The tool table and the citation rules stay.

`hermes_version` in `deployments/applications/services.tf` moves to
`0.22.2-2` for the rebuilt image (`just rebuild_hermes`).

**Tests.** `cli/tests/test_hermes_version.py` loses
`test_recall_fits_inside_hermes_prefetch_limit` and pins the new provider
name, the copy into the image and the new tag. A new
`new:cli/tests/test_hermes_openviking_tools.py` imports the wrapper with a
stand-in for the upstream module, which is not in the repo and is fetched
at build time. It checks that `prefetch` returns empty, `sync_turn`,
`on_session_end`, `on_session_switch` and `on_memory_write` reach no client,
and tool schemas and calls pass through. Neither SOUL section comes back.

**Claude Code.** `docs/how-to/connect-claude-code-to-openviking.md` is
rewritten to the skeleton in `.claude/rules/how-to-skeleton.md`:

1. remove the memory plugin (`claude plugin list` to find it, then
   `claude plugin uninstall openviking-memory@openviking` and
   `claude plugin marketplace remove openviking`, as the pinned installer
   prints);
2. check that it is gone;
3. use OpenViking on request through
   `docs/how-to/call-openviking-from-the-cli.md`.

The user does the uninstall on their own machines. `kmctl check --fix`
regenerates `docs/how-to/README.md`.

**Knowledge.** A `kmctl new decision` record chooses tools only over
automatic recall and capture, for both agents. `.okf/components/hermes.md`
replaces its recall-budget trap with the wrapper. `.okf/summary.md` is
updated or acked.

**Side effect.** Fewer memories reach OpenViking without hook-extracted
session memories. `daily-reflect` and `weekly-digest` reflect over less.

**Baseline.** Not measured. My Nomad token gets 403 on
`nomad alloc logs` for the `ov-auth-proxy` task. `ov_auth_proxy.py` logs
one stderr line per request, so the implementer records a plain Telegram
turn's request lines before the deploy as the baseline.

**Outcome.** After the deploy, the `ov-auth-proxy` stderr shows no request
to `/api/v1/search`, `/api/v1/sessions` or a session commit for a plain chat
turn followed by `/new`, and `hermes memory status` names
`openviking_tools`. In the same session, asking Hermes to search OpenViking
logs a search request through 127.0.0.1:1934 and returns account `lab`
results. `just pre_commit` and `uv run --directory cli pytest` pass.

## Could invalidate this plan

- The wrapper may not work in the real image: the gateway might not load a
  second bundled provider importing `plugins.memory.openviking`, it might
  hide the `viking_*` tools, or a plain turn might still search or commit.
  Settled by spike:ov-no-auto-capture/2: in the 0.22.2-1 image the wrapper
  (with the `_recover_pending_sessions` override) loads and activates with
  all six tools; startup sends only `GET /health`; a plain turn, `/new`, a
  built-in memory write and shutdown send nothing; an explicit
  `viking_search` reaches OpenViking. Without that override it commits a
  stale session at start (spike:ov-no-auto-capture/1).
