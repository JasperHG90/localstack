---
name: implement-ticket
description: Run one planning ticket through the loop lifecycle - perceive (ledger + git reconcile), implement tests-first, gate via `loopctl stamp`, self-review, adversarial review, commit, close via `loopctl finish`. Use when asked to implement the next ticket, run the loop, or continue autonomous ticket implementation.
---

# implement-ticket

One invocation implements exactly one ticket, end to end, with every
stage transition backed by evidence. The model proposes; the harness
verifies. Never claim a stage; earn it.

`loopctl` is the harness CLI. The SessionStart hook prints its exact
invocation path as `[loop] ctl: ...`; if the repo's task runner wraps
it (a justfile or Makefile), prefer those recipes — they encode the
same commands.

## Ground rules

- One ticket per invocation. After `loopctl finish`, STOP.
- Git is ground truth. The ledger records what git cannot (stage,
  attempts, blockers).
- Ledger writes go ONLY through `loopctl` (`register`, `advance`,
  `block`, `finish`). Direct edits to `.loop/ledger.json` are blocked
  by the state-guard hook; every `advance` re-validates the transition
  against live evidence.
- An unresolved design fork (not answered by the ticket, the repo, or
  the repo's decision record, e.g. `DECISIONS.md`) is a `blocked`
  state with code `unresolved-design-fork`. Surface it to the operator
  and stop work on that ticket; never pick an option silently.
- `.loop/HALT` engaged means do nothing: report the halt reason and
  stop.

## Protocol

1. **Perceive.** Run `loopctl reconcile`, then `loopctl ledger`. If
   HALT is engaged, stop. Pick the next ticket whose ledger stage is
   `ready` and whose dependencies (per the repo's roadmap document,
   when one exists) are `done`. Then `loopctl register <slug>` and
   `loopctl advance <slug> implementing`.
   - **Eval precondition (when `require_eval` is set).** The advance into
     `implementing` is refused unless a schema-valid eval marker exists at
     `.loop/evals/<slug>.md`. Recover by run mode. Supervised (an operator
     is present): run the `create-eval` skill to co-author the marker, then
     retry the advance. Unattended (a recurring loop, no operator to
     co-author with): do NOT retry - run `loopctl block <slug> eval-missing
     "no eval marker; author with create-eval"` and notify the operator,
     then stop on this ticket. Retrying only re-registers and re-fails every
     wake.
2. **Implement, tests first.** The ticket file (in the configured
   plans directory, default `~/.claude/plans/`) is the contract. Every
   behavior change starts with a failing test. Touch only what the
   ticket's Code surface declares; needing more is the
   `out-of-scope-fix-needed` blocker, not a judgment call. If an enabled
   `action_stages` entry runs at `after: implementing` (any stage that
   edits the tree, e.g. `update-documentation`), dispatch its artifact
   NOW, before the stamp, so its edits are stamped, reviewed, and
   committed with the code. A tree-mutating stage run after the stamp
   stales it and forces a re-gate.
3. **Gate.** First clear the cheap, deterministic checks so a lint-only
   defect does not cost a full re-stamp. Run the repo's configured
   lint/format/type hooks over the changed files through the blessed
   invocation (here, `uvx prek run --files <changed>`), let any rewrites
   land in the tree, and fix any failure rather than silence it. This pass is a
   convenience, not a substitute for the stamp: the type hook still runs
   over its whole configured target inside it, and `loopctl stamp`
   re-runs every gate. Then run `loopctl stamp` (executes the repo's
   configured gate commands and records the evidence). Red gates: fix and
   re-stamp. Then `loopctl advance <slug> gates` (refused without a fresh
   stamp).
4. **Self-review.** Re-read the diff against the ticket. Every changed
   line must trace to the ticket. `loopctl advance <slug> self-review`
   (requires a green stamp).
5. **Review.** `loopctl advance <slug> adversarial-review` (the review
   stage). First capture ONE tree fingerprint and reuse it for every
   pass: confirm `loopctl verify` is OK, then read the `tree` field from
   `.loop/stamp.json` (the exact tree the gates certified). Read
   `.loop/config.json` and dispatch EVERY enabled `review_passes` entry
   CONCURRENTLY, as a single fan-out batch rather than one at a time. Give
   each pass the ticket path, the diff scope, the repo's gate commands,
   that one shared tree fingerprint, the verdict path
   `.loop/verdicts/<slug>.<id>.md`, and any pass input (the architectural
   pass also gets its `baseline` doc). Every pass binds its verdict to the
   SAME captured fingerprint. Then JOIN: wait for all dispatched passes to
   finish before deciding anything. The passes are independent (they read
   the same frozen tree and each writes its own verdict file under
   `.loop/`, which is excluded from the fingerprint, so they cannot
   collide or drift the tree), so order does not matter. Each agent writes
   its OWN verdict file, including the `tree:` line the commit gate parses.
   The reviewers are the sole parties that can pass review, and the commit
   gate requires a passing, tree-bound verdict from EVERY enabled pass.
   With review deliberately disabled (`require_review: false`, no enabled
   pass), skip this dispatch; the stamp alone gates the commit.
   - Findings confirmed (from ANY pass, judged once all have reported at
     the join): fix, then `loopctl advance <slug> gates` (this counts the
     review cycle; at the configured cap the advance is refused - block
     with `cap-exceeded`). Re-stamp, capture the new fingerprint, then
     re-run ALL enabled passes as one fresh concurrent batch against the
     new tree. It is all-or-nothing: the gate needs every pass bound to
     the same new tree, so a single pass is never re-run alone.
   - Finding disputed: `loopctl block <slug>
     disputed-reviewer-finding "<reason>"` and escalate to the
     operator. Never argue indefinitely.
6. **Commit.** `loopctl advance <slug> commit` (refused unless the
   stamp is green AND the verdict is bound to the exact current tree).
   Commit with the subject `<slug>: summary` - the reconciler matches
   on that anchor and the commit gate re-verifies everything
   independently.
7. **Reflect.** `loopctl reflect <slug>` scaffolds
   `.loop/reflections/<slug>.md`. Fill in what worked and what worked
   less well: tag friction from the controlled vocabulary (or
   `other:<slug>` for a new pattern), record the review `cycles`,
   `gates_red`, and `blockers` hit, and add an optional one-line
   `harness_change`. Re-run `loopctl reflect <slug>` to validate. The
   reflection is in `.loop/` (excluded from the tree fingerprint), so it
   does not stale the stamp; `finish` refuses to close without a
   schema-valid one and folds it into the ticket commit.
8. **Close and stop.** `loopctl finish <slug>` - closes the ticket
   (requires the slug-anchored commit AND a valid reflection), folds
   the ledger update and the reflection into that commit via amend,
   reconciles, and notifies the operator. Stop.

## Action stages

`.loop/config.json` may declare `action_stages`: advisory artifacts (an
`agent` or a `skill`, named by `ref`) the loop dispatches at a lifecycle
anchor. They are NOT review passes: they write no verdict and gate
nothing, so the harness cannot prove one ran; you honor them. For each
ENABLED action stage, dispatch its `ref` at its `after` anchor (a
`type: agent` via a sub-agent, a `type: skill` via that skill), passing
the ticket and diff context. A tree-mutating stage (a doc-writer) must run
at `after: implementing`, before the stamp (step 2), so its edits are
committed with the code; a stage at `after: done` (a report-out) runs
after `finish` and is purely informational. To guarantee docs stay fresh,
enable the `documentation` review pass, whose verdict gates the commit;
the doc-writer action only writes them.

## Driver contract

This skill is the ITERATION, not the driver. Each invocation runs one
ticket and stops; whoever wants more tickets invokes it again. The
supported drivers are the operator saying "implement the next ticket"
(supervised) and a recurring loop command (unattended; the operator
clears the loop to rest it). Goal-condition hooks make poor drivers -
their judges cannot see the one-ticket contract. The enabled review
passes run concurrently as one fan-out batch and the driver awaits the
join before deciding; stopping while they run is permitted (stage
`adversarial-review` does not block the stop-check).

## Blocker codes

`unresolved-design-fork`, `out-of-scope-fix-needed`, `gate-flake`,
`disputed-reviewer-finding`, `environment-breakage`, `cap-exceeded`,
`eval-missing`.
Every `blocked` entry carries a code plus a one-line reason the
operator can act on (`loopctl block <slug> <code> "<reason>"`).
