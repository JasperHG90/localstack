---
type: plan
title: 'Plan: hermes-update-0-23'
description: Move the hermes job from hermes-agent v0.22.2 to v0.23.4, the latest upstream release, and keep its OpenViking memory, Bifrost models, voice notes, browser skills and crons working.
tags:
- plan
generated:
  by: process:loopctl/2.4.0
  at: '2026-11-26T13:30:30+00:00'
slug: hermes-update-0-23
epic: null
depends_on: []
priority: null
schema_version: '2.0'
---

# hermes-update-0-23

Relayed from: none

## Intent

Hermes runs hermes-agent v0.22.2. `deployments/applications/services/hermes/Dockerfile`
builds `FROM nousresearch/hermes-agent:v0.22.2`, and `hermes_version =
"0.22.2-3"` in `nomad_job.hermes` (`deployments/applications/services.tf`)
tags the image. The latest upstream release is v0.23.4 (2026-11-24).
The image nousresearch/hermes-agent:v0.23.4 ships linux/arm64. Its user, entrypoint,
`HERMES_HOME` and s6 `main-wrapper.sh` are unchanged.

The image, the skills and the config move together, because the new base
alone fails the build.

The image:
- Bump the base to `v0.23.4` and `hermes_version` to `0.23.4-1`, then build
  and push with `just rebuild_hermes` (`deployments/applications/justfile`)
  before the apply.
- The pinned uv moved from 0.12.3 to 0.13.5, and `/opt/hermes/tools/uv-0.12.3-linux-arm64/`
  no longer exists. The faster-whisper `RUN` line points at
  `uv-0.13.5-linux-arm64` instead. The `stt-whisper` extra still pins
  faster-whisper 1.2.1, and now pins `av==18.1.0` itself.
- Drop `chromium` from the apt line. v0.23.0 removed agent-browser, the
  reason the Dockerfile gives for it. The base ships its own chromium, which
  the browser runtime resolves before any system one. Keep `jq`: the base
  still lacks it, and `deployments/applications/services/hermes/skills/research/autoresearch-finalize/finalize.sh` uses it.
- Keep the OpenViking catalog plugin at 2.1.1 (`9f150ece`). It imports
  `agent.message_content`, which moved, and the compat shim at upstream
  hermes_agent/compat/moves.py maps that import for this plugin by name.
  Upstream's 2.1.2 only adds `OPENVIKING_EXTRA_HEADERS`.

The skills: v0.23.0 removed `browser_navigate`, `browser_snapshot` and the
other `browser_*` tools in favour of `browser_exec`. Rewrite the browsing step
in `deployments/applications/services/hermes/skills/productivity/medium-reader/SKILL.md`
for `browser_exec`, and correct the wording in
`deployments/applications/services/hermes/skills/productivity/blog-scraper/SKILL.md`
and `deployments/applications/services/hermes/SOUL.md`. The `browser` toolset
name stays.

The config: every config key and env var the job sets still exists with the
same meaning. The `files` toolset name in `platform_toolsets` is a separate,
older bug, fixed by ticket `hermes-file-toolset`.

Rollback: v0.23.3 moves `state.db` from schema 31 to 33, and nobody has
checked whether v0.22.2 opens a v33 database. Copy `state.db` off the
`hermes_data` volume on radxa before the apply.

Update `cli/tests/test_hermes_version.py` (base, uv path, tag) and
`.okf/components/hermes.md` (version, image contents) with the change.

Outcome: the `hermes` job's new deployment is healthy on
`ghcr.io/jasperhg90/hermes:0.23.4-1`. The gateway log shows `openviking_tools`
loaded, and a `viking_search` through 127.0.0.1:1934 returns account `lab`
memories. A Telegram voice note is transcribed. The `medium-reader` skill
loads a Medium article through `browser_exec`. `/cron list` still shows the jobs from
`deployments/applications/services/hermes/register-cron.sh`. The dashboard
OIDC login through hermes-gateway works. `just pre_commit` and
`uv run --directory cli pytest` pass.

## Problems

