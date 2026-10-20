---
type: verdict
title: 'Verdict: bifrost-update reviewer round 1'
description: 'reviewer verdict for round 1 of bifrost-update: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T10:31:56+00:00'
slug: bifrost-update
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The change does what the plan asks. The pin is 2.3.1, the provider stays at
~>0.1.0, the smoke probe expects `access_not_found`, and the component page
records the version and the migration that cannot be undone. The live job runs
v2.3.1 and is healthy, and I confirmed the post-switch traffic on my own. One
docs finding that does not block: the page points readers at the rollback dump
without naming it, and that dump can be overwritten or expire.

## Checked

- Gates: `loopctl gate stamp` from the worktree passed pre_commit, cli_tests
  and eval-row r1, with "stamp green: d91b88a1...". That fingerprint matches
  the one spike 5's run.json recorded, so the live evidence ran on this tree.
- Code read in full: the staged diff of services.tf, bifrost_smoke.py,
  cli/tests/test_bifrost_version.py and .okf/components/bifrost.md.
  `bifrost_version` feeds only `image = docker.io/maximhq/bifrost:v${bifrost_version}`
  in bifrost.hcl:40. The smoke probe's label is compared against the response
  `type`, so the rename is the only change it needs.
- r1: the test's regex finds every `bifrost_version = "..."` and asserts it
  equals exactly ["2.3.1"], so another version or "latest" fails it. It
  asserts the `~>0.1.0` string inside the `bifrost = {}` block of
  providers.tf, and it asserts that the smoke tuple has `access_not_found`
  and no `virtual_key_not_found`. Each fails_when clause is asserted.
- r2 (judgment): spike 5 records a forced backup-postgres run at 10:24:51 UTC
  writing gs://localstack-cluster-backups/postgres/pgdumpall-2026-10-20.sql.gz
  before the job was submitted at 10:25:55 UTC (nomad job status). The
  backup-postgres.hcl command is pg_dumpall, so it covers the `bifrost`
  database. Met. f1 covers how long that dump stays usable.
- r3 (judgment): `nomad job status bifrost` shows deployment e457904c
  successful, one healthy alloc on version 11. Spike 5's stdout has the
  smoke script passing all five checks on v2.3.1, a bare-string rerank
  through the OpenViking key returning 200 with the correct order, and a
  second plan reporting "No changes". Spike 5's Prometheus query used a 10m
  window that started before the switch, so I queried again myself:
  process_start_time is 10:26:10 UTC, and the new process's counters show
  bifrost_success_requests_total from openviking (embedding 3, rerank 2) and
  hermes (embedding 2) to embark. `sum(increase(...[3m]))`, a window that
  falls wholly after the start, gives 4.8 success and 7.2 upstream. These
  are the series the dashboard's `sum(rate(...[5m]))` panels read. `up` is 1.
  Met.
- r4 (judgment): the component page names v2.3.1 as the image and has a
  version-history paragraph on the migration that cannot be undone. A grep
  of docs/, README.md and .okf/ for a Bifrost 2.0.0 claim found none still
  naming it as current. The ">= 2.0.0"-style mentions in ADR 0008 and
  bifrost.hcl are historical or still true. Met.
- The missing baseline run on 2.0.0: once the label rename is in, the new
  script fails on 2.0.0 by design, so a before-run would have needed the old
  script. The baseline guards against an after-run that passes only because
  the property never held. Every assertion passed after the switch. Spike 4
  showed keys made on 2.0.0 survive, and spike 3 showed bare-string rerank
  works on both versions. I accept the gap.

## Findings

- f1 (docs, not blocking): the bifrost.md rollback paragraph says the way
  back is "the backup-postgres dump taken just before the apply" but does
  not name it. The object name has only a date in it, rclone overwrites it,
  and the bucket deletes objects after 180 days with no versioning. Name the
  object and its limits, or copy it to a name no job writes.

## Notes

- The plan says 2.3.0 adds an `app` label on request metrics. The live
  series carry no `app` label. That does not matter here, because the
  dashboard sums every label away.
