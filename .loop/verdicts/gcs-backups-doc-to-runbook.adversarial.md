---
verdict: pass
tree: 8072f87da51702cfc9a1d18ca8d740654fa46530
---

# Adversarial review — cycle 3 (final)

Scope binding omitted deliberately: my briefing carried no 64-hex scope
digest, and the instructions forbid computing one myself. The verdict
therefore falls back to the whole-tree binding, which is stricter.

Deterministic floor: `loopctl verify-eval-substance gcs-backups-doc-to-runbook`
returns `valid`, exit 0, no advisories. `loopctl verify --expect-tree
8072f87da51702cfc9a1d18ca8d740654fa46530` exits 0, so this review stands in
the checkout it was asked to review.

Gates re-run at this fingerprint, not trusted from the stale cycle-2 stamp:

- `just pre_commit` — exit 0, all 13 hooks pass (Ruff lint, Ruff format,
  Mypy strict on `cli/`, Terraform validate, Nomad fmt).
- `uv run pytest` — 511 passed, 21 deselected, 0 failed.
- Trust stamp refreshed to `8072f87d...` at
  `.loop/scratch/gcs-backups-doc-to-runbook.adversarial/trust-stamp.json`.

## a. The new `docs/gcs-backups.md:170` sentence is true

`docs/gcs-backups.md:169 = than the default. Without it the query returns
`403 Permission denied`, so the`
`docs/gcs-backups.md:170 = `gsutil ls` commands are the only check here that
does not go through Nomad at`

I read every command in the block it refers to. Six are `nomad`:
`nomad job periodic force` twice (:152-153), `nomad job status` twice
(:156-157), `nomad alloc logs` twice (:160-161). Two are not: the
`gsutil ls` pair at :164-165. `gsutil` talks to the GCS API under
Application Default Credentials, which this same file sets up at :34, and
the bucket is a `google_storage_bucket` Terraform creates (:12-13), so
reading it needs no Nomad. The claim holds exactly.

Widening "here" from the block to the whole file does not break it either.
The only other non-Nomad commands in the file are
`gcloud auth application-default login` at :34 and :42, which are auth
steps rather than checks. `just apply` at :51 registers the Nomad jobs, so
it does go through Nomad.

The fix is the right one, not a paraphrase. The cycle-2 claim keyed on the
token ("does not need such a token"), which `nomad job status` falsified.
The new claim keys on whether the command talks to Nomad at all, and
`nomad job status` plainly does:

`docs/gcs-backups.md:23 = - **Run outcomes are not visible.** `nomad job
status` shows both jobs`

That also makes the sentence robust to the token question the old one
hinged on. I re-probed Nomad this cycle and this shell still reports
`No token present`, so I cannot reproduce the default-token case either
way. The new wording is true under both.

**ADV-11: fixed-verified.**

Residual, advisory, no fix required: the "so" at :169 is a loose
connective. The 403 does not cause the `gsutil ls` pair to be the only
non-Nomad check; that is true independent of any token. The intended
reading, that gsutil is the check which sidesteps a limited Nomad path, is
sound, and :23-26 states the token facts precisely 145 lines earlier. The
reader is not misled.

## b. The new `_hcl_blocks` docstring matches real behavior

