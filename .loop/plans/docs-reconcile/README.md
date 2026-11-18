---
type: plan
title: 'Plan: docs-reconcile'
description: Audit and repair every docs/ page in place against the code and git log, and bring each to kmctl front matter and index conventions.
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T17:19:27+00:00'
slug: docs-reconcile
epic: knowledge-rebuild
depends_on:
- okf-reconcile
priority: 2
---

# docs-reconcile

<!-- This template was registered in planning. To capture an idea as a stub
instead (intent for later, promoted by the operator), write the plan with
`status: draft` in its front matter before running loopctl ticket register.
A hand-written plan's front matter needs type: plan, title, description and
slug; loopctl ticket register fills in generated. Optional: epic, depends_on,
priority, status, strictness and blocking. -->

Relayed from: none
<!-- When this ticket carries a finding raised while building another ticket,
replace "none" with that ticket's slug and the finding, in one line (ADR 0001). -->

## Intent

Reconcile `docs/` in place against the code and the git log, and bring every
page to kmctl's docs conventions. This is an audit and repair, not a rewrite:
a page that is right keeps its text. `okf-reconcile` owns `.okf/`; this ticket
touches only `docs/` and the tests that guard it.

Scope today: 81 pages (51 how-to, 19 reference, 11 explanation) plus three
folder indexes, the hand-written `docs/README.md`, three diagrams under
`docs/reference/architecture/`, `docs/note-sync.toml`, and an empty untracked
`docs/notes/main/` folder. About 39,000 words. No page has front matter yet.
99 commits touch `docs/`, the last on 2026-10-19.

The work, page by page:

1. Check every claim, command and backticked path against the code it names
   and the commits since the page last changed. Fix drift, and add what a
   reader needs that the code now does and the page omits. A page about
   something that no longer exists is deleted, with every link to it updated.
2. Give the page front matter holding only `description` (one sentence, the
   index entry), `stale_after` (three months out, kmctl's default) and
   `sources` (the files it describes), per `.claude/rules/docs-layout.md`.
   Add `verified` only through `kmctl verify` once a page has been checked.
3. Keep the how-to shape `.claude/rules/how-to-skeleton.md` sets and
   `cli/tests/test_how_to_skeleton.py` enforces, and run the plain-language
   and slop-scan rules under .claude/rules on each changed page.
4. Regenerate `docs/how-to/README.md`, `docs/reference/README.md` and
   `docs/explanation/README.md` with `kmctl check --fix`. Never edit them.
5. Keep `docs/README.md` as the hand-written hub it is: it links each folder
   index, as `.claude/rules/docs-layout.md` requires, and lists every page by
   topic, as `cli/tests/test_docs_index.py` (`test_index_lists_every_page`)
   requires. Update its entries when a page's title or path changes. The
   test does not change.
6. A page whose audience is people working on the repo (a plan, audit,
   handoff or decision record) does not stay in `docs/`. Hand it to
   `okf-reconcile` as a relayed finding rather than writing under `.okf/`.
7. Delete `docs/note-sync.toml` and the empty, untracked `docs/notes/`: the
   operator chose to drop note sync (2026-10-19).
8. When the page and the code disagree and the code is the thing that is
   wrong, leave the page describing actual behavior, and raise the bug as a
   finding for a new ticket. Do not fix product code here.

Baseline measured for the outcome: a rough scan of backticked file-like paths
(with a `/` and a file extension, or ending in `/`) found 101, of which 20 in
17 pages resolve neither from the repo root nor from the page's folder. Many
are shorthand such as services/dash.hcl for
`deployments/applications/services/dash.hcl`, so part of the work is writing paths
out from the repo root.

Outcome that shows it worked, all four true at once:

- every page under `docs/how-to/`, `docs/reference/` and `docs/explanation/`
  other than its `README.md` has front matter with a `description`, a
  `stale_after` and a non-empty `sources` whose every entry is a tracked path;
- `uvx --from git+https://github.com/JasperHG90/kmctl@v0.10.0 kmctl check`
  reports no error and no warning that names a `docs/` path;
- `just pre_commit` and `uv run --directory cli pytest` pass, including
  `cli/tests/test_docs_index.py`, `cli/tests/test_how_to_skeleton.py` and the
  doc-drift checks in `cli/tests/test_backup_coverage.py`;
- every backticked repo path in `docs/` resolves from the repo root: 0 of the
  43 shorthand paths `spike:docs-reconcile/2` found are left, and a bare name
  that exists in both Terraform roots (`secrets.tf`, `variables.tf`) names its
  root. Runtime paths, gitignored local files and files in other codebases
  are not repo paths and stay as they are.

## Could invalidate this plan

- kmctl's docs schema sets body sections that differ from this repo's. For
  how-to it wants `Before you start`, `Steps`, `Check it worked`; the repo
  rule and its test want `Introduction`, `Prerequisites`, `Directions`,
  `Additional resources`. Reference and explanation have kmctl section lists
  too (`Summary`, `Details`; `The question`, `How it works`, `Why it is this
  way`) that no page uses. `kmctl check` passes today, but no page has front
  matter yet. If adding front matter makes `kmctl check` enforce kmctl's
  sections, the outcome cannot hold without either rewriting every page's
  shape or dropping the repo rule, and that is the operator's fork.
  Settled by `spike:docs-reconcile/3`: with front matter on one page of each
  kind, `kmctl check` passed and reported no section finding. kmctl v0.10.0
  uses its section lists only for its schema and the `kmctl new doc`
  skeleton, so the repo's how-to skeleton stays. `kmctl check` also does not
  verify that `sources` paths exist; only `kmctl review due` reports an
  unresolved one, so the outcome's tracked-path check reads its notices.
- Scale: 81 pages and about 39,000 words in one ticket. An audit of this size
  may not fit one build, and it bundles three folders that could ship apart
  (how-to, reference, explanation). If it does not fit, the plan should be
  three tickets, one per folder.
- Pages that belong in `.okf/`. If the audit finds more than a handful of
  pages written for repo workers, the work moves into `okf-reconcile`'s
  territory, and the order of the two tickets (this one depends on it) is
  wrong for those pages.
  Settled by `spike:docs-reconcile/1`: 0 of 81 pages are mainly repo-worker
  content. 11 carry lines of build history (ticket codes, "at the time of
  writing") that are edited in place.
- Drift that is a code bug. If many disagreements turn out to be the code
  being wrong, the docs fixes either document bugs or wait on code tickets,
  and the outcome cannot be met by editing `docs/` alone.
  Settled by `spike:docs-reconcile/2`: of 55 unresolved paths, 43 are
  shorthand, 1 a gitignored local file, 7 runtime paths and 4 files in other
  codebases, so 0 are code bugs. All 100 `just` and `localstack` invocations
  on 23 pages match a recipe or the CLI's --help. Prose claims (ports,
  policies, TTLs) were not checked, so a code bug found there still goes to a
  new ticket per step 8.
