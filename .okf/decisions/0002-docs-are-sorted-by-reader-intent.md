---
type: decision
title: "ADR 0002: docs/ is sorted by reader intent, and holds only pages for people who use the cluster"
description: docs/ gains how-to/, reference/ and explanation/, one folder per Diátaxis type. Mixed pages are split by section with their wording kept, and material for people working on the repository moves to .okf/.
generated:
  by: claude-opus/5.5
  at: 2026-09-26
tags: [adr, decision, documentation, diataxis]
status: stable
decision_status: Accepted
decided_on: 2026-09-26
---

# ADR 0002: docs/ is sorted by reader intent, and holds only pages for people who use the cluster

- Status: Accepted
- Date: 2026-09-26

## Context

`docs/` was one flat folder. Most pages mixed several kinds of text. A
reference table of ports sat beside a how-to for sign-in, an argument for why
Prometheus is not routed through the edge, and a build plan marked as history.
Page names followed no convention (`haproxy_reverse_proxy.md`,
`cli-login.md`).

Paths into `docs/` are cited from outside it: Terraform `###` comments, a
Vault group `description`, Nomad jobspec comments, an Ansible template, and a
drift test, `cli/tests/test_backup_coverage.py`, that reads
`docs/gcs-backups.md` by path.

This repository has no Confluence or other home for explanation, unlike the
repository this layout was copied from.

## Decision

Sort `docs/` by what the reader is doing, one folder per Diátaxis type, with an
audience test applied first:

- `how-to/`: one task for a reader at work, in the shape
  `.claude/rules/how-to-skeleton.md` sets and `cli/tests/test_how_to_skeleton.py`
  checks.
- `reference/`: a surface described without instructing.
- `explanation/`: why the cluster is shaped the way it is. It stays in `docs/`
  because nothing else here could hold it.
- `tutorials/`: created with its first page.

A page whose reader works on the repository, not the cluster, leaves `docs/`
for `.okf/`, per ADR 0001.

Split mixed pages by section and keep the wording. Only headings, links and the
how-to framing change. Rejected alternative: rewrite each page in a strict
Diátaxis voice. That would have made a much larger diff to review, and the
existing prose was already measured and specific.

A second rejected alternative: fix every path cited from outside `docs/`. Paths
inside a Nomad jobspec, a Terraform heredoc or a state-bearing attribute stay
stale, because editing them re-registers a job or rewrites live Vault state for
a comment (`.claude/rules/terraform-file-layout.md`). `###` comments outside
heredocs, tests, scripts and the README are updated.

## Consequences

Every path in `docs/` moved, so bookmarks and the stale citations above point
at files that no longer exist. Anyone following one lands on a missing file and
has to look it up in `docs/README.md`.

A page whose type is truly mixed has no single home, which is the intended
pressure: the answer is to split it.

The split keeps wording written for a single page, so some pages open mid-topic
or say "below" about text that is now elsewhere. Those are fixed as they are
found, not by rewriting the tree.
