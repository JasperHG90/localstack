---
verdict: pass
tree: 8072f87da51702cfc9a1d18ca8d740654fa46530
---

# Documentation freshness: gcs-backups-doc-to-runbook, cycle 3 (final)

Both required fixes from cycle 2 are applied and both are true, not merely
different. No documented surface in this diff is left stale. Pass.

## Why the scope binding is absent

No `bound_paths:`, `scope:`, or `citations:` lines. The briefing carried no
64-hex scope digest, and the harness this pass runs under computes none:
`grep -n scope` over
`/home/vscode/.claude/plugins/cache/loop-harness/loop-harness/1.9.0/scripts/loopctl.py`
returns nothing, and its subcommand list has no digest command. Writing a
digest I computed myself would bind the verdict to a path set the gate never
agreed to. Omitting the three lines falls back to whole-tree binding, which is
stricter, so the omission is safe. For the record, the source paths in the
reviewed diff are `docs/gcs-backups.md` and `cli/tests/test_backup_coverage.py`;
the rest of the diff is `.loop/` harness artifacts, which the fingerprint
builder strips.

## The change under review

Two lines moved since tree `95865268343f936c56548771f9c95d4559067473`, as the
briefing stated. Both are inside surfaces I flagged. Nothing else in the doc
contradicts them.

## a. RF-A is true, not merely different

`docs/gcs-backups.md:170` now reads:

    `gsutil ls` commands are the only check here that does not go through Nomad at

"Does not go through Nomad at all" is the stronger claim, so I checked it
three ways rather than reading it.

**Every command in the block it quantifies over.** The referent of "here" is
the fenced block at `docs/gcs-backups.md:151-165`. It holds eight commands.
Six are Nomad:

    docs/gcs-backups.md:152 = nomad job periodic force backup-postgres
    docs/gcs-backups.md:153 = nomad job periodic force backup-minio
    docs/gcs-backups.md:156 = nomad job status backup-postgres
    docs/gcs-backups.md:157 = nomad job status backup-minio
    docs/gcs-backups.md:160 = nomad alloc logs <alloc-id>        # pgdump task
    docs/gcs-backups.md:161 = nomad alloc logs <alloc-id> upload # upload task

Two are not:

    docs/gcs-backups.md:164 = gsutil ls gs://<bucket>/postgres/
    docs/gcs-backups.md:165 = gsutil ls gs://<bucket>/minio/openviking/

The partition is exact, so "only" holds. This is what the cycle-2 wording got
wrong and this one gets right: `nomad job status` at :156-157 is a counter-
example to "the only check that does not need such a token" and is not a
counter-example to "the only check that does not go through Nomad."

**`gsutil` genuinely involves no Nomad path.** A repo-wide grep for `gsutil`,
excluding `.git/` and `.loop/`, returns three hits and all three are in this
document (`:164`, `:165`, `:170`). There is no wrapper script, no justfile
recipe, and no `nomad exec` that routes it. Its credentials come from the
operator's own ADC, which this same document sets up:

    docs/gcs-backups.md:34 = gcloud auth application-default login
    docs/gcs-backups.md:38 = `~/.config/gcloud/application_default_credentials.json`, which the Google

That is a different credential from the one Nomad injects into the job, which
Vault templates out of the jobspec:

    deployments/infrastructure/services/backup-postgres.hcl:63 = {{ with secret "${gcs_secret}" }}{{ .Data.data.service_account_json }}{{ end }}

So neither the transport nor the auth touches Nomad. "At all" is earned.

**The doc no longer contradicts itself.** The RF-A sentence and the caveat
section now say the same thing about the ACL:

    docs/gcs-backups.md:24 = registered and periodic, but the ACL denies the query that lists their
    docs/gcs-backups.md:168 = Listing a job's child allocations requires a Nomad token with more privilege

Both scope the denial to the child-run query and neither closes `nomad job
status`. An operator reading :170 is no longer told to skip the one Nomad-side
signal the ACL leaves open, which was DOC-8's whole cost. DOC-8 resolved.

## b. RF-B matches the function's real behavior

