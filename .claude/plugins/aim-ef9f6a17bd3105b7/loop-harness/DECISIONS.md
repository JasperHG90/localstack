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

R5. **Mechanical numbers are derived, not self-reported (ticket:
    reflection-derives-mechanical-facts, adopted 2026-07-06).** The
    reflection's `cycles` and `gates_red` were required of the author but
    verified by nothing and read by no aggregator, so the loop's one
    mandatory feedback channel could lie. They are now DERIVED from evidence,
    and the schema asks the agent only for judgment (friction plus prose).
    - **Repo remembers gate failures.** A RED `loopctl stamp` appends an
      event (slug, timestamp, failing command(s) with exit codes, tree) to a
      per-slug JSON-lines log at `.loop/history/<slug>.jsonl` (Q1),
      append-only, so N red runs leave N events. `distill` composes `cycles`
      from ledger `review_cycles` and `gates_red` from this log; the derived
      numbers are authoritative.
    - **Full-remove, not keep-as-hint (Q2).** `cycles` and `gates_red` are
      dropped from the required schema and the dataclass, not kept as
      overridden hints: a field the system overrides re-creates the
      unverified self-report this removes. Old reflections still parse
      because the parser ignores unknown keys.
    - **`blockers` stays agent-supplied for now (Q3).** The ledger records
      only the current blocker, not a history, so `blockers` is not cleanly
      derivable. Deriving it needs blocker-history persistence, a separate
      change.
    - **`.loop/history/` is git-tracked (Q4),** like `reflections/` and
      verdicts: it is per-slug evidence a peer reviewing a closed ticket
      should see. It stays out of the tree fingerprint (churny state), which
      holds as long as section F binds only `config.json`.

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

## F. Fingerprint binds the verification contract (ticket: fingerprint-binds-loop-config)

Adopted 2026-07-06. The stamp binds gate exit codes to a git tree
fingerprint, but the definition of "green" (`gates`, `fingerprint_ignore`)
lives in `.loop/config.json`, which the fingerprint stripped along with all
of `.loop/`. An agent could weaken a gate or widen the ignore-list and keep a
green, "fresh" stamp. The contract was agent-editable and unbound.

F1. **Bind `.loop/config.json` into the fingerprint; keep the rest of
    `.loop/` excluded.** A change to the config now stales the stamp and
    forces a re-stamp and re-review, exactly like a code change. Editing
    config stays legal (a documented workflow) but stops being free. The
    churny state files (`ledger.json`, `stamp.json`, `verdicts/`,
    `reflections/`, `history/`, `handoff.log`, `HALT`) stay excluded, which
    is why only `config.json` is bound, never the whole directory.

F2. **Bind the whole file, not a chosen key subset (Q1).** Whole-file
    binding is the simplest code, stays single-sourced through
    `tree_fingerprint`, and binds the entire contract (including
    `review_passes` and `require_*`). Its only cost is a harmless re-stamp on
    a cosmetic edit, which is legitimate work (re-run the gates on the exact
    tree), not incorrectness. A key-subset hash would add code and a second
    judgment call about which keys count.

F3. **No `config.py` validation against a self-excluding ignore-list (Q2).**
    An adversarial `fingerprint_ignore` naming `.loop/config.json` is
    neutralized by re-binding config AFTER the ignore loop, proven by a test.
    A loud `ConfigError` on that pathspec would be redundant code.

F4. **Rejected: a hook forbidding edits to `config.json`.** A state-guard
    blocks only Edit/Write, so a Bash write bypasses it, and forbidding edits
    fights the documented config workflow. The goal is not "config cannot
    change" but "changing the contract invalidates the evidence."

## G. Git-level commit backstop (ticket: commit-gate-git-hook-backstop)

Adopted 2026-07-06. The commit gate is a Claude Code PreToolUse hook that
matches `git commit` in the Bash tool string, so it cannot see commits that
never surface as a matchable string: `$(git commit)`, `eval`, a subprocess,
or a human at the terminal. A git-level `pre-commit` hook that reuses the
same `decide_commit_gate` policy closes the class no string matcher can
reach, without replacing the PreToolUse front-line block (defense in depth).

G1. **Explicit install, not automatic (Q1).** A `loopctl install-git-hook`
    and `uninstall-git-hook` pair, surfaced in the SessionStart guidance.
    Writing into a user's `.git/` is a deliberate, visible, reversible
    operator act, not a side effect of `loopctl init`.

G2. **Refuse-and-warn, never clobber (Q2).** A pre-existing unmanaged
    `pre-commit` hook or a set `core.hooksPath` makes install refuse with a
    clear message; the harness never silently destroys or chains onto an
    existing hook. Chaining is revisited only if a consumer needs it.

G3. **A single managed `.git/hooks/pre-commit` file (Q3),** not
    `core.hooksPath`. Setting `core.hooksPath` disables the default hooks
    directory wholesale; a single file is surgical, easy to detect and
    uninstall, and least surprising. A set `core.hooksPath` is treated as the
    refuse-and-warn case from G2.

