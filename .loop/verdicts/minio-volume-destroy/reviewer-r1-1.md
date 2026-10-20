---
type: verdict
title: 'Verdict: minio-volume-destroy reviewer round 1'
description: 'reviewer verdict for round 1 of minio-volume-destroy: fail.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T09:44:25+00:00'
slug: minio-volume-destroy
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The code change, the Nomad volume deletion and the docs are right, but the
Vault purge is incomplete: `secret/default/openfang/minio` still exists, so r2
fails and two pages claim something false. Purge that path with
`vault kv metadata delete secret/default/openfang/minio`, and re-run the
evidence with a check that lists every `secret/default/<job>/` for a `minio`
key instead of a fixed job list. The fix is live and irreversible, so it comes
back for a second look.

## Checked

- `loopctl gate stamp` from the worktree: `pass gate pre_commit`,
  `pass gate cli_tests`, `pass eval-row r1`, stamp green
  `f032c681eb3af42e51f330eb2ec6384cb7ed97fcb7a68e5bf820d50823bbcdf7`.
- Diff against main: the `nomad_dynamic_host_volume.minio_data` block is
  deleted whole from `deployments/infrastructure/services.tf`, nothing else in
  that file changed. The `minio_data` allowance and its docstring line are
  gone from `cli/tests/test_no_minio.py`.
- r1: the test scans deployments/, bootstrap/, cli/src and the Dockerfile and
  fails on any `minio` substring not removed by an allowed pattern for that
  filename. With the `minio_data` pattern gone, a surviving volume block would
  fail it. A second test guards against an empty scan. The row's
  `fails_when` is asserted.
- r2, judged live myself: `nomad volume status -type host` lists 14 volumes,
  no `minio_data` and no `cb07eebf`. The spike shows the host directory gone
  and the plan holding only the 15 always-run `null_resource.firewall`
  replacements. I then listed every key under `secret/default/` and every
  key one level below it: `default/minio/` is gone, but
  `secret/default/openfang/minio` is still listed, and
  `vault kv metadata get` shows version 1 deleted, not destroyed (f1).
- r3: `.okf/components/minio.md`, `host-volumes.md`, `nodes/orangepi4a.md`,
  `nodes/placement.md`, `summary.md`, plus seaweedfs, memex,
  container-registry and `docs/reference/monitoring.md` now say the volume and
  data were deleted, and `.okf/log.md` has the entry. A grep for `minio_data`
  outside `.loop/` finds only past-tense text and ADR 0018, which stays as
  written by rule. Apart from the Vault claim in f1, r3 holds.

## Findings

- f1: `secret/default/openfang/minio` survives. It is a leftover from the
  retired openfang job, so it was not in the six-job list the verify script
  walked, and the script also reports `gone` on any error from
  `vault kv metadata get`, not only on not-found. Purge it, make the check
  enumerate paths, and the claims in `.okf/components/minio.md` ("Every old
  MinIO key in Vault ... was purged") and `.okf/log.md` become true.
