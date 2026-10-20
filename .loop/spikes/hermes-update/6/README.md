---
type: spike
title: Spike hermes-update/6
description: after the upgrade, is hermes 0.22.2-1 healthy under its memory cap with the openviking provider active, does a search through the sidecar work, and do the cron jobs exist unpinned with the forced runs ok?
tags:
- spike
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T11:11:01+00:00'
slug: hermes-update
n: 6
outcome_written: true
---

# Spike hermes-update/6

after the upgrade, is hermes 0.22.2-1 healthy under its memory cap with the openviking provider active, does a search through the sidecar work, and do the cron jobs exist unpinned with the forced runs ok?

The command exited 0:

```
/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/hm-verify/verify.sh
```

## Outcome

Yes, after one fix the upgrade exposed. On 2026-10-20 `just rebuild_hermes` pushed `ghcr.io/jasperhg90/hermes:0.22.2-1` (digest e5776a47...): base v0.22.2, jq, chromium, and the OpenViking catalog plugin 2.1.1 copied in at commit 9f150ece. At 10:38 UTC the applications root updated `nomad_job.hermes` to that image, with `sessions.auto_prune: false`. All three tasks ran with 0 restarts, but the deployment failed its 5-minute healthy deadline: the image pull and the `config` prestart used it up, as on 0.21. A group `update` block (healthy_deadline 10m, progress_deadline 15m), applied in place to the same alloc c53a7771, gave a successful deployment. Nomad exec and alloc logs are refused on this client even with a management token, so the checks run over SSH to radxa with `podman exec`.

Found and fixed: the first forced runs of `daily-blog-scrape` and `insight-linker-daily` failed with "HTTP 403: Model 'deepseek-v4-flash:0731' is not allowed for virtual key 'hermes'". Every cron job had pinned that model when it was created under 0.21. Bifrost 2.3.1 (`bifrost-update`, same day) checks `allowed_models = ["*"]` against Ollama's catalog, which no longer lists it, so the gateway refuses it for every key. 2.0.0 had passed it through. A direct test against the gateway confirmed the cause: `ollama/deepseek-v4.1-flash` returns 200 and the old tag 403. All 12 jobs were released with `hermes cron edit <id> --unpin`, so they follow `model.default` (`ollama/deepseek-v4.1-flash`). Forced reruns: `insight-linker-daily` ok at 11:03:22 and `daily-blog-scrape` ok at 11:08:07 UTC.

stdout.txt: deployment successful on 0.22.2-1, and the hermes task uses 816 MiB of its 2.0 GiB cap. `hermes memory status` reports provider openviking, plugin installed and available, and plugin.yaml version 2.1.1. A search through 127.0.0.1:1934 with the placeholder key returns status ok and hits under viking://user/jasper/ (account `lab`). All 12 cron jobs, the four from register-cron.sh among them, are unpinned. The two forced runs are ok, and the overnight runs before the upgrade were ok too.

## Files

- `run.json`: the command, when it ran, its exit, the commit and tree it ran on, and where its output went
- `stdout.txt`: its standard output
- `stderr.txt`: its standard error
- `files/verify.sh`: a copy of `/tmp/claude-1000/-home-vscode-workspace/4ca90099-be7e-4fbd-920f-0030c7cc5d96/scratchpad/hm-verify/verify.sh`, which the command used
