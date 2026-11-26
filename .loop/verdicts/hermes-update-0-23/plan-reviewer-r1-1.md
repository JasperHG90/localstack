---
type: verdict
title: 'Verdict: hermes-update-0-23 plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of hermes-update-0-23: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-11-26T13:54:25+00:00'
slug: hermes-update-0-23
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

No open risk could break this plan. The three listed risks are settled by
spikes whose evidence answers them. The plan's claims about the v0.23.4 image
hold when checked against the image itself.

## Checked

- Voice notes (spike 2): the evidence answers the risk. The RUN line with
  `uv-0.13.5-linux-arm64` built on v0.23.4 arm64. All 12 packages came in as
  arm64 cp314 wheels, and the gateway's own voice path transcribed an opus
  clip with `local`/`base` in a 2 GB cgroup. The yanked av 18.1.0 comes from
  upstream's lock. Mono Telegram opus decoded fine, so it stays a watch item.
- Memory plugin (spike 3): the image used the Dockerfile's own plugin RUN and
  COPY, and the config was rendered from `hermes.hcl`. The gateway registered
  and activated `openviking_tools`, and `viking_search` reached the stub at
  127.0.0.1:1934. Settled.
- Bifrost provider (spike 1): the plugin, copied byte for byte, resolved as
  `bifrost` and sent a chat completion to the stub. Spike 3's turn also ran
  through `provider=bifrost`. Settled.
- `/opt/hermes/tools/` in v0.23.4 holds `uv-0.13.5-linux-arm64`, and the
  0.12.3 path is gone. The Dockerfile and `cli/tests/test_hermes_version.py`
  (`UV`, `WHISPER_RUN`, base and tag pins) both hard-code the old path. The
  plan names both.
- The base has no `jq`, and it ships `tools/chromium-1248/chrome-linux-arm64/chrome`.
  Dropping apt `chromium` and keeping `jq` matches the image.
- `browser_navigate` appears in v0.23.4 only in a migration note. The
  `browser` toolset is now every `browser_*` core tool, and `browser_exec` is
  among them. The toolset name in `platform_toolsets` still resolves.
- `hermes_agent/compat/moves.py` maps `agent.message_content` to
  `session_rules.turns`, as the plan says.
- The only removed tool names in the repo are at `medium-reader/SKILL.md:90`.
  `blog-scraper` and `SOUL.md` only use general wording. The plan covers all
  three.
- 2.0 facts: O2 needs O1 because `browser_exec` does not exist on v0.22.2, so
  O2 cannot ship alone, which makes `support` the right kind. The touches
  cover every file the prose changes, and each problem has a single cause.

## Findings

None.

## Notes

- No spike ran the browser path: does the bundled chromium start under s6 as
  the hermes user in the radxa podman task, and does `browser_exec` read a
  Medium page there? If it fails, the plan gets revised (browser config or
  launcher flags), not rethought. O2's check, one medium-reader run on the new
  image, catches it. The `daily-blog-scrape` cron (`register-cron.sh:36`) also
  uses the browser through `blog-scraper`, so look at its first run after the
  apply.
- The rollback plan, a `state.db` copy before the apply, covers the unchecked
  schema 31 to 33 downgrade.
