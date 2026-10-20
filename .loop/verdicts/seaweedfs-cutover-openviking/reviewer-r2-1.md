---
type: verdict
title: 'Verdict: seaweedfs-cutover-openviking reviewer round 2'
description: 'reviewer verdict for round 2 of seaweedfs-cutover-openviking: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T07:30:40+00:00'
slug: seaweedfs-cutover-openviking
pass: reviewer
round: 2
body_schema: verdict/1
---

## Summary

f1 is fixed. Each rclone listing now writes straight to its file with its own
exit guard, and sorting happens in separate steps. A new test rejects any
rclone line that pipes with a single `|`. The f2 allowlist is also in, with
exit 5 and a test that pins it to the four durable buckets. Two non-blocking
items are left. The docs do not mention exit 5 (f3). And the brief says main
was merged, but the staged tree only goes up to main before the observability
merge, so landing will hit doc conflicts again (f4). The code merges cleanly
and the tests pass on the merged tree.

## Checked

- `loopctl gate stamp` from the worktree: pass pre_commit, pass cli_tests,
  pass r1, pass r2, stamp green
  141a16ef1e7eb5a3eda8046f3154484cf3731a73e581b95dcdde3bbb4747af62.
- restore-s3.hcl, read in full. Both `lsf -R` listings redirect to
  /tmp/src-dirs and /tmp/dst-dirs with `|| exit 4` and `|| exit 3`, and
  `sort -o` runs after them. The top-level prefix listing is
  `prefixes=$(rclone lsf ...) || exit 4`. An assignment takes the status of
  its command substitution, so that guard works. The later
  `echo "$prefixes" | grep` pipe has no rclone in it. An unchecked `sort -o`
  failure would leave the files unsorted, and `comm` would then report false
  missing entries and exit 3. That fails safe.
- The case allowlist runs before any GCS access, and anything else exits 5.
- test_no_rclone_output_is_piped: the regex looks for a single `|` on a line
  that contains rclone, outside a `#`. It would catch
  `rclone lsf ... | sort > f || exit 4`, which is exactly the f1 shape, and
  `||` does not match it. test_only_durable_buckets_are_restored pins the
  case arm to DURABLE_BUCKETS and to exit 5.
- Base: `git diff --cached main` still shows main's observability work
  reversed (grafana/seaweedfs.json, test_observability_s3_clients.py,
  loki.hcl, tempo.hcl). Comparing the staged tree with each main commit shows
  it matches main as of 64a54fa/88003ec, which is before 62b07a6. I simulated
  a merge (commit-tree of the staged tree, then `git merge-tree` against
  main). It reports conflicts only in .loop/ and .okf/ files. The .tf, .hcl
  and test files merge cleanly. `uv run --directory cli pytest` on the merged
  tree, extracted to scratch, gave 637 passed and 1 failed. The failure is
  test_versions' `git grep`, which only fails because the scratch copy is not
  a git repo.
- The header comment in restore-s3.hcl now lists exit codes 1 to 5 and the
  reason for not piping.

## Findings

- f1 (resolved): fixed in restore-s3.hcl as described under Checked, and
  test_no_rclone_output_is_piped guards it.
- f2 (resolved): the case allowlist with exit 5, guarded by
  test_only_durable_buckets_are_restored.
- f3 (docs, non-blocking): add a row for 5 to the exit-code table in
  docs/reference/gcs-backups.md, and add a step 0 that refuses a bucket that
  is not one of the four durable ones. Add "5 not a durable bucket" to the
  exit-code sentence in .okf/components/gcs-backups.md, and also mention the
  SeaweedFS listing under 3 there, as the reference page does.
- f4 (docs, non-blocking): merge current main (7593db6, which contains
  62b07a6) before landing, and resolve the five .okf conflicts so that each
  page reflects both cutovers: Loki and Tempo on SeaweedFS from observability,
  and OpenViking, models and datalake from this ticket. The code needs no
  change.

## Notes

- After the merge, seaweedfs.md still says "The cutover comes in later
  tickets". Now that OpenViking and observability have both moved, that
  sentence should name what remains (registry, then MinIO removal).
