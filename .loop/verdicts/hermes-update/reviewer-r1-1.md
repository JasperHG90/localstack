---
type: verdict
title: 'Verdict: hermes-update reviewer round 1'
description: 'reviewer verdict for round 1 of hermes-update: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T11:15:21+00:00'
slug: hermes-update
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The upgrade is correct and verified live. The image, the pinned plugin copy,
the config, the deployment deadlines and the docs all match the plan. The
runtime change that unpinned the cron jobs is recorded well enough in
`.okf/components/hermes.md`, and `register-cron.sh` needs no change, because
v0.22 does not pin a model when it creates a job. Two non-blocking findings:
the memex model rename is not recorded and not deployed (f1), and the r1 test
does not tie the curl fetch to the pinned SHA (f2).

## Checked

- Gates: `loopctl gate stamp` from the worktree passed `pre_commit`,
  `cli_tests` and eval row r1 and stamped green at
  545e49a99fbef1eeb6215bd906126e395a68e0b2ccd522d7eba90dd17b99f27a.
- Code read in full: Dockerfile, the hermes.hcl hunks (group `update` with
  progress_deadline 15m above healthy_deadline 10m, `sessions.auto_prune:
  false`), services.tf, memex.hcl, test_hermes_version.py, ADR 0019, the
  hermes and bifrost pages, log.md and summary.md. The curl and tar
  `--strip-components=3` path lands the plugin files directly in
  `/opt/hermes/plugins/memory/openviking`. The local image
  `ghcr.io/jasperhg90/hermes:0.22.2-1` (e5776a47) holds plugin.yaml and the
  plugin modules there.
- r1: the test pins the base exactly, `hermes_version` exactly, and both
  config keys inside their YAML blocks. The pin check is weaker, see f2.
- r2 (judgment): spike 6 stdout shows deployment `successful` on
  `ghcr.io/jasperhg90/hermes:0.22.2-1`, the hermes task at 816 MiB of 2.0
  GiB, `hermes memory status` reporting openviking installed and available
  at plugin 2.1.1, a 1934 sidecar search returning `status ok` with hits
  under `viking://user/jasper/`, all 12 cron jobs (the four from
  `register-cron.sh` among them) unpinned, and forced `daily-blog-scrape`
  and `insight-linker-daily` runs `ok` after the unpin. The row holds.
- r3 (judgment): the Dockerfile comment and `.okf/components/hermes.md` say
  the provider is copied in at build time and pinned by commit. ADR 0019
  records that choice over the lazy install and over pip. No tracked file
  still says the provider ships in the base image (git grep). The row holds.
- The cron runtime change and register-cron.sh: I read `cron/jobs.py` and
  `tools/cronjob_tools.py` in the 0.22.2 image. `create_job` takes
  `pinned: bool = False` and only sets a model when it is pinned. The tool
  description says jobs follow the main model unless pinned. So
  `register-cron.sh`'s `/cron add` lines make unpinned jobs under 0.22, and a
  fresh `hermes_data` volume does not bring the trap back. The hermes page's
  "Cron jobs follow the main model" paragraph records the 2026-10-20 unpin,
  why it was needed, and how the trap would come back. That is enough for
  state that lives on the volume.

## Findings

- f1 (docs, non-blocking): the memex.hcl edit is right (the same
  `deepseek-v4.1-flash` the gateway answered 200 for in spike 6), but it is
  out of plan scope and undeployed while live memex is failing. Add a line
  to `.okf/log.md`, or to `components/memex` if it names models, saying
  memex's default and reflection models moved and that the change waits for
  the next applications apply. Or tell the operator to apply it.
- f2 (test-strength, non-blocking): assert that the codeload URL uses
  `${OPENVIKING_PLUGIN_SHA}`, for example by matching the curl line, so a
  floating ref fails r1.

## Notes

The comments in `deployments/applications/services.tf` near line 983, in
`scripts/check_openviking_config.py:128` and in
`.okf/practices/openviking-vision-models.md:27` say "both deepseek-v4
variants are in the catalog". These were dated measurements from September.
I could not tell whether one of the two variants meant is the retired
`:0731` tag, so I raise no finding.
