---
type: eval
title: 'Eval: ov-no-auto-capture'
description: 'Definition of done for ov-no-auto-capture: 7 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T14:27:37+00:00'
slug: ov-no-auto-capture
signoff:
  signer: delegated:jasperginn@gmail.com/claude-opus/5.5
  hash: 1dfdc65fc6be397ef30b01710ca8e9dc96f108e47a3d70fa1a2f5697a0de97e5
  at: '2026-10-20T14:27:37+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: The openviking_tools provider sends nothing to OpenViking on its own: prefetch returns empty, and sync_turn, on_session_end, on_session_switch and on_memory_write reach no client.
  Fails when: prefetch returns any text, or any of those hooks makes a request through the client.
- r2: Startup recovers and commits no leftover session.
  Fails when: initialize, with a stale pending-session marker present, makes a commit or any session request.
- r3: The six viking_* tools keep upstream's schemas and their calls reach OpenViking.
  Fails when: the tool schemas differ from upstream's, or a viking_search call does not reach the client.
- r4: Hermes's config selects memory.provider openviking_tools with no recall block, the image copies the wrapper beside the upstream plugin, and hermes_version is 0.22.2-2.
  Fails when: the config names another provider or still carries memory.openviking recall settings, the Dockerfile does not copy the wrapper to /opt/hermes/plugins/memory/openviking_tools, or the version pin differs.
- r5: SOUL.md no longer tells Hermes to search OpenViking at conversation start or to save memories after replies.
  Fails when: SOUL.md still has a Session Bootstrap section or an Auto-Capture Protocol section.
- r6: The Claude Code how-to removes the auto-capture memory plugin and points to explicit CLI use, in the how-to skeleton.
  Fails when: the page still tells readers to install the memory plugin, lacks the uninstall and check steps, or breaks the how-to skeleton.
- r7 (judgment): Live after deploy: a plain Hermes chat turn and /new send no search, session or commit request to OpenViking, while an explicit viking_search still answers.
  Fails when: the recorded proxy or OpenViking request evidence after deploy shows a search/sessions/commit request from a plain turn or /new, or the explicit search fails.
