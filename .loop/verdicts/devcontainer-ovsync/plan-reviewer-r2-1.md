---
type: verdict
title: 'Verdict: devcontainer-ovsync plan-reviewer round 2'
description: 'plan-reviewer verdict for round 2 of devcontainer-ovsync: fail.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-28T09:25:35+00:00'
slug: devcontainer-ovsync
pass: plan-reviewer
round: 2
body_schema: verdict/1
---

## Summary

p1 is resolved: `--no-bind` skips the auto re-bind (ovx cli.py, `decided is
False` returns before `read_binding`). One new contract problem, p2: the plan
and r4 name an ovx profile `lab` that does not exist on the operator's host;
the real one is `localstack`. Revise the name; no split needed.

## Checked

- Risk 1 still settled by spike:devcontainer-ovsync/1 (no writes under a
  read-only ~/.openviking from ov 0.5.0 or ovsync v0.3.0; needs
  ovcli.settings.conf, which step 3 requires).
- `--no-bind` exists in the image's ovx (v0.4.0) and is honored by `_login`.
  A login without a TTY also skips binding.
- bound.json's target is the host path (/Users/jasperginn/.openviking/...),
  used only by `--unbind`; `bind` writes to ov_config_file(environ), so the
  host-side bind writes the mounted file. Directory mount is still correct.
- Dockerfile and devcontainer.json match the plan's "Today"; the
  `uv tool install ... --from git+...@ov-sync-v0.3.0#subdirectory=...` form
  matches the existing ovx line.
- No docs page covers the host mounts today, so step 3's "new how-to"
  branch applies; r4 targets docs/how-to and the skeleton test.

## Findings

- p1 (premise, resolved): in-container login is now `ovx -L --no-bind`, and
  refresh and bind happen on the host. ovx honors `--no-bind`.
- p2 (premise, blocking, r4): the plan and r4 use the ovx profile `lab`, but
  the operator's only profile is `localstack`. `ovx --bind lab` fails with
  "profile 'lab' not found", and r4 requires the literal `--bind lab`.
