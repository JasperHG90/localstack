---
type: verdict
title: 'Verdict: ov-save-skill plan-reviewer round 2'
description: 'plan-reviewer verdict for round 2 of ov-save-skill: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-20T15:21:53+00:00'
slug: ov-save-skill
pass: plan-reviewer
round: 2
body_schema: verdict/1
---

## Summary

Pass. p1 is resolved and I found no other risk that could break the plan.

## Checked

- p1: spike 11 (exit 0, v0.4.17.1-9, lab/jasper USER token, the plugin's
  temp_upload path) answers the risk directly. Missing nested parent without
  the flag: 404, "Parent URI does not exist" in the server log. With
  `create_parent: true`: 200, both levels created, file findable. Repeat
  into an existing folder with the flag: 200, earlier entries kept. The
  server rejects unknown fields (400), so the exact field name matters, and
  the spike used the exact name the plan names.
- The fix fits the wrapper. Upstream `_tool_add_resource` builds its
  payload from a fixed key list and posts it through
  `self._client.post("/api/v1/resources", payload)`, so the wrapper has to
  either override that handler or add the field at the client post for
  that path. Either works in a subclass. That is a build detail, not a plan
  risk.
- The spike did not try the remote-URL `path=` form. `create_parent` is a
  request-level field that the resource service reads apart from the
  source kind, so I do not expect a difference. The live outcome check
  ("save this <url>") will show it if there is one.
- Wrapper (`deployments/applications/services/hermes/openviking_tools/__init__.py`)
  and its test file are on main now. The current pin is `0.22.2-2` in both
  `services.tf` and `cli/tests/test_hermes_version.py`, so the bump to
  `0.22.2-3` is consistent.
- Round-1 note on "No Terraform edit": that sentence now covers only how
  the skill file ships (the existing fileset), which is accurate. The plan
  states the `hermes_version` bump in `services.tf` and the image rebuild
  outright. The `stt` keys go into the config.yaml template inside
  `hermes.hcl` (a jobspec, re-registered on deploy), and the plan names
  config.yaml without naming that file. An implementer will find it from
  the grep, so the wording does not change what gets built.
- Earlier risks (voice bake-in, `.map.md` dotfile, skill pickup) stay
  settled by spikes 10, 2 and 9 as in round 1.

## Findings

- p1 (premise, resolved): the wrapper now sends `create_parent: true`
  whenever `parent` is set, tested against a stand-in client and settled by
  spike:ov-save-skill/11.
