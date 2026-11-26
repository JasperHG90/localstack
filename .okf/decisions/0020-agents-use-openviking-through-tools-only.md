---
type: decision
title: "ADR 0020: Agents use OpenViking through tools only"
description: "Hermes and Claude Code read and write OpenViking only when the user or a skill asks, through tools, over automatic recall and capture on every turn."
tags: [adr, decision, hermes, openviking, memory, claude-code]
generated:
  by: process:kmctl/0.12.1
  at: 2026-10-20T14:31:56Z
status: stable
sources:
  - resource: "deployments/applications/services/hermes/openviking_tools/__init__.py"
  - resource: "deployments/applications/services/hermes.hcl"
  - resource: "deployments/applications/services/hermes/SOUL.md"
  - resource: "docs/how-to/connect-claude-code-to-openviking.md"
---

# ADR 0020: Agents use OpenViking through tools only

## Context

Hermes and Claude Code both talked to OpenViking on every turn without being
asked. In Hermes, the catalog plugin that
[ADR 0019](/decisions/0019-hermes-openviking-plugin-built-into-the-image.md)
builds into the image ran a recall search and a profile read before each turn,
uploaded each turn to an OpenViking session, committed that session at session
end, `/new` and compression, and mirrored built-in `memory` writes. `SOUL.md`
added the same habits as instructions: a search and a browse on each
conversation's first message, and a `viking_remember` after each substantive
reply. On laptops, Claude Code's OpenViking memory plugin hooked the session
for recall and capture in the same way. Neither Hermes v0.22.2 nor plugin
2.1.1 has a setting that turns the hooks off. The operator wants OpenViking
read and written only when they, or a skill they run, ask for it.

## Decision

Both agents reach OpenViking through tools only.

Hermes selects `memory.provider: "openviking_tools"`, a small provider in
`deployments/applications/services/hermes/openviking_tools/` that subclasses
the upstream one. It starts upstream's `initialize` in the writes-off mode
upstream uses for cron, subagent and flush contexts, skips the recovery of
leftover sessions that `initialize` runs whatever that mode says
(spike:ov-no-auto-capture/1), returns no recall from `prefetch`, and gives a
static system prompt block. The six `viking_*` tools and their handlers stay
upstream's, so a user or a skill such as the `daily-blog-scrape` cron still
calls them (spike:ov-no-auto-capture/2). `SOUL.md` drops its Session
Bootstrap and Auto-Capture Protocol sections.

Claude Code loses its memory plugin. The how-to
`docs/how-to/connect-claude-code-to-openviking.md` now removes it and points
to the CLI for calls on request.

Rejected: keeping automatic recall and capture with a tighter budget, as the
recall-timeout tuning before this tried. It still puts OpenViking calls on
every turn and writes every session, which is what the operator does not
want. Also rejected: patching the upstream plugin in the image. A subclass
keeps upstream's code byte for byte, so a plugin bump changes only the pinned
commit, and the wrapper's few overrides are the whole difference.

## Consequences

- Fewer memories reach OpenViking: sessions are no longer extracted into
  memories. The `daily-reflect` and `weekly-digest` jobs reflect over less.
- The wrapper overrides private upstream methods (`_recover_pending_sessions`)
  and relies on the writes-off gate. A plugin bump must re-check both.
  `cli/tests/test_hermes_openviking_tools.py` holds the wrapper's side
  against a stand-in for upstream.
- Removing the Claude Code plugin is a step each user runs on their own
  machine. The repository cannot check it.

## Correction, 2026-11-24

The six upstream tools and the wrapper's few overrides are no longer the
whole difference. In the change
[ADR 0023](/decisions/0023-hermes-saves-from-a-skill-owned-map-of-roots.md)
records (commit `f19d5ef`), the wrapper in
`deployments/applications/services/hermes/openviking_tools/__init__.py`
gained two additions. A seventh tool, `viking_write`, writes text to an exact
URI, which the six cannot. And `_add_create_parent` patches the plugin's
client so that a `viking_add_resource` that names a parent sends
`create_parent: true`, which plugin 2.1.1 never sends. Upstream's six tools
and their handlers are still upstream's.
