---
type: eval
title: 'Eval: hermes-update'
description: 'Definition of done for hermes-update: 3 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T09:07:54+00:00'
slug: hermes-update
signoff:
  signer: delegated:jasperginn@gmail.com/planner
  hash: ffd9b0c1ff9cfdeb370eccd5939b569021af58b35d510879b3e751d58ec47704
  at: '2026-10-20T09:07:54+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: The Hermes Dockerfile builds from hermes-agent v0.22.2 and copies the OpenViking catalog plugin pinned at commit 9f150ece (examples/hermes-plugin) into /opt/hermes/plugins/memory/openviking; hermes_version is 0.22.2-1; config.yaml in the jobspec sets sessions.auto_prune false and memory.provider openviking.
  Fails when: the base is another version or floating, the plugin is unpinned, fetched at runtime or copied elsewhere, hermes_version differs, or either config setting is missing
- r2 (judgment): After the image is pushed and applied, the hermes job's new deployment is healthy on ghcr.io/jasperhg90/hermes:0.22.2-1, hermes memory status names openviking, a viking_search through 127.0.0.1:1934 returns account lab memories, /cron list shows the four jobs from register-cron.sh, a forced or scheduled daily-blog-scrape and insight-linker-daily run completes, and the hermes task stays under 2048 MiB.
  Fails when: any of those fails, or the evidence is not recorded in the review
- r3 (judgment): .okf/components/hermes.md and the Dockerfile comments say the OpenViking provider is copied in at build time from the pinned catalog plugin, and a decision record covers that choice over a lazy install.
  Fails when: a page still says the provider ships in the base image, or the decision record is missing
