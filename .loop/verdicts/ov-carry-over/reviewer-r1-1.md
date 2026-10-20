---
type: verdict
title: 'Verdict: ov-carry-over reviewer round 1'
description: 'reviewer verdict for round 1 of ov-carry-over: fix.'
tags:
- verdict
- review
generated:
  by: claude-opus/5.5
  at: '2026-10-20T17:01:03+00:00'
slug: ov-carry-over
pass: reviewer
round: 1
body_schema: verdict/1
---

## Summary

The change does what the plan says. The job copies only the four trees,
blogs before blog-scraper, with --ignore-existing on both writes. It rewrites
blog-scraper's sidecars on their own pass and runs its checks in the order
the plan asks, each with its own exit code. The key cannot write the old
bucket. The script derives row ids the way OpenViking 0.4.17.1 does, and
nothing in it writes the old bucket or the old schema. Gates are green on my
own stamp. One non-blocking finding: the outcome check will trip on main's
new `.map.md` after the merge.

## Checked

- `loopctl gate stamp` from the worktree: `stamp green:
  c6f675d0d32310f0135e8a52fedcc82c6a7835fe620d557a69a61bbf8a86b59d`. pre_commit,
  cli_tests and rows r1 to r7 pass.
- Image row id. In 0.4.17.1, `collection_schemas.py:795` sets id =
  md5(`<account>:<seed_uri>`) on the `viking://` URI, before
  `vectordb_adapters/base.py:_encode_uri_field_value` stores it as
  `/user/...`. For a level-2 row, `_seed_uri_for_id` returns the URI as is.
  So md5('lab:viking:/' || stored uri) is the right id. `update_uri_mapping`
  uses the same derivation. The table has no `parent_uri` column, so
  rewriting `uri` is enough.
- Regeneration set. I ran `merged_directories` on the real listing
  (ov-objects.txt). It gives argon, addyosmani, anthropic, deepmind,
  mistral, ollama, spotify and then blogs/: eight directories, which matches
  ADR 0022. openai has no file on either side, only markers. uber's files
  are all in blog-scraper, and the blogs side holds one empty directory and
  no sidecars, so the rewritten blog-scraper sidecars carry it. Leaving both
  out is correct. The only shared keys are markers and sidecars, so the
  hash check can never see a shared file. The kept trees have no other
  dotfiles. The 71 images are png, webp, jpg and gif, and all four
  extensions are in IMAGE_SUFFIXES.
- Ollama sampling risk. `semantic_dag._dispatch_dir` sorts the direct
  entries by name and runs `deterministic_sample(…, 32)`. I simulated it on
  the merged listing. For ollama, 63 entries reduce to 32, and
  `windows-preview.md` (one of the two blogs-side children) is in the
  sample. Overviews resolve child links to real URIs, which carry the child
  name. The check needs any one name per half, so it can pass. If the model
  leaves it out, the check fails loudly instead of passing wrongly. Every
  other merged directory samples all of its blogs-side children.
- Key. Statement 1 grants only GetBucketLocation, GetObject and ListBucket
  on `openviking` and `openviking/*`. Statement 2 grants
  `local.seaweedfs_write_actions` on `openviking-v2` only. There is no other
  policy for the user, and it is not in `local.buckets`. The `openviking`
  key already showed this ARN shape keeps the two buckets apart. r4's test
  parses the statements and bounds the old bucket's actions to the three
  reads.
- No writes to the old side. In the job, `$old` is only ever a source
  (copy, check, lsf). Every write goes to `$new` or a local tmp. In the
  script, `openviking.ov_context` appears only in SELECTs and in the FROM of
  the INSERT…SELECT into `openviking_v2`.
- Eval rows r1 to r7. Each test asserts its fails_when. r1 checks the
  refused tree (exit 5, nothing copied), the top-level set and the
  --ignore-existing flags. r2 would catch a scraper copy that includes
  sidecars, a missing rewrite or an overwrite. r3 seeds regenerated shared
  sidecars and expects exit 0, plus one case for each of codes 2, 3, 6 and
  7, all distinct. r5 checks the order, the rows-after-reindex step and the
  new id with no old id. r6 covers each defect kind. r7 checks the parent
  path and the source list.
- r8 (judgment). The how-to produces every piece of evidence the row names.
  Step 3 gives the job's exit code. Step 4's script prints each re-index
  result with failed and unsupported counts, then checks counts, the union
  and the since-cutover notes, the merged overviews, the 52 image rows plus
  a find by name, 10 title finds per tree, and the top-level "nothing else".
  Step 5 diffs the old bucket against the cutover baseline. The `--format
  pst` baseline parses with `read_listing`. The task polling and the
  `failed_records` field match `reindex_executor.py` and `tasks.py`. The
  check covers only `user/jasper/resources/`, which is the one place the
  carry-over writes. Caveat: see f1.
- Consistency: reference/openviking.md (exit codes, key scope), the
  seaweedfs and openviking-service components, the storage.tf comments, the
  OpenViking README and ADR 0022 agree with the code.

## Findings

f1: `.map.md` from ADR 0023 is a top-level name the check rejects by
default. This is a plain fix: a default allow, or one line in the how-to.

## Notes

- ADR 0022's Context says the two blog trees "hold the same eight sources".
  blog-scraper also holds nvidia, deepseek, `_lockprobe` and some loose
  posts. Loose wording, worth a touch if you are in the file anyway.
- `_lockprobe/Example_Domain` (a probe artifact) carries into `blogs/`. The
  plan says to copy whole trees, so this is the operator's call.
- `reindex()` treats a `cancelling` task status as finished and failed. That
  is fine.