`cli/tests/test_backup_coverage.py:124 =     """Bodies of `resources {` or
`config {` blocks, keyed by the owning task.`

Probed the real function against the real jobspecs rather than reading the
regex:

- `resources` on `backup-postgres.hcl` -> keys `['pgdump', 'upload']`,
  bodies `cpu = 500 / memory = 512` and `cpu = 200 / memory = 256`.
- `config` on the same -> keys `['pgdump', 'upload']`, images
  `postgres:18` and `rclone:latest`.
- `resources` and `config` on `backup-minio.hcl` -> key `['sync']`.
- `task` on both -> `{}`. The cycle-2 falsehood is gone, and gone because
  the regex at :139 demands an unlabelled block, which `task "x" {` is not.

The docstring names exactly the two keywords any caller passes, and there
are only two callers:

`cli/tests/test_backup_coverage.py:204 =         blocks = _hcl_blocks(path,
"resources")`
`cli/tests/test_backup_coverage.py:237 =         configs = _hcl_blocks(path,
"config")`

I re-attacked the `owner`/`task` narrowing I cleared at cycle 2 rather than
rubber-stamping it. Fed a synthetic jobspec with a `task "upload" {` string
sitting inside `pgdump`'s `resources` body: the block stays keyed to
`pgdump` and `upload` keeps its own. `owner` is captured at block-open
(`cli/tests/test_backup_coverage.py:140 =             owner = task`) and
never re-read, so "keyed by the owning task" is accurate, including under
the case that would break it.

**ADV-14: fixed-verified.**

Bounded non-finding: a `resources {` block at group level, after the last
task closes, is attributed to that last task. Nomad HCL permits neither
`resources` nor `config` outside a `task`, so it is unreachable for both
callers. Not scored.

## c. Controls re-run against this tree

All three control sets re-run from
`.loop/scratch/gcs-backups-doc-to-runbook.adversarial/`. Your claim holds.

- Unmutated tree GREEN: all four baselines in set 1, both in set 2.
- **C1-C6 all RED**, each with the message its own drift should produce.
- **X1 RED** — pgdump/upload figures swapped *inside* the postgres section:
  "task `pgdump` sets 500 MHz / 512 MB, which the bullet for that task
  does not state." The intra-section binding holds.
- X2-X5, X7-X10 RED. Y1, Y2, Y4-Y10 RED.
- Y11-Y14 RED and loud ("parser found no cpu/image ... cannot be checked").
  ADV-7's downgrade holds: the one-line-HCL reformat gives a false red, never
  a silent pass.
- X6 GREEN — ADV-6, known. The node check is section membership, not
  placement. The plan's stated Fails-when for that test
  (`.loop/plans/...:159-160`) is "the doc says `firebat` for the postgres
  job", which C2 reddens. Inside the contract. Advisory.
- Y3 GREEN — reordering the task bullets. Correct: each bullet still owns
  its figures. Not a defect.

Every deterministic eval row's stated Fails-when is exercised and reddens:
row 3 by C1/X9, row 4 by C2/C3/C4/C5/X2/X7/X8.

## New finding this cycle, checked because no gate exercises it

`cli/tests/test_backup_coverage.py:96 = # Four claims in that runbook have
already gone stale under commits that moved`

A historical claim in a comment, which a green stamp is silent about. I
checked it against git history instead of scoring it from the diff.
It is exact:

- `3eb60ae` moved `pgdump` cpu 1000 -> 500 and `upload` cpu 500 -> 200 in
  the jobspec and left the doc alone.
- `4b0af46` moved both node constraints to `radxa-dragon-q6a` and left the
  doc alone.
- `be88f27` repaired all four in the doc.

Four claims, "both node constraints and two CPU figures", and the comment
correctly excludes the memory figures, which never drifted (512/256/512
throughout). Warranted under `minimal-comments`: a reason and a measurement
no source can state. **ADV-13: verified-true.**

## Settled findings the diff does not touch

- ADV-1, ADV-2, ADV-3, ADV-5, ADV-8 — no change in scope, still hold as
  fixed-verified at cycle 2; re-confirmed by this cycle's green gate, green
  baselines and red X1/Y1.
- ADV-6 — no change in scope, still holds, advisory, inside the plan's
  stated Fails-when.
- ADV-7 — no change in scope, still holds, advisory-downgraded, re-confirmed
  by Y11-Y14.
- ADV-9 — no change in scope, still holds. `403 Permission denied` unchanged
  at :25 and :169; the cycle-2 anonymous-case caveat is unchanged.
- ADV-10 — no change in scope, still holds. `docs/gcs-backups.md:3` still
  reads "copy cluster data off-site" rather than "are configured to copy".
  The file self-bounds at :23-26. Outside eval row 6's stated Fails-when.
  Advisory.

## Unverified, deliberately not scored

ADV-12, `docs/gcs-backups.md:160`: `nomad alloc logs <alloc-id>` with a
`# pgdump task` comment but no task argument, on a two-task allocation. This
is unchanged floor content, a context line in the diff carried from the
pre-change file. Confirming it needs a live two-task allocation, and this
shell reports `No token present` with `nomad job allocs backup-postgres`
returning 403. **Marked unverified, not scored.**

## Scope

Two non-harness files change, both named in the plan's file table
(`.loop/plans/...:138-139`): `docs/gcs-backups.md` rewritten whole, and
`cli/tests/test_backup_coverage.py` extended purely additively after line 89,
reusing the file's existing `REPO_ROOT`, `JOBSPEC` and `_require`. No new
test file, no new dependency, no adjacent code improved. Every changed line
traces to the ticket.

Doc scanner re-run on the edited file: 0 em dashes, no ` -- `, no semicolon
splice, no tier-1 slop, no spatial copula, no British spellings, no
TODO/FIXME. Line lengths over 80 are pre-existing bullet style and this
rewrite reduced them from 22 to 18; the repo has no
`.claude/rules/markdown-formatting.md` to enforce a wrap.

## Verdict

**pass.** Both fixes are real and correct, not paraphrases. The controls
reproduce the cycle-2 picture exactly against the new tree, the unmutated
tree is green, and the gates pass at this fingerprint. Four advisories
(ADV-6, ADV-7, ADV-9, ADV-10, plus the loose "so" at :169) and one
unverifiable floor line (ADV-12) remain, none of which reaches an eval row's
Fails-when or blocks the commit.
