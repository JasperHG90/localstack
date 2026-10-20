---
type: eval
title: 'Eval: ov-save-skill'
description: 'Definition of done for ov-save-skill: 6 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T16:10:15+00:00'
slug: ov-save-skill
signoff:
  signer: delegated:jasperginn@gmail.com/claude-opus/5.5
  hash: 0781278fe9850de90d398d7a95568f8ebdf061b5ab0b946f28c329f31282ef6b
  at: '2026-10-20T16:10:15+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: The save-to-openviking skill loads (front matter), reads .map.md before saving, asks when no place was given and saves nothing before the answer, appends a new root to the map, falls back to exactly one list of the resources root, seeds the four roots, writes the map only with viking_write, and holds no hardcoded leaf folders beyond the seed.
  Fails when: any of those instructions is missing or contradicted in the skill.
- r2: SOUL.md points at the save-to-openviking skill for any save and lists viking_write in its tool table, and still forbids shelling out to curl.
  Fails when: SOUL.md lacks the pointer or the viking_write row, or drops the curl rule.
- r3: The openviking_tools wrapper exposes viking_write with create, replace and append; a call posts content/write with uri, content and mode; a bad mode or missing uri errors without a request; the upstream six still pass through.
  Fails when: viking_write is missing from the schemas, sends a different request, sends on bad input, or an upstream tool stops passing through.
- r4: viking_add_resource with a parent reaches OpenViking with create_parent: true; without a parent it does not.
  Fails when: a parent-bearing call lacks create_parent: true, or a call without parent carries it.
- r5: The image bakes faster-whisper 1.2.1 pinned to Hermes's uv.lock, config pins stt.provider local and stt.local.model base, and hermes_version is 0.22.2-3.
  Fails when: the Dockerfile line is missing or unpinned, either stt key differs, or the version pin is not 0.22.2-3.
- r6 (judgment): Live after deploy on Telegram: 'save this <url>' with no place makes Hermes read the map, propose a folder and ask before writing; 'save this to <folder>' writes there without asking; a voice note plus 'save the transcript' lands as a Markdown file in the confirmed folder; a new root the operator names appears in .map.md with its description.
  Fails when: the recorded post-deploy evidence shows any of these failing.
