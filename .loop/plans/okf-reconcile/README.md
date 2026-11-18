---
type: plan
title: 'Plan: okf-reconcile'
description: Reconcile .okf/ in place with the code, the git log and kmctl conventions, and write its summary and manifesto.
tags:
- plan
generated:
  by: process:loopctl/2.2.2.dev1+gd84319696
  at: '2026-10-19T17:20:16+00:00'
slug: okf-reconcile
epic: knowledge-rebuild
depends_on: []
priority: 1
---

# okf-reconcile

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

Reconcile `.okf/` in place with the code, the git log and kmctl v0.10.0
conventions. Keep what is right, fix what drifted, fill the gaps the history
shows, and write the two empty kmctl templates, `.okf/summary.md` and
`.okf/manifesto.md`. This is not a backfill from scratch. `docs/` is out of
scope (ticket `docs-reconcile` depends on this one).

Measured on 2026-10-19, at HEAD:

- `kmctl check` passes with 1 warning: the summary is behind.
- `kmctl review due --json` reports 70 due and 444 notices. Every notice is
  "source not resolved", across 63 concepts. 303 sources pin a path to
  commit 3ec5d1e (git:SHA:PATH), 14 more pin other commits, 17 name a bare
  commit and 94 name an archived loop ticket (loop:SLUG). kmctl resolves only
  a path git tracks at HEAD, so none of these ever flags its concept when the
  code changes. The three plain-path sources in
  `.okf/decisions/0015-loopctl-owns-the-pre-commit-hook-and-chains-prek-behind-it.md`
  resolve.
- Code drift since the 3ec5d1e pin: 23 files changed (662+/96-), mainly
  `deployments/applications/services/openviking.hcl`, `justfile`,
  `.devcontainer/Dockerfile`, `deployments/infrastructure/oidc.tf`,
  `deployments/infrastructure/database.tf`,
  `deployments/infrastructure/identity.tf`,
  `deployments/infrastructure/services/grafana/alert-rules.yaml` and new
  tests under `cli/tests/`. The concepts that cite these are the first ones
  to audit.
- History gap: 82 loop tickets live in the tree at 48f52e2 (read with
  git show 48f52e2:.loop/...). The bundle cites 79. R10, R11 and R12 (keyless
  MinIO for loki, registry and memex) are cited nowhere.
- Both `.okf/summary.md` and `.okf/manifesto.md` are still the unfilled
  `kmctl init` templates.

The work, all inside `.okf/`:

1. Repoint sources. Every git:SHA:PATH source becomes the plain PATH when
   that path is tracked at HEAD. A path that moved (most old `docs/` pages)
   points at its new home. A path that is gone, a bare commit and a loop:SLUG
   leave `sources` and become a short Evidence line in the body that names
   the commit SHA or the ticket, so the provenance survives in prose.
2. Audit each concept in `.okf/components/`, `.okf/nodes/`,
   `.okf/practices/`, `.okf/proposals/` and `.okf/architecture/` against the
   code its sources name and the commits since its `generated.at`. Fix the
   drift in the body. Give a time-bound concept (a proposal, a practice tied
   to an upstream version) a `stale_after`.
3. Fill the gaps: record R10 to R12 in the concepts they changed
   (`.okf/components/minio.md` and its neighbors), and any other gap the
   audit finds. Update a concept before creating a new one.
4. Write `.okf/manifesto.md`: what the cluster is for, invariants and values
   as the manifesto-invariants rule in .claude/rules requires (that file is
   not tracked by git yet). An invariant is
   `enforced` only when it names a test in `cli/tests/` that passes, else
   `planned`. Values go in marked as a draft for the operator to approve in review
   (operator, 2026-10-19). Add the
   invariant ids to the Depicts section of
   `.okf/architecture/deployment-layers.md`, per the diagrams-stay-current
   rule in .claude/rules (also untracked).
5. Mark ADR 0014 superseded by ADR 0001 with `kmctl decision supersede`:
   both record the choice to keep knowledge in an OKF bundle, and 0014 is the
   template `kmctl init` wrote (operator, 2026-10-19).
6. Write `.okf/summary.md`: at most 500 words, citing concepts inline.
7. Append one line to `.okf/log.md` for each change, naming every touched
   concept id. Keep the section indexes and `.okf/index.md` in step (the
   root index counts are already wrong: it says 13 decisions, there are 15).

Build setup: `.claude/rules/` is gitignored apart from four files, so a fresh
worktree lacks the manifesto-invariants and diagrams-stay-current rules, the
SSH key and the tfvars that `just pre_commit` needs. Run `just worktree_setup
<worktree>` right after `loopctl ticket advance okf-reconcile building`.

Write each invariant bullet with its `planned` or `enforced` status on its
first line, since r5 reads only that line. Write or ack the summary last, in
the ticket's final commit, so kmctl does not count it behind.

The docs tickets that depend on this one (`docs-howto`, `docs-reference`,
`docs-explanation`) repoint any `.okf` source that names a page they rename or
delete, and their evals require `kmctl review due` to report no notice at all,
so the empty notices this ticket reaches stay empty.

Decision records keep their bodies byte for byte (`.claude/rules/okf-bundle.md`).
A wrong claim in one gets an appended `## Correction, YYYY-MM-DD` section. No
agent adds a `verified` entry or runs `kmctl verify`: only a person can.

Outcome, all checked at the ticket's commit:

- `kmctl check` prints "all checks passed" with no warning line.
- `kmctl review due --json` has an empty `notices` list, and every `due`
  entry's reasons are exactly `["unverified"]` (no summary, no stale_after
  passed).
- Every concept in `.okf/components/`, `.okf/nodes/`, `.okf/practices/`,
  `.okf/proposals/` and `.okf/architecture/` has at least one source.
- `.okf/summary.md` is at most 500 words, has none of the template's
  placeholder sentences, and links at least one concept from each section.
- Every invariant in `.okf/manifesto.md` is marked `planned` or `enforced`,
  each `enforced` one names a test that passes under
  `uv run --directory cli pytest`, and each appears in a Depicts section.
- Every concept file the ticket's diff changes is named by id in a line the
  diff adds to `.okf/log.md`, and no earlier line of it changes.

## Could invalidate this plan

- Step 1 edits the `sources` front matter of 10 notices across the decision
  records, while leaving their bodies alone. If the operator reads "a record
  is never rewritten" in `.claude/rules/okf-bundle.md` as covering front
  matter too, those edits must come out. The empty-notices outcome then has
  to exclude `.okf/decisions/`, or each record takes a correction section
  instead. Only the operator can settle this: by accepting this risk or by
  ruling the other way before the build starts.
