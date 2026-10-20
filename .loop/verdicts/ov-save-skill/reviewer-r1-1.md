---
type: verdict
title: 'Verdict: ov-save-skill reviewer round 1'
description: 'reviewer verdict for round 1 of ov-save-skill: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T16:36:31+00:00'
slug: ov-save-skill
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The change does what the plan asks. The skill, SOUL line, `viking_write`,
`create_parent` patch, faster-whisper bake-in, stt config, version bump,
how-to, ADR and component notes are all in place, and the gates are green.
The three findings are small. One is a newline in the skill's append
instruction that could glue a new root onto the last seed line. The other
two are docs fixes: an ADR number shared with ov-carry-over, and a how-to
step that saves the same link twice. None needs another review round.

## Checked

- `loopctl gate stamp` from the worktree: pre_commit pass, cli_tests pass,
  r1 to r5 pass, "stamp green:
  b9398eff477577f5ce47a53202e90542c362bca85c9b59cde0e6493773245b7a".
- I read the wrapper against upstream plugin 2.1.1 source in the
  scratchpad (hermes-src). Upstream `handle_tool_call` dispatches via
  `getattr(self, "_tool_" + ...)`, so the `_tool_add_resource` override
  is used. Upstream calls
  `self._client.post("/api/v1/resources", payload)` positionally, so the
  patched `post` sees the payload. The patch only matches the exact
  `/api/v1/resources` path with a truthy `parent`. `upload_temp_file` goes
  through `_httpx` directly, not `post`, and other endpoints pass through
  unchanged. The `_create_parent_added` attribute stops a second wrap on
  the same client, and a rebuilt client gets patched on its next save.
  `_VikingClient` has no `__slots__`. Hermes' memory manager routes by the
  names from `get_tool_schemas()`, so `viking_write` reaches the wrapper's
  `handle_tool_call`.
- `viking_write` sends `{uri, content, mode}` with no `processing_mode`,
  so it uses the default mode as spike 2 requires, not `vectors_only`. It
  validates input before sending and wraps errors with `tool_error`.
- The Dockerfile RUN line matches spike 10's
  `files/spike.sh` line 28 byte for byte, after `$U` is expanded. It runs
  as root, since `USER root` comes earlier and nothing resets it.
  `stt.provider: local` written explicitly in config.yaml goes through
  `_resolve_explicit_provider("local")`, and `stt.local.model` is read at
  transcription_tools.py:597.
- Eval rows. r1/r2: `test_hermes_save_skill.py` asserts each listed
  instruction: front matter, map read before `viking_add_resource`, the
  ask/wait phrases, append via `viking_write`, exactly one `viking_browse`
  list and no `tree`, four seed roots, no curl or `content/write`, and
  folder refs limited to the seed roots. r3: the four `-k viking_write`
  tests cover the schema enum, the exact payload, five bad inputs that
  send nothing, and the six upstream tools passing through.
  r4: two calls per case cover parent on a URL and on a local path, and
  no flag without parent, with empty parent or with `to`. A separate test
  covers a client rebuild. r5: pins the exact RUN line, the version and
  both stt keys.
- r6 (judgment, live): the how-to produces evidence for each part. Step 1
  is a save with a named place, with no question asked, and it seeds the
  map. Step 2 is a save with no place, where Hermes proposes and asks.
  Step 3 adds a new root with a description. Step 4 saves a voice-note
  transcript as a dated .md. Step 5 reads `.map.md` from the shell,
  which shows the seed roots and the new `notes/` line. Whether Hermes read
  the map in step 2 is visible only in tool progress or logs, not in the
  reply, so the recorded evidence should come from the gateway log.
- Consistency: ADR 0019 gets a dated Correction section, the form
  okf-bundle.md allows. components/hermes.md, the summary ack, log, docs
  indexes and SOUL tool table agree with the code. The blog-scraper skill
  is untouched. `/opt/data/tmp` is not on Hermes's read denylist,
  `write_file` creates parent directories, and the terminal backend is
  local, so the uploaded path exists.

## Findings

- f1: the append newline. Not blocking, because the fix is a one-line
  instruction change.
- f2: the ADR 0022 clash with ov-carry-over. It is a merge-order chore.
  `kmctl check` should catch any link left broken.
- f3: the how-to step 2 duplicate save.

## Notes

`test_names_no_folder_beyond_the_seed_roots` only sees backticked or
`viking://` paths, so a leaf named in plain prose would slip past it. The
"blogs/anthropic" example in step 3 is one such case, and as an example
it is fine.
