---
type: verdict
title: 'Verdict: hermes-update plan-reviewer round 1'
description: 'plan-reviewer verdict for round 1 of hermes-update: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-20T08:54:59+00:00'
slug: hermes-update
pass: plan-reviewer
round: 1
body_schema: verdict/1
---

## Summary

No open risk could break this plan. The two risks it lists are settled by spikes whose evidence answers them. The provider choice (copy the pinned catalog plugin in at build time) is the route spike 3 proved, after it ruled out the pip/uv route. I found no unlisted risk that would force a rethink.

## Checked

- Risk 1, the OpenViking provider: spike 2 (exit 0, FAIL=0) shows the v0.22.2 gateway lazy-installing catalog plugin 2.1.1 onto the volume, keeping it offline, and sending `viking_search` to the 1934 sidecar with the placeholder key, with no `openviking-server` started. Spike 3 (exit 0) shows `uv pip install` fails to build, and that a copy of `examples/hermes-plugin` at 9f150ece into `/opt/hermes/plugins/memory/openviking` resolves through `find_provider_dir` and serves `viking_search` on a fresh volume with no route off the host and no runtime install. This is the path the plan takes. The account `lab` gap is the same on 0.21 and 0.22: the plugin sends no account header, and `ov_auth_proxy.py` drops caller credentials and sets the bearer token itself, so the account comes from the token as it does today. The plan's Outcome checks this live.
- Risk 2, the Bifrost provider: spike 1 (exit 0) loads the plugin, copied byte for byte from `hermes.hcl`, under Python 3.14.7, resolves it, and routes `POST /v1/chat/completions` to a stub.
- Repo claims: the Dockerfile (`deployments/applications/services/hermes/Dockerfile`) adds only apt packages and a comment that says the provider ships in the base image, which the plan updates. `hermes_version = "0.21.0-1"` is in `services.tf`. `rebuild_hermes` reads it and builds the image. `hermes.hcl` selects the provider through `memory.provider: "openviking"`, mounts nothing over `/opt/hermes/plugins`, and lists `cronjob` in `platform_toolsets`, a name the plan says still works. `register-cron.sh` holds the four jobs the Outcome names. The live volume has no `plugins/openviking` at 0.21, so on first start it looks like the fresh volume spike 3 tested.

## Findings

None.

## Notes

The things left to building do not threaten the approach: the exact `sessions.auto_prune` key, the `config` prestart task's `/tmp/setup.sh` running under the new base's entrypoint, chromium on the new base OS, and how the Dockerfile fetches the pinned subdirectory (a BuildKit git `ADD` or a fetch in `RUN`). A failure in any of them shows up in the build or the first deployment, and the fix is local.
