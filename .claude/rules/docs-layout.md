---
title: docs-layout
description: What belongs in `docs/` and what belongs in `.okf/`. Read before adding or moving a page in either.
---

# `docs/` and `.okf/`

Two folders hold prose, and they have different readers.

- `docs/` is for people who USE the cluster: the operator running it, a person
  who logs in to a service on it, and anyone deploying a job onto it. Nothing
  here is executed, so anything here that has to stay true needs something
  outside this folder checking it (`cli/tests/test_backup_coverage.py` is the
  model). `docs/README.md` is the index and lists every page.
- `.okf/` is for agents and people working ON this repository: decisions and
  the alternative each rejected, lessons learned the hard way, proposals not
  yet built, and history a user never needs. How to read and extend it is
  `.claude/rules/okf-bundle.md`. Ticket plans and verdicts stay in `.loop/`,
  and the bundle does not copy them.

<constraint name="docs-sorted-by-reader-intent">
WHY: a page filed under the wrong heading is read by the wrong person and
answers a question they did not ask.

`docs/` has one subdirectory per Diátaxis type, and the test is what the reader
is doing, never how the page is shaped.

- `how-to/` is for a reader at work with one task. Every page has the shape
  `.claude/rules/how-to-skeleton.md` sets.
- `reference/` describes a surface without instructing: commands, routes,
  ports, roles, what a service exposes. Architecture diagrams are under
  `reference/architecture/`.
- `explanation/` says why the cluster is shaped the way it is. There is no
  Confluence here, so the "why" for users is in `docs/`.
- `tutorials/` is a lesson for a learner at study, sure to succeed in one
  sitting. It is created with its first such page.

Mixing two intents in one page is a reason to split it, never to blend them.
</constraint>

<constraint name="audience-gates-the-folder">
WHY: a spike, a build plan or a handoff reads as current instructions to a user
who finds it in `docs/`, and it goes stale where nobody maintaining the user
docs looks.

Audience decides the folder before intent does. A spike, a superseded proposal,
a build plan, an audit, a handoff note, or the record of a choice goes to
`.okf/`, even when it is shaped like a guide.
</constraint>

<constraint name="index-tracks-the-folder">
WHY: an index is believed, so an index that disagrees with its folder is worse
than none.

Adding, renaming or removing a page under `docs/` updates `docs/README.md` in
the same change, and updates every link to the old path.
`cli/tests/test_docs_index.py` refuses a page the index does not list. A path
cited inside a Nomad jobspec, a Terraform heredoc or a state-bearing attribute
stays as it is, per `.claude/rules/terraform-file-layout.md`, because editing
it re-registers a job or rewrites live state.
</constraint>
