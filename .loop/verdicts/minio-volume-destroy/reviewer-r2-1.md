---
type: verdict
title: 'Verdict: minio-volume-destroy reviewer round 2'
description: 'reviewer verdict for round 2 of minio-volume-destroy: pass.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T09:47:32+00:00'
slug: minio-volume-destroy
pass: reviewer
round: 2
body_schema: verdict/1
---

## Summary

f1 is fixed. The leftover openfang MinIO key is purged with all its versions,
and a full recursive walk of the secret/ mount finds no path or field named
minio. The docs' claim that every old MinIO key was purged is now true. The
tree is unchanged since round 1 and the stamp is still green, so the ticket
passes.

## Checked

- `loopctl gate stamp` from the worktree: `pass gate pre_commit`,
  `pass gate cli_tests`, `pass eval-row r1`, stamp green
  `f032c681eb3af42e51f330eb2ec6384cb7ed97fcb7a68e5bf820d50823bbcdf7`, the
  same tree as round 1.
- Vault, live: `vault kv metadata get secret/default/openfang/minio` returns
  "No value found", so the metadata and every version are gone, not only
  soft-deleted. `vault kv list secret/default/openfang` no longer lists
  `minio`.
- I did not rely on the spike's two-level check, which only matches exact
  top-level names. I walked the whole `secret/` mount recursively, with no
  depth limit: 123 paths, none matching `minio` (case-insensitive). I also
  read every leaf's field names, without printing values, and none contains
  `minio`.
- Spike 2 evidence (`.loop/spikes/minio-volume-destroy/2/`): no `minio_data`
  volume, host directory gone, and a plan holding only the 15 always-run
  `null_resource.firewall` replacements, the same as round 1.
- Docs: `.okf/components/minio.md` lines 37-38 and 117-119 say every MinIO key
  under `default/minio/*` and `default/<job>/minio` was purged with all its
  versions. The Vault walk confirms that.

## Findings

- f1: resolved. The openfang key was purged with `vault kv metadata delete`.
  My recursive walk of `secret/` finds no MinIO path left, so r2 holds and the
  purge claims in `.okf/components/minio.md` and `.okf/log.md` are true.

## Notes

`.okf/components/minio.md:117-118` says the keys were "deleted in
`minio-removal`". The openfang key was soft-deleted in April, when its job
retired, so that wording is a little loose for that one key. The purge claim
that follows is correct, and this is not a finding.