`cli/tests/test_backup_coverage.py:124` now reads:

    """Bodies of `resources {` or `config {` blocks, keyed by the owning task.

I re-attacked this by calling the function, not by reading it. Loading the
module and invoking `_hcl_blocks` against both jobspecs:

    backup-postgres.hcl  resources -> ['pgdump', 'upload']
    backup-postgres.hcl  config    -> ['pgdump', 'upload']
    backup-postgres.hcl  task      -> []
    backup-minio.hcl     resources -> ['sync']
    backup-minio.hcl     config    -> ['sync']
    backup-minio.hcl     task      -> []

Both halves of the docstring hold. Bodies are real (`resources` for `pgdump`
returns `cpu    = 500` / `memory = 512`, matching
`deployments/infrastructure/services/backup-postgres.hcl:45-46`), and the keys
are the owning tasks. The `task "x" {` capability the cycle-2 docstring still
advertised is gone from both the code and the text, which is the correct
pairing. Those two keywords are the only ones any caller passes:

    cli/tests/test_backup_coverage.py:204 =         blocks = _hcl_blocks(path, "resources")
    cli/tests/test_backup_coverage.py:237 =         configs = _hcl_blocks(path, "config")

DOC-9 resolved.

## c. Writing-rules re-scan

Run over the whole of `docs/gcs-backups.md`, not just the changed line.

| Check | Result |
|---|---|
| Em dashes | 0 |
| ` -- ` in prose | 0 |
| Prose semicolon splices (outside fenced and inline code) | 0 |
| Tier-1 slop | 0 |
| British spellings | 0 |
| Smart quotes | 0 |
| Self-narration, throat-clearing, hedging seesaw | 0 |
| Participial tails, emphasis crutches, spatial copula | 0 |
| `not just` / `not only X but also Y` | 0 |

Your count matches mine. The new sentence is active throughout ("requires",
"returns", "They show", "writes") and every line of it wraps under 80 chars.

One judgment-level item, surfaced rather than fixed, as
`.claude/rules/slop-scan-for-docs.md` directs for low-confidence categories:

    docs/gcs-backups.md:171 = all. They show what is in the bucket, not which run put it there: `nomad job

"Y, not X" is the bare-trailing contrastive form. I am keeping it. The rule's
own test is whether the contrast is load-bearing and survives removal, and
here it is the sentence's entire job: it is what stops the doc claiming a
particular night succeeded, which is R9. Cutting the "not" half would leave
"They show what is in the bucket" and quietly delete the constraint.

Two scan notes that are not findings against this diff. The ASCII arrows at
`docs/gcs-backups.md:68-71` are resource-to-path mapping notation in a list,
not prose connectors, and they are unchanged context lines from before this
ticket. And `.claude/rules/markdown-formatting.md`, which Layer 2 item 1
cites, does not exist in this repo, so the 80-char wrap has no local authority;
the over-80 lines at `:72-79`, `:88-96`, `:104-106` and `:145-146` all predate
this diff regardless.

## d. Settled findings DOC-1 through DOC-7

Re-attacked where the two changed lines could reach them; absence claims
otherwise.

**DOC-1 (overturned, cycle 2) — IN SCOPE, re-attacked, stays overturned.**
RF-A rewrote the sentence immediately before it, so I re-opened the anchor.
`docs/gcs-backups.md:171-172` is byte-identical to what I overturned on, and
the jobspec still backs it: `backup-postgres.hcl:29` builds
`pgdumpall-$(date +%Y-%m-%d).sql.gz` at run time and `:56` copies
`/alloc/data/` to `:gcs:${gcs_bucket}/postgres/`, so a forced run and an 02:00
run do produce the same object name under the same prefix. RF-A added no new
inference on top.

**DOC-2 (overturned, cycle 2) — IN SCOPE, re-attacked, stays overturned.**
RF-B edited the same function. Grep for `type: ignore`, `noqa`,
`pytest.mark.skip`, `pytest.mark.xfail` and `fmt: off` across
`cli/tests/test_backup_coverage.py` returns nothing, and `Mypy (strict, cli/)`
passes. The docstring narrowing introduced no suppression.

**DOC-3 (overturned, cycle 2) — IN SCOPE, re-attacked, stays overturned.**
RF-B touched the parser DOC-3 depends on, so I re-ran the whole cycle-2
mutation set against this tree rather than trusting the prior result. Control:
all four green. Six mutations, each reddening exactly one test: intra-section
`pgdump`/`upload` figure swap reddens the resources test; intra-section
`pgdump`/`upload` image swap reddens the schedules-and-images test;
cross-section `pgdump`/`sync` figure swap reddens the resources test; doc-only
provider bump reddens the provider test; doc-only node drift to `firebat`
reddens the constraints test; dropping the cron from the doc reddens the
schedules test. R3's task-keying promise still holds as written.

**DOC-4 (overturned, cycle 2) — IN SCOPE, re-attacked, stays overturned.**
RF-A rewrote the sentence that once carried the splice. The rule's own command
finds zero prose semicolon splices in the file. The RF-A sentence uses a period
after "the default" and a colon after "put it there", both correct.

**DOC-5 (advisory) — no change in scope, still holds.** RF-A changed one line
at :170 and shifted no line numbers above it, so `docs/gcs-backups.md:7` and
`:9` are untouched. Re-opened the anchors anyway:

    deployments/infrastructure/services.tf:13 =     value     = "firebat"
    deployments/infrastructure/services.tf:33 =     value     = "orangepi4a"

Both still correct, still pinned by no test. Advisory stands, not a blocker.

**DOC-6 (confirmed-correct) — no change in scope, still holds.** Neither
changed line states a version, a figure, an image, a cron or a path. Re-opened
the two anchors nearest the change anyway:

    deployments/infrastructure/providers.tf:17 =         version = "~>7.27.0"
    deployments/infrastructure/storage.tf:13 =       age = 180

Both match the doc at `:130` and `:146`.

**DOC-7 (confirmed-correct) — no change in scope, still holds.** RF-A replaced
a sentence inside `## Operating the jobs` and removed no command from the block
above it; RF-B cut half a sentence from a test docstring, which is not
operator-facing content. The section list is intact: `:15`, `:28`, `:54`,
`:63`, `:113`, `:132`, `:148` plus the six `###` subsections. The coverage
floor is unmoved.

## Gates, re-run rather than trusted

Per the reviewer-brief, re-run against this tree, not read from a stamp.

- `just pre_commit`: exit 0 in 4.6s, all 13 hooks Passed, including
  `Ruff (lint)`, `Ruff (format)` and `Mypy (strict, cli/)`.
- `uv run --project cli pytest cli/tests/test_backup_coverage.py -q`:
  6 passed in 0.02s.
- Mutation set: control green, six mutations each reddening exactly one test.

No trust stamp written. At 4.6s the gate is far under the brief's one-minute
threshold and mutates nothing outside the worktree, so stamping it would only
tell a later cycle to skip a five-second check.

## Eval rows re-checked

RF-A sits inside the sentence eval row 6 governs, so I re-read the rows that
bear on the changed text.

- Row 1 (no change-framing): the three banned strings are absent.
- Row 2 (deploy commands survive): `gcloud auth application-default login` at
  `:34` and `:42`, `just init` / `just apply` at `:50-51`.
- Row 6 (claims no more than anyone can confirm): no "are taken nightly", no
  "runs every night", no assertion of end-to-end success anywhere. The H1
  `# Nightly GCS Backup Jobs` names the configured schedule, which R9 and the
  row both permit. `:171` actively disclaims the outcome the row forbids.
- Row 7 (names its own gaps): the R8 wording is at `:20-26` and the forbidden
  overreach ("has never been performed") appears nowhere.

## Findings

| ID | Severity | Status |
|---|---|---|
| DOC-8 | was required-fix | resolved |
| DOC-9 | was required-fix | resolved |
| DOC-1 to DOC-4 | overturned | re-attacked, stay overturned |
| DOC-5 | advisory | unchanged, non-blocking |
| DOC-6, DOC-7 | confirmed-correct | unchanged |
| DOC-12 | informational | writing-rules scan clean; one contrast surfaced, kept |
| DOC-13 | informational | gates and mutation set green at this tree |
| DOC-14 | informational | eval rows 1, 2, 6, 7 hold |

No required fixes. No reader of `docs/gcs-backups.md` at this tree would be
misled by a stale claim, and no docstring in
`cli/tests/test_backup_coverage.py` describes behavior the code does not have.

Ledger updated at
`.loop/scratch/gcs-backups-doc-to-runbook.documentation/findings.json`.
