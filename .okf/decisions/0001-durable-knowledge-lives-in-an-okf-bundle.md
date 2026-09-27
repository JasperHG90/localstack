---
type: decision
title: "ADR 0001: Durable knowledge is kept in a validated OKF bundle, not in docs/ or AGENTS.md"
description: Why this repository keeps its decisions, lessons and unbuilt proposals in .okf/ with checked frontmatter and an append-only decisions directory, rather than as more pages in docs/ or more paragraphs in AGENTS.md.
generated:
  by: claude-opus/5.5
  at: 2026-09-26
tags: [adr, decision, knowledge, okf, documentation]
status: stable
decision_status: Accepted
decided_on: 2026-09-26
---

# ADR 0001: Durable knowledge is kept in a validated OKF bundle, not in docs/ or AGENTS.md

- Status: Accepted
- Date: 2026-09-26

## Context

Until this record, `docs/` held everything written down about the cluster in
one flat folder of 29 pages: user guides beside a Postgres spike, a superseded
dashboard proposal, two build plans nobody carried out, a 2FA handoff, and an
audit of loop ticket plans. A reader could not tell a current instruction from
a record of what someone once intended. `monitoring.md` said so in its own
body: "The rest of this document is the original build plan ... treat the
addresses and file lists below as history rather than as current state."

`AGENTS.md` is loaded into every session, so everything in it is paid for on
every task. It has to stay a map.

`.loop/` holds ticket plans, verdicts and reflections. It records what a ticket
set out to do and whether it passed review, but a finished ticket's reasoning
is spread over those files and nothing points a later reader at the one
decision inside it that still matters.

The code comments carry the rest. `deployments/infrastructure/database.tf`
opens with forty lines of why, and a reader who reaches the same constraint
from elsewhere never sees them.

## Decision

Keep durable knowledge in `.okf/`, an Open Knowledge Format bundle at the
repository root, and keep `docs/` for people who use the cluster.

The format buys three things plain markdown under `docs/` did not:

- **Frontmatter that is checked.** Every non-reserved file carries YAML
  frontmatter with a non-empty `type`, and `okf:validate --strict` gates each
  change.
- **Trust stated rather than assumed.** `generated.by` says who wrote the text
  and `verified` says which person confirmed it, so a reader can tell a lead
  from a fact.
- **Two kinds of file.** A concept is edited in place. A record under
  `decisions/` is append-only and corrected by appending, so 0007 can visibly
  supersede 0002.

The bundle was seeded by hand from the `docs/` pages that were not user docs.
Rejected alternative: run `okf:backfill` over the repository's history of about
465 commits. It would have produced many more concepts, every one unverified,
at the cost of a large multi-agent run, and the pages already in `docs/` held
the reasoning worth keeping. A backfill can still run later on top of this
bundle.

## Consequences

Every decision that rejects a real alternative now owes a record, in the change
that acts on it. Nothing enforces that: the validator checks a bundle's shape,
not whether a decision reached one.

Records 0001 and 0002 set the bundle up. Records 0003 to 0012 were written
retrospectively in the same change, from the pages they were carved out of,
and are numbered by `decided_on`. Their numbers follow the order the choices
were made, not the order the records were written.

Every seeded concept is unverified. It was carved out of a page written against
the cluster on that page's date.

The rule that governs the bundle is `.claude/rules/okf-bundle.md`, and
`.claude/rules/docs-layout.md` says which of the two folders a page belongs in.
Both are loaded every session, which is the overhead this decision accepts.
