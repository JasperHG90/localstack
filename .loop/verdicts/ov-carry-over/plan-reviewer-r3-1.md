---
type: verdict
title: 'Verdict: ov-carry-over plan-reviewer round 3'
description: 'plan-reviewer verdict for round 3 of ov-carry-over: pass.'
tags:
- verdict
- plan
generated:
  by: claude-opus/5.5
  at: '2026-10-20T15:21:51+00:00'
slug: ov-carry-over
pass: plan-reviewer
round: 3
body_schema: verdict/1
---

## Summary

Round 3, pass. p3 is resolved and I found no new risk that breaks the plan.
One cross-ticket gap is listed under Notes for the dispatcher. It does not
change this plan's approach.

## Checked

- p3. Every `rclone copy` uses `--ignore-existing`. blogs copies first, so
  the 26 shared keys keep the blogs version. blog-scraper's sidecars are
  excluded from its copy and go only through `cat | sed | rcat`, which also
  skips existing keys. That fixes the ordering trap from round 2's notes,
  where the rewrite skipped every sidecar. The hash check leaves out every
  `.abstract.md`/`.overview.md` and the 26 shared keys. So step 3's
  regenerated sidecars and later live saves no longer fail a re-run.
  Sidecars are checked by presence, the `blog-scraper/` text check covers
  `blogs/`, and the directory check runs last. Resolved.
- The `blog-scraper/` text check only works if non-sidecar files never hold
  that URI text. Otherwise it would fail on every run while the hash check
  needs those files unchanged. spike:ov-carry-over/3 found the text only in
  sidecars (2 keys, both sidecars, 0 after regeneration). Article bodies are
  scraped posts, and the URI is OpenViking's own. No risk here.
- Using `sed` instead of a per-directory semantic re-index for directories
  that exist only in blog-scraper. The spike regenerated those directories.
  The plan rewrites URI text instead. `vectors_only` reads the parent
  `.overview.md` as text, and the rewritten `### [name](uri)` entries point
  at real `blogs/` URIs. The outcome's per-tree find check would show a
  miss. That is a build detail, not a risk to the plan.
- The image-row `id` is now `md5('lab:' || new_uri)`, which matches
  `_seed_uri_for_id` as read in round 2.
- `register-cron.sh` runs only by hand ("only run once on initial deploy"),
  so the Hermes restart in ov-fresh-instance does not re-add or resume a
  paused `daily-blog-scrape`.

## Findings

- p1 (resolved): rewritten sidecars are out of the hash check and checked
  on their own.
- p2 (resolved): old image rows are copied after the re-index, as
  spike:ov-carry-over/4 tested.
- p3 (resolved): every copy and the rewrite skip existing keys, and the
  hash check covers only files the target keeps unchanged.

## Notes

- The plan says `daily-blog-scrape` is paused "from `ov-fresh-instance`'s
  cutover". `.loop/plans/ov-fresh-instance.md` (Cutover order) has no such
  step: it stops `openviking` and restarts Hermes, nothing more. The cron is
  live (spike:hermes-update/6 forced a run on 2026-10-20). If the pause is
  missed, the 08:00 run after the cutover saves new posts under
  `viking://user/jasper/resources/blog-scraper/` in the new instance and
  marks them seen in `blog-scraper.json`, so they are never saved under
  `blogs/`. This plan's outcome check would name those keys, and moving
  them by hand fixes it, so the plan still holds. But the pause has to
  happen at the ov-fresh-instance cutover, which is still in review: add
  `hermes cron pause daily-blog-scrape` to its cutover order, or have the
  operator do it then.
