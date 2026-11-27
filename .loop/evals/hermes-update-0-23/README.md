---
type: eval
title: 'Eval: hermes-update-0-23'
description: 'Definition of done for hermes-update-0-23: 5 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-27T12:28:28+00:00'
slug: hermes-update-0-23
signoff:
  signer: delegated:jasperginn@gmail.com/claude
  hash: a4b778ee87117e0182d5ea8aa334a779a7cd9ce1deae0d366d0f4da83a3f314d
  at: '2026-11-27T12:28:28+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: The hermes Dockerfile builds FROM nousresearch/hermes-agent:v0.23.4, runs the faster-whisper install with /opt/hermes/tools/uv-0.13.5-linux-arm64/uv, still copies the OpenViking plugin 2.1.1 at pin 9f150ece and the openviking_tools wrapper, installs jq but not chromium, and hermes_version in deployments/applications/services.tf is 0.23.4-1.
  Fails when: the base is any other tag, the uv path names another version, the plugin pin or wrapper copy changes, chromium is still installed or jq is not, or the tag is not 0.23.4-1
- r2: No skill or SOUL.md under deployments/applications/services/hermes names a browser tool v0.23.0 removed (browser_navigate, browser_snapshot, browser_click and the rest of the old browser_* set), and medium-reader browses with browser_exec.
  Fails when: any removed browser_* tool name appears under deployments/applications/services/hermes, or medium-reader does not name browser_exec
- r3 (judgment): .okf/components/hermes.md records that the operator chose no state.db copy before the apply (2026-11-27), and that v0.23.3 moved state.db from schema 31 to 33, so a rollback to 0.22.2-3 has no restore point.
  Fails when: the page claims a state.db copy or rollback path that does not exist, or omits that there is none
- r4 (judgment): After the apply, the hermes job's new deployment is healthy on ghcr.io/jasperhg90/hermes:0.23.4-1; the gateway log shows openviking_tools loaded; a viking_search through 127.0.0.1:1934 returns account lab memories; a Telegram voice note is transcribed; medium-reader loads a Medium article through browser_exec; /cron list shows the jobs from register-cron.sh; and the dashboard OIDC login through hermes-gateway works.
  Fails when: any of those fails, or its evidence is not recorded in the review
- r5 (judgment): .okf/components/hermes.md names v0.23.4 and the image's current contents (no chromium, uv 0.13.5), and the Dockerfile comments no longer cite agent-browser or 'Checked against v0.22.2'.
  Fails when: a page or comment still describes v0.22.2 as current or gives agent-browser as the reason for chromium
