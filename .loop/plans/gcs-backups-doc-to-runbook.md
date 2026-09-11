---
epic = "backups"
priority = 25
summary = "Rewrite docs/gcs-backups.md from a one-time change description into a present-tense operator reference for two live jobs, pin its drift-prone facts to source, and state plainly what nobody has verified."
premise = { Q1 = "writing a restore section requires performing a restore against live data, which is outside a documentation rewrite" }
---
# Ticket: gcs-backups-doc-to-runbook

## 1. Rewrite the GCS backup doc as an operator reference

`docs/gcs-backups.md` describes a change that shipped months ago, in the
future tense, while serving as the only operator reference for two live
backup jobs. Rewrite it to describe the system that exists, pin the facts
that have already drifted, and say plainly which parts of the backup chain
nobody has verified.

## 2. Size / Effort

**M.** One 138-line file rewritten, plus four drift tests. The size is in
verifying every surviving claim against source, not in the prose.

## 3. Triggered by

The operator, rejecting a proposal to defer this: "not out of scope. Fix".
Raised as a non-blocking finding by both review passes on
`backup-swap-memex-for-openviking`.

## 4. Context

`docs/gcs-backups.md:3` opens with a `## Context` heading whose body
(`docs/gcs-backups.md:5`) reads "No off-site backups exist" and "This change
adds two Nomad periodic batch jobs". Both jobs have run nightly since (P1).

