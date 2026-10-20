---
type: eval
title: 'Eval: ov-carry-over'
description: 'Definition of done for ov-carry-over: 8 row(s).'
tags:
- eval
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T16:10:13+00:00'
slug: ov-carry-over
signoff:
  signer: delegated:jasperginn@gmail.com/claude-opus/5.5
  hash: 8c6e8b564618d18a49a89f2b4ae8786b4bc38552abbf0d04c8061da0e62db96d
  at: '2026-10-20T16:10:13+00:00'
verified: null
---

Rows: rows.json; the fields each row takes: loopctl schema eval-rows.

- r1: The ov-carry-over job copies only clips, blogs, leo and blog-scraper (remapped into blogs/) from the old bucket, every copy skips existing keys, and it refuses any other prefix.
  Fails when: the job copies any other prefix, lacks --ignore-existing on a copy, keeps blog-scraper's own key prefix, or accepts a prefix outside the four.
- r2: blog-scraper sidecars reach blogs/ only through the rewrite step, which replaces the blog-scraper/ URI with blogs/ and skips existing keys.
  Fails when: the blog-scraper copy includes .abstract.md/.overview.md, the rewrite does not replace the URI text, or it overwrites an existing key.
- r3: The job's checks hash-compare only non-sidecar files, require every sidecar present at its new key, require no blog-scraper/ text under blogs/, run the directory check, and exit with a distinct code per failure.
  Fails when: the hash check includes sidecars or the 26 shared keys, a missing sidecar, leftover blog-scraper text or a missing directory does not fail the job, or two failures share an exit code.
- r4: The ov-carry-over storage user can only read and list the old openviking bucket and write openviking-v2.
  Fails when: the user gets any write or delete action on openviking, or lacks read on openviking or write on openviking-v2.
- r5: The re-index script regenerates the merged blogs directories deepest first and blogs/ last, runs vectors_only on clips, blogs and leo, then copies the old image rows with the URI rewritten and id = md5('lab:' || new_uri).
  Fails when: the regeneration order or set is wrong, vectors_only runs on another tree, image rows are copied before the re-index, keep blog-scraper/ in their URI, or keep the old id after a rewrite.
- r6: The script's comparison against real listings under tmp_path passes on a correct carry-over and names each missing, extra or out-of-place key otherwise.
  Fails when: a missing file, an extra top-level tree, a leftover blog-scraper key or a count mismatch passes the comparison.
- r7: The blog-scraper skill saves new posts under blogs/<source>/.
  Fails when: the skill still names blog-scraper/ as its save path.
- r8 (judgment): Live after the carry-over: the job exits 0; clips and leo match the old counts and blogs holds the union; the re-index reports zero failures (images unsupported); a title search finds 10 random files per tree; each of the 52 images with an old row has one at its new URI and is found by name; nothing outside clips, blogs and leo beyond what ov-fresh-instance created; the old bucket's object count is unchanged.
  Fails when: the recorded post-run evidence shows any of these failing.