G4. **Uninstall removes only the managed hook (Q4),** restores any hook it
    displaced, and is a no-op when nothing managed is present; install is
    idempotent.

G5. **Reuse `decide_commit_gate` unchanged via a canonical command (Q5).**
    The git entry passes a canonical `"git commit"` so the policy's
    `_invokes_git_commit` guard fires, keeping one policy function and no
    `hooks.py` edit. HALT parity, dormancy, and the fail-open-on-internal-
    error split are preserved at this second enforcement point.

G6. **Land after `commit-gate-targets-the-committed-repo` (Q6).** The two
    tickets share `decide_commit_gate`; sequencing after the in-flight
    sibling keeps the reused policy stable and avoids churning the matcher
    twice.

## P. Plan-ledger reconciliation (ticket: reconcile-registers-orphan-plans)

Adopted 2026-07-06. A ticket is a plan file plus a ledger entry referencing it;
registering the entry was a separate, easy-to-miss step, so orphan plans
accumulated invisibly. Reconcile now guarantees the invariant plan-on-disk maps
to a ledger entry (MANIFESTO I17).

P1. **Enforcement is reconcile, not a write-time hook (Q-settled).** The plans
    pass keys on the plan file's existence, so a missed registration is
    recovered on the next reconcile and `loopctl register <slug>` is always
    available. A PostToolUse hook that registered on the plan-file write was
    rejected: a one-shot that, on failure or fail-open, orphans the plan
    forever. Reconcile also does NOT collapse creation into a `loopctl new`
    command; free-writing a plan file stays legal.

P2. **Auto-register orphans at `ready`; never silently drop (Q1, Q2).** The
    bias is "no lost tickets", not "no drafts": an unwanted auto-registered
    draft is `loopctl drop`-able. No new stage is added; a `ready` orphan still
    cannot advance without an eval (`require_eval`). The plan path is derived
    from the slug, not stored (Q3).

P3. **Reverse orphans warn, never delete (Q1).** An entry whose plan is missing
    warns only when non-terminal and not dropped; `done`/`blocked`/`dropped`
    entries are silent (their plans are legitimately gone). Reconcile never
    deletes a ledger entry. Full reverse-orphan handling (rename detection) is a
    follow-up.

P4. **Repo-contained plans only (Q5).** A `plans_dir` resolving outside the
    repo (the shared-home default `~/.claude/plans`) auto-registers nothing, so
    one repo's ledger never pulls another repo's plans.

P5. **Fire at `loopctl reconcile` and SessionStart (Q6).** SessionStart now
    persists the ledger when it registers an orphan; harness-written state,
    best-effort, fail-open-wrapped.

P6. **"Dropped" is a flag on `TicketEntry`, not a `Stage` member (Q7,
    load-bearing).** Drop is a reversible retirement orthogonal to lifecycle
    position, so it is modeled as `dropped: bool`, keeping the closed `Stage`
    enum closed (honoring the I1 / R1 / S1 grain) and preserving the pre-drop
    stage across an un-drop. Un-drop is `loopctl register <slug>` clearing the
    flag. A terminal `dropped` stage was the considered alternative (symmetric
    with `done`); the flag was chosen as the narrower diff that does not
    conflate two axes.

## Q. Decision prompts in skills (ticket: skills-prompt-decisions-via-qa)

Adopted 2026-07-06. Skills surfaced operator decisions as easy-to-miss soft
prose; genuine discrete forks now use the Claude Q&A feature
(`AskUserQuestion`). The convention is recorded in `AGENTS.md` (Project
conventions) so future skills inherit it (Q2).

Q1. **Convert only discrete forks; free-form authoring stays prose.** In
    `create-eval`, the scenario count and, per row, keep/cut, the Scorer
    choice, and the Threshold choice become `AskUserQuestion` (recommended
    option first); the Behavior/Input/Expected drafting stays prose. In
    `create-ticket`, the eval handoff becomes a Q&A. The failure mode to avoid
    is a gimmicky multiple-choice skill that forces open-ended work into
    buttons.

Q2. **The convention gets a durable, tracked home in `AGENTS.md`** (its Project
    conventions section), plus the per-skill edits. `.claude/rules/` is NOT a
    viable home here: every rule under it is aim-vendored from an external repo
    and `.claude/` is gitignored, so a local file there is an untracked orphan
    that aim would overwrite. `AGENTS.md` (symlinked as `CLAUDE.md`) is tracked
    and auto-loaded, so a future skill author sees the rule from the repo, not
    only from Memex KV.

Q3. **`implement-ticket` stays out of scope.** Its forks are `loopctl block`
    codes for an often-unattended loop where `AskUserQuestion` has no operator
    to answer; the block route is correct there.

Q4. **The Q&A fires in the driver, not the planner.** `ticket-planner` stays a
    read-only, return-a-path subagent; the interactive prompt lives in the
    `create-ticket` driver context. The planner carries only a one-line note
    saying so.

Q5. **The `documentation` review pass is not enabled for this change.** The
    slop-scan rule already covers `.md` freshness, and enabling a pass is a
    config change that would stale the stamp and widen scope.