- P1: Hermes runs v0.22.2, a minor release behind upstream v0.23.4, and the Dockerfile cannot build on the new base because its uv path is gone.
- P2: The `medium-reader` skill calls `browser_navigate` and `browser_snapshot`, which v0.23.0 removed.

## Goals

- G1: Run the current upstream Hermes with memory, models, voice notes and crons still working.
- G2: Keep every skill able to reach the tools it names.

## Outcomes

### O1: The hermes image builds on v0.23.4 and the job runs healthy on 0.23.4-1
- kind: behaviour
- goal: G1
- fixes: P1
- needs: none
- touches: `deployments/applications/services/hermes/Dockerfile`, `deployments/applications/services.tf`, `cli/tests/test_hermes_version.py`, `.okf/components/hermes.md`
- checked by: `just rebuild_hermes`, the new deployment's health, `openviking_tools` in the gateway log, a `viking_search` returning `lab` memories, a transcribed voice note, `/cron list`, and `uv run --directory cli pytest`
- seen by: operator

### O2: medium-reader browses with browser_exec
- kind: support
- goal: G2
- fixes: P2
- needs: O1
- touches: `deployments/applications/services/hermes/skills/productivity/medium-reader/SKILL.md`, `deployments/applications/services/hermes/skills/productivity/blog-scraper/SKILL.md`, `deployments/applications/services/hermes/SOUL.md`
- checked by: a grep finding no removed `browser_*` tool name under `deployments/applications/services/hermes`, and one medium-reader run on the new image
- seen by: operator

## Could invalidate this plan

- Voice notes on the new base. The faster-whisper install runs
  `uv export --frozen --extra stt-whisper` with the base's own uv. v0.23.4
  ships uv 0.13.5, `uv.lock` revision 5 and Python 3.14.9. If that export or
  the install fails, or pulls an `av` or `ctranslate2` build without an arm64
  cp314 wheel, voice notes stop working and the plan needs another way to
  pin the speech engine.
  Settled by `spike:hermes-update-0-23/2`: on v0.23.4 arm64 the line, with
  uv switched to `uv-0.13.5-linux-arm64`, built and pulled arm64 cp314 wheels
  for all 12 packages (faster-whisper 1.2.1, av 18.1.0, ctranslate2 4.8.3).
  The gateway voice path picked `local`/`base` and transcribed a 5.4 s opus
  clip, peaking at 574 MB. Upstream's lock pins av 18.1.0, which PyPI has
  yanked over a double free with custom channel layouts. Mono opus decoded
  fine, so the line keeps the lock's pin.
- The memory plugin on 0.23. The OpenViking catalog plugin 2.1.1 imports a
  module that moved, and our `openviking_tools` wrapper subclasses its
  provider. The compat shim and the unchanged `MemoryProvider` base say both
  still load, but only by reading. If the gateway on v0.23.4 fails to load
  `openviking_tools`, or the new rule that each load returns a fresh instance
  refuses it, Hermes loses its memory and the plan needs a plugin bump or a
  wrapper rewrite.
  Settled by `spike:hermes-update-0-23/3`: an image built from v0.23.4 with
  the Dockerfile's plugin `RUN` and `COPY openviking_tools`, run as the
  unattended gateway with config rendered from `hermes.hcl`, logged
  `openviking_tools` registered (7 tools) and activated with no error.
  `viking_search` sent `POST /api/v1/search/find` to a stub at
  `OPENVIKING_ENDPOINT`. No plugin was installed at runtime.
- The Bifrost model provider on 0.23. Every model call goes through the
  `model-providers/bifrost` drop-in plugin that the `config` task writes.
  `register_provider` and `ProviderProfile` keep every field it passes, by
  reading. If that plugin does not load on v0.23.4, no model call works and
  the plan grows a provider rewrite.
  Settled by `spike:hermes-update-0-23/1`: the plugin, copied byte for byte
  from `hermes.hcl`, loads in v0.23.4 (Python 3.14.9) as provider `bifrost`,
  and a one-shot run sent `POST /v1/chat/completions` to a stub Bifrost.
