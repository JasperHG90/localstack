---
type: plan
title: 'Plan: ov-carry-over'
description: Copy the clips, blog-scraper and blogs trees from the old OpenViking bucket into the fresh instance key for key, re-index them there without new summaries, and carry nothing else.
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-20T13:56:21+00:00'
slug: ov-carry-over
epic: ov-reset
depends_on:
- ov-fresh-instance
priority: 3
---

# ov-carry-over

Relayed from: none

## Intent

`ov-fresh-instance` starts OpenViking over on a new bucket and a new
Postgres schema, account `lab`, user `jasper`, and leaves the old
`openviking` bucket and schema as a read-only backup. The operator keeps
four trees from the old instance and nothing else: clips (280 objects,
written by ov-clip), blog-scraper (2417), blogs (166) and leo (449, Leo's
meeting transcripts, digests and notes). In the old bucket they sit under
`lab/user/jasper/resources/{clips,blog-scraper,blogs,leo}/`. OpenViking maps
`viking://X` to `/local/<account>/X`, so that key is the URI
`viking://user/jasper/resources/<tree>` (jasper's own resources), not the
account-shared `viking://resources/<tree>`. The operator keeps this root
(`viking://user/jasper/resources/`, their choice over the shared
`viking://resources/`). clips, blogs and leo land at the same URI and key
they have now. blog-scraper is merged into blogs (operator's choice: one
`blogs/<source>/` tree for scraped and shared posts): its keys land under
`blogs/` with the `blog-scraper/` segment replaced. Memories, peers,
sessions, projects and handoffs stay behind.

How: copy at the storage layer, then re-index in the new instance. This
needs no old OpenViking at all, so the choice between exporting before the
cutover and running a temporary old instance falls away. A temporary old
instance would write its queue and vector state into the backup. An export
before the cutover would have to run before `ov-fresh-instance`, which this
ticket depends on. Pack export/import (`/api/v1/pack/*`) needs a running
old instance, so it is the fallback, not the plan.

1. Copy. A parameterized Nomad batch job `ov-carry-over`
   (`new:deployments/applications/services/ov-carry-over.hcl`, registered in
   `deployments/applications/services.tf`) runs on the rclone 1.75.2 image
   `deployments/infrastructure/services/restore-s3.hcl` uses. For each of
   the four source trees, and only those (the job refuses any other prefix),
   it runs `rclone copy --create-empty-src-dirs --s3-directory-markers` from
   `openviking/lab/user/jasper/resources/<tree>/` to the same prefix in the
   new bucket, except blog-scraper, which copies to `.../resources/blogs/`.
   The two blog trees share 26 relative keys: the root and per-source
   (addyosmani, anthropic, deepmind, mistral, ollama, openai, spotify, uber)
   `.abstract.md`/`.overview.md` sidecars and directory markers, and one
   article (`deepmind/gemini-4-argon.md/`). blogs copies first and
   blog-scraper copies with `--ignore-existing`, so a shared key keeps the
   blogs version. Every `.abstract.md` and `.overview.md` copied from
   blog-scraper has the text `viking://user/jasper/resources/blog-scraper/`
   rewritten to `viking://user/jasper/resources/blogs/` on the way
   (`rclone cat | sed | rclone rcat`), so directories that exist only in
   blog-scraper need no new summary: their copied sidecars would otherwise
   still point at `blog-scraper/` URIs (spike:ov-carry-over/3); `rclone check` for blog-scraper skips those 26 keys by an
   explicit list, then `rclone check --one-way` (every old file present with
   the same hash), then the one-way directory check from restore-s3, because
   `rclone check` passes with every marker missing
   (`spike:seaweedfs-cutover-openviking/2`). It exits with a distinct code
   per failure, as restore-s3 does. The `.abstract.md` and `.overview.md`
   sidecars travel with the files. `nomad job dispatch ov-carry-over` re-runs
   it, and a re-run only adds missing keys.
2. Key. A SeaweedFS user `ov-carry-over` in
   `deployments/applications/storage.tf` with GetObject and ListBucket on
   `openviking` and write on the new bucket, so the job cannot change the
   backup. Its key goes to `default/ov-carry-over/seaweedfs` from
   `deployments/applications/secrets.tf`. Remove the user, the key and the
   job once the operator signs off on the carry-over (a follow-up stub, not
   this ticket).
3. Re-index. `new:scripts/ov_carry_over.py`, run by hand like
   `scripts/ov_identity_probe.py` with a token from
   `docs/how-to/call-openviking-from-the-cli.md`, first regenerates
   the summaries of the merged `blogs/` root and each shared source
   directory (addyosmani, anthropic, deepmind, mistral, ollama, openai,
   spotify, uber), whose kept sidecars describe only the blogs half, with
   `POST /api/v1/content/reindex` `mode=semantic_and_vectors`
   `recursive=false`, deepest first and `blogs/` last
   (spike:ov-carry-over/3: at most 33 VLM calls per directory, about 300 in
   all), then calls
   `POST /api/v1/content/reindex` with `mode=vectors_only` on clips, blogs
   and leo. A USER token may re-index its own user namespace. In 0.4.17.1,
   `vectors_only` takes each file's summary from its parent's `.overview.md`
   and makes no VLM call, so ~2900 files cost embeddings only (embark via
   Bifrost), not new summaries. The script then checks the outcome below and
   exits non-zero on the first miss.
4. Tests in `new:cli/tests/test_ov_carry_over.py`, in the style of
   `cli/tests/test_restore_s3.py`: the job copies only the four prefixes, remaps blog-scraper into blogs,
   keeps the marker flags, and fails on a failed check or a missing
   directory; the key is read-only on `openviking`; and the script's
   comparison and "nothing else" logic run against real listings written
   under `tmp_path`.

The blog scraper keeps finding its state. Its dedupe reads exact URL keys
from $HERMES_HOME/state/blog-scraper.json (/opt/data/state/ in the
hermes job), not from OpenViking
(`deployments/applications/services/hermes/skills/productivity/blog-scraper/SKILL.md`),
so the reset does not touch it. The skill's save path moves from
`blog-scraper/<source>/` to `blogs/<source>/` in
`deployments/applications/services/hermes/skills/productivity/blog-scraper/SKILL.md`. ov-clip keeps no state of its own in
OpenViking.

Outcome: the job exits 0, so every old file in the four trees is in the
new bucket at its key with the same hash, empty directories included.
Then the script passes: through the new instance's API, clips and leo list
the same file count as the old bucket, and blogs lists the union of the two
blog trees' files (each old file at its new key; the duplicated article
once), plus any file written since the cutover, which it names; the merged
directories' `.overview.md` mention files from both halves; the re-index reports zero
failures, and a search for the title of each of 10 files chosen at random
per tree returns that file. Outside clips, blogs and leo the new instance holds
only what `ov-fresh-instance` created. The old bucket's object count does
not change. `just pre_commit` and `uv run --directory cli pytest` pass.

