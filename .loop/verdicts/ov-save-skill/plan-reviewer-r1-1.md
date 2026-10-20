---
type: verdict
title: 'Verdict: ov-save-skill plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of ov-save-skill: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-20T15:10:00+00:00'
slug: ov-save-skill
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

Fail on one finding, p1: the skill saves with an explicit `parent=`, and
OpenViking will not create a missing parent folder in that case. The plugin
also cannot pass `create_parent`. Saves into new folders fail. The fix is a
small change to the wrapper this ticket already edits, so this needs a
revision, not a rethink and not a split.

## Checked

- Voice/STT: settled. Spikes 1 and 3 show the base image has no engine and
  no config setting turns one on. Spike 8 shows the unpinned install breaks
  (PyAV 19). Spike 10 shows the uv.lock-pinned line from the plan
  transcribes, caches the model under /opt/data/.cache/huggingface and works
  offline after a restart, with peaks of 593/384 MB. The uv path in the RUN
  line exists in nousresearch/hermes-agent:v0.22.2 (aarch64). `just
  rebuild_hermes` builds only linux/arm64. The build runs as root and the
  venv is root-owned. The `stt.provider: local` and `stt.local.model` keys
  match tools/transcription_common.py and transcription_local.py.
  config.yaml is a template in hermes.hcl that setup.sh copies over on
  every start, so the keys reach the running instance. This is a hermes.hcl
  edit, even though the skill part says "No Terraform edit".
- `.map.md` dotfile: settled by spike 2 (USER token, create, replace and
  append all 200, exact read-back through both read paths, one VLM call per
  write, kept out of search in the default processing mode).
- Skill pickup: settled by spike 9 (8/8 sessions called `skill_view` first,
  5/5 asked with no place given, 3/3 saved without asking when a place was
  given). Spike 6's failure was the literal "?" check.
- Wrapper: on main now. Upstream `get_tool_schemas` returns `_TOOL_SCHEMAS`
  and `handle_tool_call` routes through `_TOOL_HANDLERS`, and
  agent/memory_manager.py builds `_tool_to_provider` from
  `get_tool_schemas()`. Overriding both in the subclass is therefore enough
  for `viking_write`, and `self._client.post` uses the same token and path
  as the other tools.
- Skills fileset ships any new `**/SKILL.md` on each deploy. The telegram
  toolsets include `files`, so the skill can write the local transcript
  file.

## Findings

- p1 (premise, blocking): an explicit `parent=` turns off auto-create in
  OpenViking v0.4.17.1 (resource_service.py sets `create_parent=True` only
  when neither `to` nor `parent` is given, and tree_builder.py raises
  "Parent URI does not exist"). Plugin 2.1.1's `_tool_add_resource` drops
  `create_parent` from the payload. A new root, a proposed subfolder, a new
  `blogs/<source>/` or `clips/<slug>/` therefore fails on its first save.
  Spike 9 used a stub server and never hit this. Revise the plan to have the
  wrapper send `create_parent: true` (with a stand-in client test), or use
  `to=`. Whether `to` creates missing parents is a spike question.

## Notes

The prior `plan-reviewer-r1.json` is a loopctl placeholder with no
findings, so there are no earlier ids to carry over.
