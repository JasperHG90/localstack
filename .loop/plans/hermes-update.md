---
type: plan
title: 'Plan: hermes-update'
description: Move the hermes job from hermes-agent 0.21.0 (base v2026.8.31) to 0.22.2, the latest upstream release, and keep its OpenViking memory, Bifrost models and crons working.
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T08:09:45+00:00'
slug: hermes-update
epic: null
depends_on: []
priority: null
---

# hermes-update

Relayed from: none

## Intent

Hermes runs hermes-agent 0.21.0: `deployments/applications/services/hermes/Dockerfile`
builds `FROM nousresearch/hermes-agent:v2026.8.31`, and `hermes_version =
"0.21.0-1"` in `nomad_job.hermes` (`deployments/applications/services.tf`)
tags the image both tasks in `deployments/applications/services/hermes.hcl`
run. The latest upstream release is v0.22.2 (2026-10-15). Upstream switched
to SemVer tags at v0.21.6, so the base becomes the upstream
`hermes-agent` image at tag `v0.22.2`, which ships arm64.

The bump is one change that cannot ship in parts: the new base alone
leaves Hermes without its memory provider, so the image, the provider and
the config move together.

The tag: bump the Dockerfile base to `v0.22.2` and `hermes_version` to
`0.22.2-1`, then build and push with `just rebuild_hermes`
(`deployments/applications/justfile`) before the apply.

The provider: OpenViking left core in v0.22.0 (upstream PR 134350) and now
comes from Volcengine's catalog plugin (`openviking` 2.1.1 at `9f150ece`),
which Hermes installs at first start when `memory.provider: openviking` is
set and lazy installs are on (see the first risk). The plugin reads the same
`OPENVIKING_ENDPOINT`, `OPENVIKING_API_KEY`, `OPENVIKING_ACCOUNT` and
`OPENVIKING_USER` env and exposes the same six `viking_*` tools the skills
call, so the sidecar contract with
`deployments/applications/services/hermes/ov_auth_proxy.py` stays as is.

The config: change `config.yaml` in the jobspec only where 0.22 needs it.
Release notes that touch this job: `sessions.auto_prune` now defaults to on
and deletes ended sessions idle for 90 days at startup; cron tools load
behind `tool_search` and `cronjob` is renamed `cronjob_manage` (the old name
still works); unpinned cron jobs follow the main model at fire time; one
gateway per machine is the default (this job has one profile). The skills
layout (`skills.external_dirs`, `skills_sync.py`, which `start-hermes.sh`
relies on) and the upstream `ProviderProfile` base class, which the
Bifrost profile imports, are still present at v0.22.2. The Dockerfile
comments and
`.okf/components/hermes.md` that say the provider ships in the base image
change with it, and the provider choice gets a `kmctl new decision` record.

Memory: the `hermes` task uses 817 MiB of its 2048 MiB cap (measured with
`nomad alloc status -stats` on alloc 8c8f1338, 2026-10-20). Oversubscription
is off, so 2048 is the hard cap and stays unchanged unless the new version
measures near it. The arm64 base grows from 939 MB to 1,096 MB compressed.
The last deployment (c795ebaa) failed its progress deadline after a 2.5
minute pull although the alloc runs, so judge health from the new
deployment's status, not from the alloc alone.

Outcome: the `hermes` job's new deployment is healthy on
`ghcr.io/jasperhg90/hermes:0.22.2-1`; `hermes memory status` names
openviking and a `viking_search` through 127.0.0.1:1934 returns account
`lab` memories; `/cron list` still shows the four jobs from
`deployments/applications/services/hermes/register-cron.sh`, and the 08:00
`daily-blog-scrape` and 10:00 `insight-linker-daily` runs complete (scheduled
or forced with `/cron run`); the `hermes` task stays under 2048 MiB;
`just pre_commit` and `uv run --directory cli pytest` pass.

## Could invalidate this plan

- OpenViking memory provider left core. The Dockerfile and
  `.okf/components/hermes.md` assume the provider ships in the base image.
  At v0.22.x Hermes must fetch Volcengine's catalog plugin at first start.
  If that install fails inside the container (no lazy install in a
  non-interactive gateway, no network path, a write outside the
  `hermes_data` volume that is lost on restart), or the plugin does not talk
  to OpenViking through the sidecar with a placeholder key and account
  `lab` (or tries to start its own `openviking-server` because the endpoint
  is localhost), Hermes loses its memory and the plan needs a different way
  to supply the provider. Waiting on a spike.
- Bifrost provider profile under 0.22. Every model call goes through the
  drop-in `model-providers/bifrost` plugin the `config` task writes. v0.22.0
  removed the plugin compat import layer and moved the runtime to Python
  3.14. If `from providers import register_provider` or `ProviderProfile`
  no longer load from `$HERMES_HOME/plugins/model-providers/`, no model call
  works and the plan grows a provider rewrite. Waiting on a spike.
