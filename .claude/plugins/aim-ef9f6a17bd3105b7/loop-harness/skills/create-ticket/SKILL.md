---
name: create-ticket
description: Author one loop-harness planning ticket in the format the implement-ticket loop consumes. Use when asked to plan a feature, scope a change, draft a ticket, or turn a described problem into a ticket the loop can run. Writes one ticket file to the configured plans directory.
---

# create-ticket

A loop-harness ticket is the CONTRACT the `implement-ticket` loop
executes against and the `loop-reviewer` judges against. This skill
defines that contract and produces one ticket file in it. Everything
downstream depends on a ticket shaped exactly this way: the lifecycle
gates, the tree-bound verdict, and the "every changed line traces to
the ticket" scope rule all read it as the interface. The format is
load-bearing.

## Two authoring paths

- **Scaffold inline (this skill).** For a small, well-understood
  change you already hold in context, write the ticket directly using
  the contract below.
- **Delegate the exploration (the `ticket-planner` agent).** For
  anything needing repo-aware investigation (finding the code
  surface, discovering the gates, resolving cited anchors), dispatch
  the `ticket-planner` subagent. Repo exploration is a read-heavy
  fan-out that belongs off the driver's context. The subagent returns
  just the ticket path. Prefer this for real features.

Both paths produce the same contract, and this file is its source of
truth.

## Where the ticket goes

Write one file to the plans directory the consumer configured
(`.loop/config.json` `plans_dir`, default `~/.claude/plans/`), named
`<slug>.md`. The slug is the ticket's stable identity. The loop's
commit-subject convention is `<slug>: summary` and the reconciler
matches commits by it, so choose a slug that is unique, kebab-case,
and descriptive (`add-rate-limit-headers`, not `fix` or `ticket-3`).

## The contract

Every ticket carries these sections. Omit a section only when it is
genuinely empty, and say so rather than dropping it silently.

1. **Title.** One line naming what changes and why it is worth doing.
2. **Size / Effort.** A rough magnitude (S/M/L) and one clause on what
   drives it. Calibrates the reviewer's expectations.
3. **Triggered by.** The request, bug, or decision that motivates
   this, in one sentence.
4. **Context.** What exists today, cited to the code (`path:line`),
   and what is wrong or missing. The reader should not need to
   re-derive the current state.
5. **Non-goals / out of scope.** What this ticket deliberately does
   NOT do. This prevents scope creep and tells the reviewer that a
   diff touching those areas is a violation.
6. **Requirements & restrictions.** What the change must achieve and
   the principles it must respect, EACH cited to where the repo
   states it (a rule file, an existing pattern, a config). Discover
   the repo's own conventions and cite them rather than assuming
   generic ones.
7. **Code surface.** The specific files and `path:line` anchors the
   change will touch, each with a one-line note on the change. The
   "every changed line traces to the ticket" scope rule is checked
   against this list, so keep it precise and complete. Needing a file
   not listed here is the `out-of-scope-fix-needed` blocker.
8. **Tests & validation gates.** The exact gates this change must pass,
   discovered from the repo (its test command, its lint/type config,
   its review rule), and the specific tests to add. A bug fix names a
   reproducing test first. Every test named here must have its file
   listed in §7's code surface — a named test with no declared home
   forces the implementer to guess where it lives.
9. **Risk assessment.** Blast radius, reversibility, and the likeliest
   failure modes. What breaks if this is wrong.
10. **Subtickets.** The change decomposed into an ordered,
    dependency-aware sequence a single loop iteration can each
    execute.
11. **Open questions.** Every decision this ticket cannot answer from
    the request, the repo, or the consumer's decision record. Each
    carries a recommendation. An unresolved design fork is a `blocked`
    state for the implementer (code `unresolved-design-fork`), never a
    silent judgment call, so surfacing forks here with your
    recommended resolution is what lets the operator settle them
    before the loop runs.

## Discipline

- **Cite, do not assume.** Every claim about the current code carries
  a `path:line` anchor you actually resolved. Re-open each anchor,
  because stale line numbers mislead the implementer.
- **Discover the gates from the repo**, not from habit. The test
  command, the lint/type config, the review rule, and the CI (or its
  absence) are facts about this repo, and the ticket's "Tests &
  validation gates" section must match them.
- **Forks are the operator's, not yours.** When the request, the repo,
  and the decision record leave a choice open, it goes in Open
  Questions with a recommendation. Picking silently is the failure the
  loop's `unresolved-design-fork` block exists to prevent.
- **One ticket, one slug, one file.** Split unrelated changes into
  separate tickets the loop runs independently.

## After the ticket: register it

Registering the ticket is a MANDATORY step, not a question: run `loopctl
register <slug>` as soon as the plan file is written, so the ticket is a
visible ledger row from birth rather than an invisible orphan. Reconcile is
the backstop (it auto-registers any plan whose slug is absent from the ledger
on the next run), but do not lean on it: register here. If a `ticket-planner`
sub-agent authored the plan, it returns only the path; you, the driver,
register.

## After the ticket: ask about the eval

Once the ticket is written, put the eval decision to the operator with
`AskUserQuestion` before moving on, recommended option first (author the
eval now / defer it / skip it). Co-authoring the eval with the
`create-eval` skill builds a small scenario set in the five-column
Behavior/Input/Expected/Scorer/Threshold template that makes the
Definition of Done concrete before implementation. This is the "eval is
the spec" step, and surfacing it as a real decision is not optional: a
ticket handed off without it is an incomplete handoff. When the change
carries a guardrail (a behavior it must refuse, or an invariant it must
not weaken), say so and recommend authoring the eval, since prose alone
leaves that wobbly.

If the consumer sets `require_eval` in `.loop/config.json`, the eval is
REQUIRED, not a choice: the loop refuses to pick the ticket up until the
marker exists, so state that it is mandatory and author it rather than
asking whether to.
