---
epic = "backups"
priority = 25
summary = "Rewrite docs/gcs-backups.md from a one-time change description into a runbook for two jobs that have been running for months, and pin its drift-prone facts to the source."
---
# Ticket: gcs-backups-doc-to-runbook

## 1. Rewrite the GCS backup doc as a runbook

`docs/gcs-backups.md` describes a change that shipped months ago, in the
future tense, while serving as the only operator reference for two live
backup jobs. Rewrite it to describe the system that exists, and pin the facts
that have already drifted.

## 2. Size / Effort

**M.** One 138-line file rewritten, plus one drift test. The size is in
verifying every surviving claim against source, not in the prose.

## 3. Triggered by

The operator, rejecting a proposal to defer this: "not out of scope. Fix".
Raised as a non-blocking finding by both review passes on
`backup-swap-memex-for-openviking`.

## 4. Context

`docs/gcs-backups.md:3` opens with a `## Context` heading whose body
(`docs/gcs-backups.md:5`) reads "No off-site backups exist" and "This change
adds two Nomad periodic batch jobs". Both jobs have run nightly since; the
most recent `backup-minio` submission predates this ticket by months, and the
job reports `Status = running` with 161 dead children.

The same framing recurs at `docs/gcs-backups.md:94` ("Google provider
added"), and `docs/gcs-backups.md:118` ("re-init needed first time"). The
`## Verification` heading at `docs/gcs-backups.md:112` frames its commands as
a post-change check rather than the operating procedure they now are.

The framing has already cost accuracy. `docs/gcs-backups.md:94` states the
Google provider is `hashicorp/google ~>6.0.0`; `deployments/infrastructure/providers.tf:16`
declares `~>7.27.0` (P2). A doc written as a historical record invites nobody
to re-check it, so its claims rot silently. Three other false claims in this
same file were found and fixed during the previous ticket
(`backup-swap-memex-for-openviking`): a wrong node for both jobs, and wrong
CPU figures for two tasks.

## 5. Non-goals / out of scope

- No change to any `.tf`, `.hcl`, or job behavior. The cluster is correct;
  the document is what is wrong.
- No change to `deployments/infrastructure/providers.tf`. P2's drift is fixed
  in the doc by correcting the doc, not by downgrading the provider.
- No Diátaxis-style split into separate tutorial, how-to and reference pages.
  One operator-facing page stays one page.
- No new content about backup *restore*, which the file has never covered.
  Absent, and out of scope here; note it in section 11 rather than inventing
  a procedure that has never been run.
- The `memex` mention at `docs/gcs-backups.md:27` stays. It names the Vault
  per-job credential-path pattern, is still true against
  `deployments/applications/secrets.tf:28`, and has nothing to do with which
  bucket is backed up.

## 6. Requirements & restrictions

- R1. The document describes the system in the present tense. No sentence
  frames the jobs as a change being introduced, and no heading
  (`## Context`, `## Verification`) presupposes a reader who is about to
  apply them. Delivered by the rewrite row in section 7.
- R2. Every factual claim that survives is anchored to the source that states
  it, and verified against it. The claims already known wrong are
  `docs/gcs-backups.md:94`'s provider version (P2). Delivered by the rewrite
  row in section 7.
- R3. The provider version claim is pinned by a test, not just corrected once.
  It is the third drift found in this file in one week, so a one-time fix
  restores accuracy without preventing the next one. Delivered by
  `test_backup_doc_names_the_google_provider_version` in section 8.
- R4. The change ships with a test (`.claude/rules/python-testing.md`).
  Delivered by the `cli/tests/test_backup_coverage.py` row in section 7.
- R5. The prose obeys `.claude/rules/plain-language.md` and the scanner in
  `.claude/rules/slop-scan-for-docs.md`: no em dashes, American spellings, no
  tier-1 slop, no contrastive negation, no participial tails. Checked as a
  gate in section 8.
- R6. Gates pass: `just pre_commit` (`.loop/config.json`), which runs ruff,
  ruff-format and mypy strict over `cli/tests`
  (`.pre-commit-config.yaml:58`). Listed as a gate in section 8.

## 7. Code surface

| File | Change |
|---|---|
| `docs/gcs-backups.md` | R1, R2: rewritten whole. Present tense throughout; `## Context` becomes a statement of what the jobs protect and against what; `## Verification` becomes the operating procedure; `docs/gcs-backups.md:94`'s `~>6.0.0` becomes the declared `~>7.27.0`. Every surviving claim re-checked against its source. |
| `cli/tests/test_backup_coverage.py` | R3, R4: extended with a drift test pinning the provider version the doc states to the one `deployments/infrastructure/providers.tf` declares. Same file as the existing backup drift tests, same subject. |

Nothing else. No `.tf` or `.hcl` file is touched.

## 8. Tests & validation gates

The new test joins the two already in `cli/tests/test_backup_coverage.py`
(section 7) and follows their shape: parse both sides, assert agreement,
self-check that neither parser returned nothing.

- `test_backup_doc_names_the_google_provider_version` (R3, R4) — parse the
  `hashicorp/google` version constraint out of `docs/gcs-backups.md`, parse
  the `version` string from the `google` block in
  `deployments/infrastructure/providers.tf`, assert they match.
  Fails-when: the doc says `~>6.0.0` while the provider declares `~>7.27.0`,
  which is the state on `main` today, so the test reddens against the
  pre-change tree. Also fails if either parser finds nothing.

Gates, discovered from `.loop/config.json` and `.pre-commit-config.yaml`:

- `just pre_commit` (R6) — the configured gate.
- `uv run --project cli pytest cli/tests/test_backup_coverage.py` — the three
  tests, run directly during implementation.
- The slop scan in `.claude/rules/slop-scan-for-docs.md` (R5), run over the
  rewritten file: em-dash count, ` -- ` in prose, British spellings, tier-1
  slop, contrastive negation, participial tails.
- The scenario set in `.loop/evals/gcs-backups-doc-to-runbook.md` is the
  acceptance layer above these gates.

No `terraform plan` gate. Nothing in this ticket reaches Terraform.

## 9. Risk assessment

Blast radius: one documentation file and one test. No runtime effect.
Reversible by reverting the commit.

Failure modes, likeliest first:

1. The rewrite drops a fact an operator needs mid-incident. Reframing invites
   cutting, and a claim that is merely *unfashionable* to state is not the
   same as one that is false. Mitigated by treating the existing file as the
   floor for coverage: every section keeps a home.
2. The rewrite asserts something newly false while making prose flow. Every
   surviving claim is re-anchored (R2), which is the bulk of the work.
3. The doc drifts again next month. R3 pins the one fact already proven to
   drift. It does not pin the rest, and cannot.

Not a risk: the cluster. No executable file changes.

## 10. Subtickets

None. One file rewritten plus one test fits a single iteration.

## 11. Open questions

- Q1 `restore-procedure-absent`. The file documents how backups are written
  and never how they are read back. A backup nobody has restored is a
  hypothesis, not a backup. Writing that section means actually restoring a
  `pgdumpall-*.sql.gz` into a throwaway database and an `rclone` pull from
  GCS, which is real operator work against live data and well beyond a doc
  rewrite. Recommendation: keep it out of this ticket, and note the absence
  in the document itself so a reader is not misled into thinking the gap is
  their own. Raise a follow-up ticket to do the restore and write it up.

## Premises / assumptions

- **P1.** The two jobs are live, not pending, so the present tense is the
  accurate one. probe: `nomad job status backup-minio` against the cluster
  returned:

  ```
  Submit Date          = 2026-07-07T10:02:54+02:00
  Status               = running
  Periodic             = true
  Children Job Summary: Dead 161
  ```

- **P2.** The doc's Google provider version is wrong. Anchors:
  `docs/gcs-backups.md:94` states `~>6.0.0`;
  `deployments/infrastructure/providers.tf:16` declares `~>7.27.0`.
- **P3.** The remaining structural facts in the doc are correct as of this
  tree, so the rewrite is reframing plus one correction rather than a
  wholesale re-derivation. Anchors checked one by one: the four
  `google_*` resources at `deployments/infrastructure/storage.tf:6`, `:22`,
  `:27` and `:33`; the four Vault secrets at
  `deployments/infrastructure/secrets.tf:301`, `:317`, `:332` and `:348`; the
  `age = 180` lifecycle rule at `deployments/infrastructure/storage.tf:13`;
  the crons `0 2 * * *` (`deployments/infrastructure/services/backup-postgres.hcl:7`)
  and `0 3 * * *` (`deployments/infrastructure/services/backup-minio.hcl:7`);
  the Vault policy template at
  `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`; and
  the two variables at `deployments/infrastructure/variables.tf:6` and `:11`.
- **P4.** This file drifts unattended, so pinning one fact is worth a test.
  Evidence: the immediately preceding ticket found and fixed three false
  claims in it (the node constraint at `docs/gcs-backups.md:72`, and the CPU
  figures at `docs/gcs-backups.md:57` and `:62`), each traced by the
  reviewers to a commit that moved the code and left the doc alone.
- **P5.** No code reads this file, so the rewrite cannot break a gate other
  than the writing-style scan. UNCERTAIN only in the trivial sense that it
  rests on absence; the previous ticket's reviewers grepped the repo for
  references to this document's content and found none outside `.loop/`.
