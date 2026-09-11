eval: gcs-backups-doc-to-runbook

**Definition of Done:** `docs/gcs-backups.md` describes the backup system as
it exists today, every mechanically checkable fact in it is pinned to the
source that declares it, and the document says plainly which parts of the
backup chain nobody has verified.

| Behavior | Input | Expected | Fails-when | Scorer | Threshold |
|---|---|---|---|---|---|
| The document describes a running system, not a change being made | `docs/gcs-backups.md`, whole file | No sentence presents the jobs as new or about to be added. The strings "This change adds", "No off-site backups exist" and "re-init needed first time" are gone, and no heading presupposes a first-time reader. | Any of those three strings survives, or a new sentence introduces the jobs as a change. | human with rubric: read the file start to finish | 100% |
| An operator changing the backup infrastructure still finds the commands | `docs/gcs-backups.md`, the `## Prerequisites` section and the `just init` / `just apply` block | Both survive, re-framed as what to run when rotating the service-account key or moving the bucket. `gcloud auth application-default login` is still present, because `localstack env` sets no Google credential. | Either is deleted as "change framing", which would strip the only record of how to authenticate to GCP. | human with rubric: read those two sections | 100% |
| The Google provider version in the doc matches the one Terraform declares | `docs/gcs-backups.md` and `deployments/infrastructure/providers.tf:17` | Both read `~>7.27.0`. | The doc says `~>6.0.0`, which is the state on `main` today, so this reddens against the pre-change tree. Also fails if either parser finds nothing. | deterministic: `test_backup_doc_names_the_google_provider_version` | 100% |
| Every mechanically checkable fact in the doc matches its jobspec | The twelve facts R3 names: provider version, two node constraints, six CPU and memory figures keyed by task, three container images; plus the two cron expressions the rewrite adds | Each matches its source. Figures bind to their own task, so a `pgdump`/`sync` swap still fails. The doc states `0 2 * * *` and `0 3 * * *` literally, which it does not today. | Any pinned fact is edited in one place only; or the crons are left as prose, in which case the schedule test finds nothing in the doc and fails. | deterministic: the four tests in `cli/tests/test_backup_coverage.py` | 100% |
| Nothing an operator could previously find in this file is gone | The current 138-line file, section by section, against the rewrite | Every section keeps a home. Reframing may move, merge or rename a section; it may not drop its content. The Vault policy constraint, the GCS path tree, the per-job credential paths, and the four Terraform resource listings all survive. | Any section's content is absent from the rewrite with no replacement, most likely `## Vault Policy Constraint` or the `## Configuration` block, which read as change-time detail but are what an operator needs to locate a credential. | human with rubric: diff the old file's section list against the new one | 100% |
| The document claims no more than anyone can confirm | `docs/gcs-backups.md`, whole file, including its H1 | Claims are limited to what the jobspecs and `nomad job status` support: the jobs are registered, periodic, and configured to copy named sources to named destinations. The H1 may name the configured schedule, because the crons carry it. | The document states that backups "are taken nightly", "run every night", or otherwise asserts end-to-end success, which the 403 on the children query means nobody can currently confirm. | human with rubric: read every claim about outcomes | 100% |
| The document names its own gaps | `docs/gcs-backups.md`, the section stating absences | It says this document does not cover restore, and that this repo records no verified read-back of a backup. Both worded as checkable claims about the repo. | The gaps go unmentioned, leaving a reader to assume restore is covered elsewhere; or the wording overreaches into "no restore has ever been performed", which is as unverifiable as the claims 'The document claims no more than anyone can confirm' forbids. | human with rubric: read that section | 100% |

Notes:

- Rows 3 and 4 are the only ones a test can score. The rest are judgments
  about framing and completeness, which no parser reaches.
- Row 4 is the reason the rewrite adds literal cron expressions. The document
  today carries none, so the schedule half of that test would fail by
  construction against the current text.
- Not scored here: whether a restore actually works. That needs a restore
  performed against live data, which the plan's Q1 defers to a follow-up
  ticket. Row 7 scores only that the document admits the gap.

signed-off-by: JasperHG90 2026-09-11
