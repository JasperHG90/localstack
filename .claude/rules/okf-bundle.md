---
title: okf-bundle
description: How to read, extend and validate the `.okf/` knowledge bundle.
---

# Using the OKF bundle

`.okf/` at the repository root holds durable knowledge as markdown. What
belongs in it, and what belongs in `docs/` instead, is
`.claude/rules/docs-layout.md`, and this rule does not repeat it. What is below
is how to find something in the bundle, how to add to it without degrading it,
and what has to pass before a change to it is done.

## Start at the root index, every time

`.okf/index.md` is the entry point and the only file you should open without a
reason. It carries the bundle's `okf_version`, one link per section, and a
count, so a reader sees the whole surface before opening anything. Each
subdirectory carries its own `index.md` listing that section's concepts with
the description from each concept's own frontmatter.

Read the root index, pick the sections that bear on the task, then follow
links. Grepping `.okf/` for a keyword skips the layer built to save you that
work and returns the concept that happens to share your wording rather than the
one that answers you.

`index.md` and `log.md` are reserved names. Never use either for a concept.

## One concept is one file, and its path is its id

A concept's path minus `.md` is its identifier, so a link reads
`/practices/ufw-rules-outside-user-rules.md` from anywhere in the bundle.
Filenames are kebab-case, `[a-z0-9-]` only, and they name a domain entity.
`vault-login-mfa` is an entity. `feat-add-vault-2fa` is a change that touched
one, and a bundle named that way becomes a commit log with worse ordering.

Prefer updating an existing concept to creating a neighbor. Two files on one
entity split its history, and the thinner one is the one a reader finds first.

## The one hard rule

A bundle is conformant when every non-reserved `.md` file has parseable YAML
frontmatter carrying a non-empty `type`. Everything else in the frontmatter is
optional and worth filling anyway: `title`, `description`, `tags`, `status`,
`stale_after`, `generated`, `verified`, `sources`.

A `description` holding a colon has to be quoted or the whole document stops
being YAML. That turns a concept into a file the validator rejects and a reader
still sees.

## Weigh what you read

The bundle was hand-seeded from `docs/` pages that were written against the
cluster as it stood on their date, and no person has re-confirmed them since.
Treat an unverified claim as a lead. `status: draft` or `deprecated`, a
`stale_after` already past, and an absent `verified` all mean the same thing,
which is check before you rely on it.

When a person confirms a concept, add a `verified` entry naming them in the
actor convention `human:<id>`. Consumers key trust off that prefix, so an agent
must never write one for work a person did not actually check.

## Writing back

Learning something durable while working is the moment to update the bundle,
not a separate task to file. Touching a concept means updating its body, then
appending a dated bullet to `log.md` saying why the change happened.

Which trust field moves depends on what you actually did. `generated.by` says
who produced the CURRENT TEXT. Correcting a claim or tidying a paragraph leaves
that text mostly the previous author's, so `generated.by` stays as it is. It
becomes yours when you have rewritten enough that the previous author would not
recognize it.

Confirming content is what `verified` is for. Who wrote a concept need not be
who checked it:

```yaml
verified:
  by: human:jasperhg90
  at: 2026-09-26
```

`generated.at` marks the content's last meaningful change, so a corrected claim
moves it and a typo does not. Leave old `verified` entries in place when you do
rewrite: a `verified.at` earlier than `generated.at` is the signal that the
sign-off predates the text.

`sources` is provenance. Reach for it when you cite something specific, such as
a commit or the `docs/` page a concept was carved out of, and not before.
Hand-writing a concept needs `type`, `title`, `description`, `tags` and
`generated`, which is a complete frontmatter with no warnings.

A log bullet carries intent. `Updated vault-login-mfa` restates the heading.
`Recorded that enforcing MFA before enrollment locks the operator out` is the
reason someone reads a log for. `log.md` is append-only history: correct a
concept by editing the concept and logging the correction.

## Capturing a decision

A decision gets a record in `.okf/decisions/` at the moment it is made, in the
same change that acts on it. Writing it later means writing what you now
believe you thought, which is a different document.

Something is a decision when a real alternative was rejected. A choice with no
alternative was not a decision, and neither is an implementation note, a status
update, or a summary of what a ticket did. Ticket history stays in `.loop/`.

The file is `NNNN-kebab-summary.md`, taking the next number in sequence, zero
padded to four digits. Order is part of what records say: 0007 can only
supersede 0002 if a reader can see which came first.

```markdown
---
type: decision
title: "ADR NNNN: The decision, stated as a claim"
description: What changed and what it costs, in one or two sentences.
generated:
  by: claude-opus/5.5
  at: 2026-09-26
tags: [adr, decision]
status: stable
decision_status: Accepted
decided_on: 2026-09-26
---

# ADR NNNN: The decision, stated as a claim

- Status: Accepted
- Date: 2026-09-26

## Context

What was true, what was not known yet, and what forced a choice.

## Decision

The choice, in the imperative, with the alternative that was rejected.

## Consequences

What this costs, what it rules out, and what now has to stay true.
```

`status` is the OKF lifecycle field and answers "should a reader still follow
this": `stable`, or `deprecated` once superseded. `decision_status` carries the
record's own words, such as `Accepted`, `Superseded by ADR 0009`, or
`Accepted, reasoning corrected`.

A record is never written over. Correcting one means appending a
`## Correction, YYYY-MM-DD` section saying what the record got wrong and what
replaced it. A reversal is written in BOTH records, by marking the old one
superseded and naming it from the new one.

<constraint name="decisions-are-captured-as-records">
WHY: the reasoning behind a choice is the first thing lost and the most
expensive to reconstruct, and an agent that made the choice is the only party
who still holds it.

Reject a real alternative, write the record, in the same change. It goes in
`.okf/decisions/` with the next number, carries Context, Decision and
Consequences, and states the alternative it rejected. Appending a correction is
how a record changes. Editing its body is not.
</constraint>

<constraint name="okf-entry-point-is-the-root-index">
WHY: the bundle exists to let a reader see what is available before opening
anything, and a keyword search returns the concept that shares your wording
rather than the one that answers you.

Open `.okf/index.md` before any other file in the bundle, and reach a concept
by following a link from an index.
</constraint>

<constraint name="okf-changes-are-validated">
WHY: the single hard conformance rule is a YAML parse, which fails silently to
a human reader. A malformed concept still renders and still reads as knowledge.

A change to `.okf/` is not done until `Skill(okf:validate)` passes against it
with `--strict`. Fix every error and every warning rather than dropping the
flag.
</constraint>

<constraint name="okf-trust-is-not-assumed">
WHY: a concept reads with the same confidence whether or not anyone checked it.

Never write a `verified` entry, and never write `human:` in any actor field,
for work a person did not confirm. An agent records itself in `generated.by`
using `<producer>/<version>` (for example `claude-opus/5.5`), and leaves the
concept unverified.
</constraint>

<constraint name="okf-indexes-track-their-directory">
WHY: an index is a promise about what a directory contains, and a reader who
trusts it stops looking when it is wrong.

Adding, renaming or removing a concept updates that directory's `index.md` and
the root index count in the same change. The entry carries the concept's own
`description`, not a fresh one written at the index.
</constraint>
