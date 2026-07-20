# DECISIONS

The loop-harness plugin's own decision record: design choices about the
tool itself, frozen so an implementer treats an unanswered fork as a
`blocked` state rather than a judgment call. Decisions about how a
particular repo *consumes* the harness stay in that consumer's own
decision record; only decisions about the harness's design live here.

## R. Reflection (ticket: reflection)

Adopted by the operator 2026-07-03, moved here from the first
consumer's decision record 2026-07-05 (a decision about the tool
belongs with the tool).

R1. **Enforcement point: at finish.** `loopctl finish` (via
    `ctl.done()`) refuses to close a ticket without a schema-valid
    `.loop/reflections/<slug>.md`. Existence and schema are mechanically
    checked ("code must"); reflection quality stays a skill instruction
    ("prompts may"). No new lifecycle stage is added.

R2. **Location: committed per-slug files** under `.loop/reflections/`,
    exactly like `.loop/verdicts/`. No state-guard carve-out is needed
    (the guard covers only `ledger.json` and `stamp.json`), and `.loop/`
    is excluded from the tree fingerprint, so a reflection written late
    in the lifecycle does not stale a green stamp.

R3. **Schema: a controlled friction vocabulary with an `other:` escape
    hatch,** so `loopctl distill` aggregates mechanically while new
    patterns are still captured and can be promoted to tags later.

R4. **Distillation: operator-run `loopctl distill`.** It aggregates the
    reflection frontmatter and hands recurring friction to the
    `ticket-planner` agent, which authors improvement tickets that flow
    through the normal loop protocol. No threshold-triggered automatic
    ticket creation: automating when a ticket is born is itself an
    operator-owned decision.

## S. Selectable stages (tickets: loop-config-review-passes,
loop-commit-gate-n-verdicts, loop-review-agents, loop-config-action-stages,
loop-doc-writer-and-custom-stages)

Adopted 2026-07-05. Stages become selectable in `.loop/config.json` without
dissolving the enforced spine or the closed `Stage` enum.

S1. **Review is N config-selected passes, not a new stage.** The single
    reviewer verdict generalizes to a list of `review_passes`, each writing
    its own tree-bound verdict; the commit gate requires every enabled
    pass. This runs INSIDE the existing `adversarial-review` stage, so
    `Stage` and `_ORDER` are unchanged: it EXTENDS the commit criterion (N
    verdicts, not one) rather than adding a lifecycle stage, honoring R1's
    grain (enforce at an existing point, do not grow the state machine).

S2. **Review is disableable, but only deliberately.** Adversarial review
    ships on; the architectural and documentation passes are opt-in. An
    empty or all-disabled `review_passes` is a loud `ConfigError` unless
    `require_review: false` is set explicitly, which gates commits on the
    stamp alone and is warned at session start. The commit-gate hook fails
    SAFE: a malformed config falls back to the mandatory adversarial pass,
    never to zero, so a broken config blocks rather than falls open.

S3. **Action stages are advisory by honesty.** `action_stages` dispatch a
    project artifact (an `agent` or a `skill`) at an anchor but write no
    verdict and gate nothing. The harness's only evidence primitive is the
    tree fingerprint; an action leaves no tree-bound artifact it can
    re-derive, so recording that one "ran" would be an unverified claim,
    exactly what R1 refuses. Doc freshness is therefore enforced by the
    `documentation` review pass (which writes a verdict), while the
    `loop-doc-writer` action only writes the docs. A tree-mutating action
    runs at `after: implementing` so its edits ride the stamped tree.

S4. **Custom stages reference project-bound artifacts by name.** A custom
    review pass or action stage names an agent or skill in the consumer's
    normal `.claude/` locations, dispatched by the skill; the harness
    resolves no paths. Hooks stay the separate, event-driven surface
    (`hooks/hooks.json`); a stage is something the skill actively
    dispatches, so stage `type` is `agent` or `skill`, not `hook`.