The same framing recurs at `docs/gcs-backups.md:94` ("Google provider
added") and `docs/gcs-backups.md:118` ("re-init needed first time"). The
`## Verification` heading at `docs/gcs-backups.md:112` frames its commands as
a post-change check rather than the operating procedure they now are.

The framing has already cost accuracy. `docs/gcs-backups.md:94` states the
Google provider is `hashicorp/google ~>6.0.0`;
`deployments/infrastructure/providers.tf:17` declares `~>7.27.0` (P2). A doc
written as a historical record invites nobody to re-check it, so its claims
rot silently. Three other false claims in this same file were found and fixed
during the previous ticket (P4).

A second gap is not about framing. Nothing in the repo or the cluster shows
that a nightly run has ever succeeded: the jobs are registered and periodic,
but the ACL denies the query that would list their children (P5). The
document also never covers restore. So the write path is unverified and the
read path is undocumented, and the current text says neither.

## 5. Non-goals / out of scope

- No change to any `.tf`, `.hcl`, or job behavior. The cluster is correct;
  the document is what is wrong.
- No change to `deployments/infrastructure/providers.tf`. P2's drift is fixed
  by correcting the doc, not by downgrading the provider.
- No Diátaxis-style split into separate tutorial, how-to and reference pages.
  One operator-facing page stays one page.
- No restore procedure. Writing one honestly means restoring a
  `pgdumpall-*.sql.gz` into a throwaway database and pulling from GCS, which
  is operator work against live data, not a documentation edit. The document
  will say the gap exists (R8); Q1 records why it is deferred.
- Scope of the word "reference": this document covers the WRITE path, how
  backups are configured and run. It is not a recovery runbook and R8 makes
  the document say so, so a reader in an incident is not misled into opening
  it for a restore it does not contain.
- No attempt to prove a nightly run succeeded. That needs an ACL change to
  read job children (P5), which is a cluster permission question and its own
  ticket. R9 bounds what the document may claim instead.
- The `memex` mention at `docs/gcs-backups.md:27` stays. It names the Vault
  per-job credential-path pattern, is still true against
  `deployments/applications/secrets.tf:28`, and has nothing to do with which
  bucket is backed up.

## 6. Requirements & restrictions

- R1. The document stops framing the jobs as NEW. No sentence presents them
  as a change being introduced, and no heading presupposes a reader seeing
  them for the first time. This bans the framing, NOT deploy-time
  instructions: `## Prerequisites` and the `just init` / `just apply` block
  are what an operator still runs to rotate the service-account key or move
  the bucket, so they stay, re-framed as "when you change the backup
  infrastructure". Delivered by the rewrite row in section 7.
- R2. Every factual claim that survives is anchored to the source that states
  it, and verified against it. The one claim already known wrong is
  `docs/gcs-backups.md:94`'s provider version (P2). Delivered by the rewrite
  row in section 7.
- R3. Every doc claim that is mechanically parseable from both the document
  and its source is pinned by a test. The set is twelve facts: the provider
  version, the two node constraints, the six CPU and memory figures carried
  by three tasks (`pgdump`, `upload`, `sync`), and the three container image
  references. Each figure binds to its own task, so swapping two tasks'
  numbers still reddens. Chosen on evidence, not taste: all four of P4's real
  drifts are node constraints and CPU figures, so a test pinning only the
  provider version would have stayed green straight through the commit that
  caused them.
  The document today states its schedules only as prose ("2:00 AM
  Europe/Amsterdam") and carries no cron expression, so the schedule is not
  parseable and no test can pin it. The rewrite therefore states both cron
  expressions literally beside the prose time, which is also what an operator
  reading a schedule wants. Delivered by the four tests in section 8.
- R4. The change ships with a test (`.claude/rules/python-testing.md`).
  Delivered by the `cli/tests/test_backup_coverage.py` row in section 7.
- R5. The prose obeys `.claude/rules/plain-language.md` and the scanner in
  `.claude/rules/slop-scan-for-docs.md`: no em dashes, American spellings, no
  tier-1 slop, no contrastive negation, no participial tails. Checked as a
  gate in section 8.
- R6. Gates pass: `just pre_commit` (`.loop/config.json`), which runs ruff,
  ruff-format and mypy strict over `cli/tests`
  (`.pre-commit-config.yaml:58`). Listed as a gate in section 8.
- R7. Coverage floor: every section of the current document keeps a home in
  the rewrite. The existing file is the floor for what an operator can find,
  so reframing may move or rename a section but may not drop its content.
  A claim that is merely awkward to state in the present tense is not the
  same as one that is false. Delivered by the rewrite row in section 7 and
  checked by eval row 5.
- R8. The document states, in its own text, two absences, each worded as a
  checkable claim about this repo rather than an assertion about history no
  one can verify: this document does not cover restore, and this repo records
  no verified read-back of a backup. It must not say a restore "has never
  been performed", which is the same unverifiable shape R9 forbids in the
  opposite direction. This is the single most reader-facing promise in the
  ticket, so it gets its own producer: the rewrite row in section 7.
- R9. The document makes no unverified end-to-end claim about backup success.
  It may say the jobs are registered, periodic, and what they are configured
  to copy, all of which P1 and the jobspecs support. It may not say backups
  "are taken nightly" or equivalent, which P5 shows nobody can currently
  confirm. This covers the document's H1: a title may name the jobs and the
  schedule they are configured with, because the cron expressions carry that,
  and may not assert that the backups succeed. Delivered by the rewrite row
  in section 7 and checked by eval row 6.

## 7. Code surface

| File | Change |
|---|---|
| `docs/gcs-backups.md` | R1, R2, R7, R8, R9: rewritten whole. Present tense; `## Context` states what the jobs protect and against what; `## Prerequisites` and the deploy block re-framed as infrastructure-change instructions; `## Verification` becomes the operating procedure; `docs/gcs-backups.md:94`'s `~>6.0.0` becomes `~>7.27.0`; a new short section states the restore and read-back gaps. Every surviving claim re-checked against its source. |
| `cli/tests/test_backup_coverage.py` | R3, R4: extended with four drift tests pinning the document's provider version, node constraints, resource figures, and schedules and images to the sources that declare them. Same file as the existing backup drift tests, same subject. |

Nothing else. No `.tf` or `.hcl` file is touched.

## 8. Tests & validation gates

The four new tests join the two already in `cli/tests/test_backup_coverage.py`
(section 7) and follow their shape: parse both sides, assert agreement,
self-check that neither parser returned nothing.

- `test_backup_doc_names_the_google_provider_version` (R3) — parse the
  `hashicorp/google` version constraint from `docs/gcs-backups.md`, parse
  `version` from the `google` block at
  `deployments/infrastructure/providers.tf:17`, assert they match.
  Fails-when: the doc says `~>6.0.0` against the declared `~>7.27.0`, which
  is the state on `main` today, so it reddens against the pre-change tree.
- `test_backup_doc_matches_jobspec_node_constraints` (R3) — parse the node
  named for each job from the doc, and the `constraint` value from each of
  `deployments/infrastructure/services/backup-postgres.hcl` and
  `deployments/infrastructure/services/backup-minio.hcl`.
  Fails-when: the doc says `firebat` for the postgres job, the exact drift
  P4 records.
- `test_backup_doc_matches_jobspec_resources` (R3) — parse the six CPU and
  memory figures from the doc and from the three `resources` blocks, keyed by
  task name so each figure binds to its own task.
  Fails-when: the doc says 1000 MHz for the `pgdump` task against `cpu = 500`,
  a drift P4 records; and, because the figures are keyed rather than compared
  as a set, when the `pgdump` and `sync` numbers are swapped.
- `test_backup_doc_matches_jobspec_schedules_and_images` (R3) — parse both
  cron expressions and all three container image references from the doc and
  the jobspecs. The crons are parseable only because R3 requires the rewrite
  to state them literally; against the document as it stands today this test
  finds nothing in the doc and fails, which is the correct behavior for a
  test written before its subject exists.
  Fails-when: a cron or image is edited in one place only. The third image is
  the `upload` task's rclone reference at
  `deployments/infrastructure/services/backup-postgres.hcl:54`, which the doc
  names at `docs/gcs-backups.md:58` and which a two-image test would miss.

Every test fails if either of its parsers finds nothing, so a parser broken
by the rewrite cannot pass vacuously.

Gates, discovered from `.loop/config.json` and `.pre-commit-config.yaml`:

- `just pre_commit` (R6) — the configured gate.
- `uv run --project cli pytest cli/tests/test_backup_coverage.py` — all six
  tests, run directly during implementation.
- The slop scan in `.claude/rules/slop-scan-for-docs.md` (R5), run over the
  rewritten file: em-dash count, ` -- ` in prose, British spellings, tier-1
  slop, contrastive negation, participial tails.
- The scenario set in `.loop/evals/gcs-backups-doc-to-runbook.md` is the
  acceptance layer above these gates, including row 5 (R7) and row 6 (R9).

No `terraform plan` gate. Nothing in this ticket reaches Terraform.

## 9. Risk assessment

Blast radius: one documentation file and one test file. No runtime effect.
Reversible by reverting the commit.

Failure modes, likeliest first:

1. The rewrite drops a fact an operator needs mid-incident. Reframing invites
   cutting. R7 makes the existing file the coverage floor and gives it a
   producer, rather than leaving it as an intention here.
2. The rewrite asserts something newly false while making prose flow. Every
   surviving claim is re-anchored (R2), which is the bulk of the work, and
   the R3 tests hold the mechanically checkable subset.
3. The document reads as a recovery runbook and is opened as one during an
   incident, when it covers only the write path. R8 makes the document say
   so in its own text; section 5 bounds the word.
4. The doc drifts again. R3 pins twelve facts across four tests. It does not
   pin the prose, and no test can.

Not a risk: the cluster. No executable file changes.

## 10. Subtickets

None. One file rewritten plus four tests in one file fits a single iteration.

## 11. Open questions

- Q1 `restore-procedure-absent`. The file documents how backups are written
  and never how they are read back, and P5 shows no nightly run has been
  confirmed either. Writing the restore section means actually restoring a
  `pgdumpall-*.sql.gz` into a throwaway database and pulling from GCS: real
  operator work against live data, well beyond a doc rewrite. Resolved for
  this ticket: keep the restore out (section 5), and make the document state
  the gap (R8) so a reader is not misled into thinking the omission is their
  own. Recommendation for the follow-up: one ticket that performs a restore
  and documents it, and which will need the ACL question in P5 settled to
  confirm the backups it restores from.

## Premises / assumptions

- **P1.** The two jobs are registered and periodic, so the present tense is
  the accurate one for their configuration. probe: `nomad job status
  backup-minio` against the cluster returned:

  ```
  Submit Date          = 2026-07-07T10:02:54+02:00
  Status               = running
  Periodic             = true
  ```

- **P2.** The doc's Google provider version is wrong. Anchors:
  `docs/gcs-backups.md:94` states `~>6.0.0`;
  `deployments/infrastructure/providers.tf:17` declares `~>7.27.0`.
- **P3.** Every other structural fact in the doc is correct as of this tree,
  so the work is reframing plus one correction rather than a re-derivation.
  The plan reviewer checked all 138 lines against source independently and
  found exactly the one false claim P2 names. Anchors, covering each family
  of claim the document makes: the four `google_*` resources at
  `deployments/infrastructure/storage.tf:6`, `:22`, `:27` and `:33`; the four
  Vault secrets at `deployments/infrastructure/secrets.tf:301`, `:317`,
  `:332` and `:348`; the `age = 180` lifecycle rule at
  `deployments/infrastructure/storage.tf:13`; the two `nomad_job` resources
  at `deployments/infrastructure/services.tf:701` and `:713`, the host
  volumes those jobs' data lives on at
  `deployments/infrastructure/services.tf:13` and `:33`, and the postgres
  host at `deployments/infrastructure/services.tf:707`; the hardcoded
  `secret/data/` prefix that makes the doc's `secret/data/default/...` paths
  resolve, in
  `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`
  (`deployments/infrastructure/secrets.tf:3` sets the mount from
  `var.secret_mount`, which has no default, so the literal name is not
  derivable from the repo alone); the crons `0 2 * * *`
  (`deployments/infrastructure/services/backup-postgres.hcl:7`) and
  `0 3 * * *` (`deployments/infrastructure/services/backup-minio.hcl:7`); the
  images at `deployments/infrastructure/services/backup-postgres.hcl:26` and
  `deployments/infrastructure/services/backup-minio.hcl:22`; the Vault policy
  template at
  `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`; the
  `just init` and `just apply` recipes at
  `deployments/infrastructure/justfile`; the bucket set at
  `deployments/applications/storage.tf:2`; the node names at
  `bootstrap/inventory/cluster.ini:2`; and the two variables at
  `deployments/infrastructure/variables.tf:6` and `:11`.
- **P4.** This file drifts unattended, so pinning its parseable facts is
  worth four tests. Evidence: the immediately preceding ticket found and
  fixed four false claims in it, at `docs/gcs-backups.md:55` and
  `docs/gcs-backups.md:72` (both node constraints) and
  `docs/gcs-backups.md:57` and `docs/gcs-backups.md:62` (CPU figures), each
  traced by the reviewers to a commit that moved the code and left the doc
  alone. R3 pins that exact family.
- **P5.** Nobody can currently show a nightly run succeeded, so the document
  must not claim one did. probe: `nomad job status backup-minio` printed its
  children summary but the follow-up allocation query returned
  `Error querying job: Unexpected response code: 403 (Permission denied)`,
  and the plan reviewer independently reproduced the denial on
  `nomad job allocs backup-postgres` and on
  `/v1/jobs?prefix=backup-postgres%2F`. The ACL permits reading the job and
  denies reading its children.
- **P6.** No RUNTIME code reads this document, so the rewrite cannot change
  cluster behavior. It can and will break gates: the four tests R3 adds parse
  this file, so a rewrite that moves a pinned fact reddens them by design,
  and the writing-style scan reads it too. Evidence: the previous ticket's
  reviewers grepped the repo for references to this document's content and
  found none outside `.loop/`, and this ticket's plan reviewer repeated the
  sweep. UNCERTAIN in the sense that it rests on an absence.
