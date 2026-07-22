---
name: create-eval
description: Co-author a ticket's eval marker with the operator before implementation, using the five-column Behavior/Input/Expected/Scorer/Threshold template, written to .loop/evals/<slug>.md. Use when a ticket needs its Definition of Done made concrete, when the require_eval gate refuses pickup because no eval marker exists, or whenever you finish writing a ticket and are about to hand it off. Writes one marker file and validates it with loopctl eval.
---

# create-eval

The eval is the spec. Before a ticket is implemented, this skill sits
with the operator and turns its Definition of Done into a small set of
concrete, scored scenarios: for each observable behavior, a specific
input, what good looks like, who judges it, and the bar it must clear.
Those scenarios become the acceptance layer the implementation is
measured against, written to `.loop/evals/<slug>.md`.

An eval written this way is the contract, the changelog, and the
definition of done in one artifact. It binds to intent, not to a tree,
because it is authored before the code exists. The reasoning behind
this, and the source of the template below, is in
`references/eval-is-the-spec.md`. Read it when you want the why or a
fuller worked example.

When `require_eval` is set in `.loop/config.json`, the harness refuses
to advance a ticket into `implementing` until a schema-valid marker
exists for its slug. This skill produces that marker. The harness only
checks the marker's shape, never its content, so the substance is yours
and the operator's to get right here.

## The five-column template

Every scenario row carries five columns. Copy the blank table from
`assets/eval-template.md` and fill one row per scenario.

| Column | What it holds |
|-----------|-------------------------------------------------------------|
| Behavior  | The observable thing the system does, in the user's frame, not technical jargon. |
| Input     | A specific, concrete test case: an actual string, file, or situation, never an abstract category. |
| Expected  | What "good" looks like for this input, stated as structural requirements the output must satisfy. |
| Scorer    | Who or what judges the output: a deterministic check, a model with a rubric, or a human with a rubric. |
| Threshold | The pass bar: a hard 100%, a numeric rubric score, a percentage of cases, or a baseline to beat. |

Scorer and Threshold are the two columns a bare "input to expected"
table leaves out, and they are what make a row testable. Without a
Scorer, no one knows who decides whether the row passed. Without a
Threshold, "good enough" stays an argument. State them, and the row
becomes a check the loop and the reviewer can both apply.

## What the marker is (and is not)

- It is the acceptance layer ABOVE unit tests: scenarios in the
  domain's own language. Some rows later become unit tests (Scorer:
  deterministic), some an agent or model check (Scorer: model with
  rubric), some a human judgment (Scorer: human with rubric), and some
  are guardrails: a behavior the system must refuse or an invariant it
  must not weaken.
- It is NOT a restatement of the ticket's unit tests. If a row only
  repeats what a `test_*` already asserts in code terms, cut it or
  raise it to the outcome the test defends.
- It is small and deliberate. Aim for roughly one row per real
  behavior or branch, plus a few adversarial rows: about 5 for a
  narrow change, 10 to 15 when the behavior is wide or the failure
  modes are subtle. This is the ticket-scoped cousin of the larger
  production eval sets described in the reference.

## The schema the harness checks

`.loop/evals/<slug>.md` must carry, anywhere in the file:

- a header line that reads exactly `eval: <slug>` (the ticket's slug),
  and
- at least one scenario row: a `-` or `*` list item, or a `|` table
  row.

A five-column table row is a `|` row, so it satisfies the schema. The
check is content-blind and slug-bound: a header naming another slug, or
a header with no scenario row, fails, and the substance is never
graded. Everything else in the file is free-form, so keep the one-line
Definition of Done and any notes you like above the table.

## Working with the operator

1. **Read the ticket.** Find `<slug>.md` in the configured plans
   directory (`.loop/config.json` `plans_dir`, default
   `~/.claude/plans/`) and read its Context, Requirements, Non-goals,
   and Tests sections so the eval traces to what the feature should
   produce and refuse.
2. **Propose a count, then ask via `AskUserQuestion`.** Suggest how many
   scenarios fit this feature and say why (see the sizing guidance
   above), then put the count to the operator with `AskUserQuestion`:
   your recommended count first, plus nearby options, so the decision is
   unmissable rather than buried in prose.
3. **Draft every column; surface the discrete forks via `AskUserQuestion`.**
   Propose concrete rows first; do not wait to be asked. Writing each
   row's Behavior, Input, and Expected is free-form collaboration and
   STAYS PROSE: do not force open-ended authoring into multiple-choice.
   But three choices per row are discrete forks, so put each to the
   operator with `AskUserQuestion`, recommended option first: keep or
   cut a proposed row; which Scorer (a deterministic check, a model with
   a rubric, or a human with a rubric); and which Threshold (100%, an
   N/5 rubric score, a percentage of cases, or a baseline to beat). For
   a guardrail row the recommended Scorer is deterministic and the
   recommended Threshold is 100%. A row missing its Scorer or Threshold
   is not yet done; if a row cannot be written, surface that rather than
   paper over it.
4. **Write the marker.** Write `.loop/evals/<slug>.md` from the blank
   in `assets/eval-template.md`: the `eval: <slug>` header, a one-line
   Definition of Done, then the five-column table with one row per
   scenario.
5. **Validate.** Run `loopctl eval <slug>`. A non-zero exit means the
   shape is wrong (missing header or no row); fix and re-run until it
   reports `valid`.
6. **Reference it from the ticket.** Add or update a line in the
   ticket's "Tests & validation gates" section pointing at
   `.loop/evals/<slug>.md`, so the two Definition-of-Done sources stay
   in step. Nothing enforces this link, so maintain it by hand.

## Discipline

- **The operator owns the substance.** This is a collaboration, not a
  generation. Draft proactively, but every row ships only once the
  operator agrees it is right.
- **One scenario, one claim.** A row that asserts two things is two
  rows.
- **Concrete over abstract.** "Given an empty config, expect defaults
  with no gates" beats "handles missing config gracefully". The Input
  column holds a real value, never a category.
- **Score the guardrails hardest.** The rows that protect an invariant
  (a change that must still be detected, a config that must be refused)
  carry a deterministic Scorer and a 100% Threshold, because a
  guardrail that passes 90% of the time is a guardrail with a hole.
- **One marker, one slug, one file.** The marker's identity is the
  ticket slug; keep it to `.loop/evals/<slug>.md`.
