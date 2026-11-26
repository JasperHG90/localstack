---
type: verdict
title: 'Verdict: hermes-file-toolset plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of hermes-file-toolset: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-26T13:54:08+00:00'
slug: hermes-file-toolset
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

Round 1. No open risk could break this plan. The premise, the target name,
the warning string and the platform scope all check out against upstream
hermes-agent at v0.22.2 and v0.23.4.

## Checked

- `toolsets.py` defines `file` (read_file, write_file, patch, search_files)
  at both tags. `files` is neither a toolset nor a key of
  `_LEGACY_TOOLSET_MAP` in `model_tools.py` (only `file_tools` is), so the
  entry resolves to nothing today. No other listed toolset (terminal, web,
  browser, memory, skills, cronjob) carries file tools, so Telegram and email
  really run without them.
- The other six names in both lists exist at both tags, so after the rename
  every entry is valid and the new test passes on the fixed config.
- `hermes_cli/toolset_validation.py` emits
  "platform '<p>' references unknown toolset '<name>'", the string the
  outcome checks for. `hermes_cli/toolset_scope.py` restricts only the
  discord toolsets, so `file` is allowed on telegram and email.
- The Telegram check has a data volume to read from
  (`hermes_data_volume` in hermes.hcl).
- The 2.0 facts match the prose: one cause (P1), one behaviour outcome that
  ships alone, `needs: none` is right, and `touches` names the two files the
  prose changes.

## Findings

None.

## Notes

`hermes-update-0-23` also touches `cli/tests/test_hermes_version.py`; that
is merge order, not a risk. The gate runs offline, so the test must hold the
known names as a list in the test file. That is a build detail.