## Could invalidate this plan

- A key-for-key copy may not be enough for the new instance. Settled by
  spike:ov-carry-over/1: after a key-for-key copy (markers, `.abstract.md`,
  `.overview.md`) into a fresh v0.4.17.1-9 instance with an empty schema,
  `POST /api/v1/content/reindex` `mode=vectors_only` with a USER token
  indexed every file and directory (failed 0), made no VLM call, and a find
  on each title returned the file. The trees are under
  `viking://user/jasper/resources/` (old bucket keys
  `lab/user/jasper/resources/...`), which a USER token may re-index.
- Merging blog-scraper into blogs. Settled by spike:ov-carry-over/3: after
  a storage copy that remapped blog-scraper into blogs with ignore-existing,
  `content/reindex` `mode=semantic_and_vectors` `recursive=false` on each
  merged directory, deepest first, rewrote only that directory's sidecars
  (VLM calls at most `overview_sample_limit` 32 plus 1 per directory), the
  new overviews named files from both halves, and `vectors_only` then
  indexed every file at its `blogs/` URI with failed 0, no VLM call and no
  row mentioning blog-scraper; find returned each title. The spike also
  showed that directories present only in blog-scraper keep sidecars that
  name `blog-scraper/` URIs, which the copy's text rewrite handles.
