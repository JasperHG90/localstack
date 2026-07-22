# reflection-derives-mechanical-facts

## 1. Title

Make the repo remember gate failures and derive the reflection's
mechanical numbers from recorded evidence, so the agent supplies only the
judgment (friction tags + prose) it alone can give.

## 2. Size / Effort

**M.** Three moving parts, none large: (a) a new append-only gate-failure
history log written when `loopctl stamp` produces a RED stamp, (b) a
schema shrink in `reflection.py` that stops requiring the self-reported
numeric fields, and (c) wiring `distill` to compose derived numbers
(ledger `review_cycles` + the new log) instead of ignoring them. Effort is
not volume; it is keeping the change coherent with a sibling fingerprint
ticket (§6, §9) and picking storage/compat forks that the operator must
settle first (§11), not the implementer.

## 3. Triggered by

Operator insight, confirmed in conversation: the reflection frontmatter
mixes two kinds of content — mechanical facts the system already records
(`cycles`, `gates_red`) and genuine judgment only the agent has (friction
tags, "what worked / what was hard"). `verify_reflection` checks schema
and existence only; it never checks whether the self-reported numbers are
TRUE. The signal meant to make the loop improve over time is therefore
agent-authored and unverified. The fix is not to police the self-report —
it is to delete the need for it: derive the mechanical facts from
evidence, and ask the agent only for what cannot be derived.

## 4. Context

Today's reflection schema requires six frontmatter fields
(`reflection.py:43`):

```python
_REQUIRED_FIELDS = ("slug", "cycles", "gates_red", "blockers", "friction", "worked")
```

Two of these are mechanical and one is only partly knowable:

- **`cycles` is already recorded.** The findings loop
  (adversarial-review -> gates) bumps `TicketEntry.review_cycles`
  (`ctl.py:83-84`), persisted in `.loop/ledger.json`
  (`ledger.py:62`, serialized `ledger.py:73`). `scaffold_reflection`
  even pre-fills `cycles` FROM the ledger already
  (`reflection.py:327-328`), then asks the agent to hand-transcribe it
  into frontmatter it could read directly. That round-trip is pure risk.
- **`gates_red` is NOT recorded anywhere durable.** `write_stamp`
  overwrites `.loop/stamp.json` on every run (`stamp.py:171-173`); the
  stamp is a latest-only snapshot. A ticket that goes RED, then RED again,
  then GREEN leaves only the final GREEN stamp on disk. The count of red
  gate runs over a ticket's life exists ONLY in the agent's memory — which
  is precisely why the reflection asks the agent for it. The repo forgets
  gate failures and outsources the memory to the agent.
- **`blockers` is only partly derivable.** `TicketEntry.blocker` holds a
  SINGLE current blocker (`ledger.py:63`), not a history, so a ticket that
  hit two blockers over its life records only the last. This makes
  `blockers` neither cleanly derivable nor cleanly judgment — see §11 Q3.

The sharper finding, confirmed by grep: **`distill` never reads `cycles`
or `gates_red` at all.** `distill` (`reflection.py:360-406`) updates only
the `friction`, `blockers`, and `worked` counters and collects
`harness_change`; `DistillSummary` (`reflection.py:100-125`) and
`format_distill` (`reflection.py:409-445`) carry no numeric aggregate.
`grep -rn '\.cycles\|\.gates_red' src/` returns nothing. So today the two
numeric fields are **required of the agent but consumed by no one**: pure
cost (an unverified self-report the schema enforces) with zero benefit
(the aggregation that would use them does not exist). The fix removes the
cost AND, for the first time, wires the derived numbers into distillation
so the signal actually exists and is trustworthy.

This strengthens the harness's core bet, stated as invariant I13
(`MANIFESTO.md:171-176`): a ticket cannot close without a schema-valid
reflection, because the reflection is the loop's one mandatory feedback
channel. A feedback channel whose numbers are self-reported and unverified
is a channel that can lie. Deriving the numbers from evidence makes the
mandatory feedback loop as trustworthy as the stamp itself.

## 5. Non-goals / out of scope

- **Do not grade prose.** `verify_reflection` stays schema/existence only
  (I13; DECISIONS.md R1). "Prompts may" grade quality; "code must" only
  checks shape.
- **Do not add a lifecycle stage.** Enforcement stays at finish via
  `ctl.done()` (DECISIONS.md R1). No new `Stage` enum member.
- **Do not change the fingerprint policy in this ticket.** Binding
  `.loop/config.json` into the fingerprint is the sibling ticket
  `fingerprint-binds-loop-config` (§9). This ticket only ensures its new
  log stays on the EXCLUDED side of whatever policy that ticket lands.
- **Do not build blocker-history persistence.** Turning
  `TicketEntry.blocker` into a list is a separate change; this ticket
  scopes `blockers` per the Q3 decision, nothing more.
- **Do not auto-create tickets from distilled numbers.** Distillation
  stays operator-run and hands friction to `ticket-planner` (DECISIONS.md
  R4).
- **No new runtime dependency.** The core is stdlib-only
  (`MANIFESTO.md:197`); the log is JSON lines via `json`.

## 6. Requirements & restrictions

Must achieve:

- **R-A. The repo remembers gate failures, not the agent.** When
  `loopctl stamp` produces a RED stamp, append one event to a durable,
  append-only per-ticket record capturing at minimum: ticket slug,
  timestamp, the gate command(s) that failed (with exit codes), and the
  tree fingerprint the gates ran on. Appended, never overwritten, so N red
  runs leave N events. (Storage form: Q1.)
- **R-B. Derive the mechanical numbers from evidence at distill time.**
  `distill` composes `cycles` from ledger `review_cycles` and `gates_red`
  from the new log, per slug, and surfaces them in `DistillSummary` /
  `format_distill`. The derived numbers are authoritative; nothing the
  agent writes in frontmatter can change them.
- **R-C. Shrink the schema to judgment-only.** The agent supplies only the
  non-derivable fields: `slug`, `friction`, `worked`, and optional
  `harness_change`. `cycles` and `gates_red` are no longer REQUIRED of the
  author. (Full-remove vs keep-as-hint: Q2.)
- **R-D. Old reflections still parse.** Every existing file under
  `.loop/reflections/` (all carry `cycles:`/`gates_red:`) must remain
  schema-valid so `distill` and `verify_reflection` keep reading them (see
  the 12 committed reflections; `stamp-fingerprint-ignore-list.md` is a
  representative). Validation leniency per Q2.

Restrictions the repo states, each cited:

- **I13 grain — enforce at an existing point, do not grade prose**
  (`MANIFESTO.md:171-176`; DECISIONS.md R1).
- **Reflections are committed per-slug evidence** like verdicts
  (DECISIONS.md R2; `reflection.py:11-15`). The new log is evidence of the
  same family (Q4 decides git-tracking).
- **The fingerprint certifies the CODE tree; loop state never stales it**
  (`stamp.py:69-71`). `tree_fingerprint` subtracts all of `.loop` from a
  throwaway index (`stamp.py:110`). The new log MUST stay subtracted (§9).
- **Controlled friction vocabulary with `other:` escape** is unchanged
  (DECISIONS.md R3; `reflection.py:32-41`).
- **Docstrings track behavior** (numpy convention): any signature or field
  change updates the docstring in the same edit
  (`.claude/rules/python-docstrings.md`).
- **Every change ships a test; no mocking the git/FS layer**
  (`.claude/rules/python-testing.md`).
- **Stdlib-only core** (`MANIFESTO.md:197`).

## 7. Code surface

Schema and distillation — `src/loop_harness/reflection.py`:

- `reflection.py:43` `_REQUIRED_FIELDS` — drop `cycles` and `gates_red`
  (and `blockers` per Q3) from the required tuple.
- `reflection.py:55-83` `Reflection` dataclass — remove the `cycles` and
  `gates_red` attributes (Q2: full-remove) or demote them to ignored hints;
  update the `Attributes` docstring accordingly.
- `reflection.py:228-281` `parse_reflection` — stop requiring/reading the
  numeric fields; extra keys in old files are already tolerated (the
  parser reads specific keys and ignores the rest, `reflection.py:252-272`),
  which is the mechanism R-D relies on — confirm and pin it with a test.
- `reflection.py:312-352` `scaffold_reflection` — remove `cycles:` and
  `gates_red:` from the emitted template (currently `reflection.py:333-334`,
  and the ledger read at `reflection.py:327-328` that pre-fills `cycles`).
- `reflection.py:100-125` `DistillSummary` — add fields carrying the
  derived per-ticket numbers (e.g. `gates_red` and `cycles` totals or
  per-slug pairs); update docstring.
- `reflection.py:360-406` `distill` — read `review_cycles` from
  `load_ledger(repo)` (already imported, `reflection.py:25`) and read the
  new gate-failure log per slug; compose the derived numbers into the
  summary. Keep the "schema-invalid files are skipped, never dropped"
  behavior.
- `reflection.py:409-445` `format_distill` — render the derived numbers in
  the ticket-planner briefing.

Gate-failure log (new) — module + write path:

- New: a small append-only writer/reader. Recommended home a new
  `src/loop_harness/history.py` (mirrors `stamp.py`'s single-responsibility
  shape) OR a helper in `stamp.py`; storage form is Q1. Path recommended
  `.loop/history/<slug>.jsonl`.
- `src/loop_harness/cli.py:40-48` `cmd_stamp` — after `run_gates` /
  `write_stamp` / `verify_stamp`, when the verdict is RED, append the
  failure event. `cmd_stamp` already holds `results` (the `GateResult`
  list with exit codes) and the config; the failing subset is
  `[r for r in results if r.exit_code != 0]`. This is the single blessed
  place a RED stamp is produced by the CLI.
- `src/loop_harness/stamp.py:143-174` `write_stamp` / `stamp.py:53-58`
  `GateResult` — read-only reference for the tree fingerprint and the
  per-gate exit data the event records; do not change the stamp payload.

Evidence sources consumed (read-only, no change):

- `src/loop_harness/ledger.py:62` `TicketEntry.review_cycles` and
  `ledger.py:110-117` `load_ledger` — the `cycles` source.
- `src/loop_harness/hooks.py:246-269` `_tree_from_verdict_file` /
  `verdict_tree` — verdict files as corroborating evidence, if Q3/derivation
  needs them.

Config / ignore surface:

- `.gitignore` — currently ignores `.loop/stamp.json` (churny) while
  tracking `.loop/reflections/` (evidence). Q4 decides whether
  `.loop/history/` is added here.

Docs to update in the same change (they describe the schema/loop):

- `MANIFESTO.md:171-176` (I13) and `MANIFESTO.md:69` (the `reflection.py`
  role line) — reflect that mechanical numbers are now derived, not
  self-reported; consider a new invariant "the repo remembers gate
  failures." Any `.md` edit runs the slop-scan rule
  (`.claude/rules/slop-scan-for-docs.md`).
- `DECISIONS.md` R-section — record the schema shrink and derivation as a
  new sub-decision under R (the design change is exactly what R governs).

## 8. Tests & validation gates

Repo gates (the blessed invocation is the `just check` recipe;
`justfile:4-7`): `git add --intent-to-add -A .` then `uv run pytest` then
`uvx prek run --all-files` (ruff-lint, ruff-format, mypy). This repo
self-hosts the loop: `.loop/config.json` sets `require_eval: true` and two
review passes — `adversarial` (loop-reviewer) and `architectural`
(loop-architect, baseline `MANIFESTO.md`). Author the eval marker first
(§ handback). No CI workflow exists; the gates and review passes ARE the
gate.

Tests to add (real temp repos via the `repo` fixture in
`tests/conftest.py`; never mock git or the filesystem, per
`.claude/rules/python-testing.md`):

- **Gate-failure log accumulates.** In `tests/test_stamp.py` (or a new
  `tests/test_history.py` if the writer lands in a new module — pick to
  match the writer's home): drive a ticket RED N times then GREEN through
  the stamp path and assert the log holds exactly N failure events, each
  carrying slug, timestamp, the failing command(s)+exit codes, and the
  tree. Assert a GREEN run appends nothing.
- **Derivation matches reality, ignoring the body.** In
  `tests/test_reflection.py`: with a ledger `review_cycles` of C and a log
  of N failure events, `distill` reports `cycles == C` and
  `gates_red == N` for that slug EVEN WHEN the reflection body omits the
  numbers or states contradictory ones. This is the anti-self-report
  assertion.
- **Shrunk schema validates with judgment only.** In
  `tests/test_reflection.py`: a reflection carrying only
  `slug`/`friction`/`worked` (+ optional `harness_change`) and prose parses
  VALID with no `cycles`/`gates_red`.
- **Old-schema reflections still parse (R-D).** In
  `tests/test_reflection.py`: a file that still carries `cycles:` and
  `gates_red:` (the current format, as in the committed reflections) parses
  VALID; `distill` ignores the stale numbers and uses the derived ones.
- **Scaffold no longer emits numeric fields.** In
  `tests/test_reflection.py`: `scaffold_reflection` output has no `cycles:`
  or `gates_red:` line and re-parses VALID.

The existing `tests/test_reflection.py` `VALID` fixture and any test
asserting `_REQUIRED_FIELDS` membership or reading `Reflection.cycles`/
`.gates_red` will need updating in lockstep (pre-existing-issues rule:
fix, do not skip). Every test file named here is listed in §7.

## 9. Risk assessment

- **Blast radius.** `reflection.py` (schema + distill), one new small
  module or `stamp.py` helper, `cli.py` `cmd_stamp`, plus doc/decision
  edits. `distill` and `cmd_stamp` are the only behavior changes on hot
  paths; both are covered by the tests above.
- **Cross-ticket fingerprint coherence (the load-bearing risk).** The
  sibling ticket `fingerprint-binds-loop-config` (#1) changes
  `tree_fingerprint` (`stamp.py:61-115`) to BIND `.loop/config.json` (the
  verification contract) while still excluding churny `.loop` state. The
  new gate-failure log is churny STATE, not contract, so it MUST stay
  EXCLUDED — otherwise every gate run would mutate the tree and stale the
  stamp it just wrote, deadlocking the loop. Today `stamp.py:110` subtracts
  all of `.loop`, so a log under `.loop/history/` is excluded
  automatically. This stays safe **as long as #1 re-binds only
  `config.json`, not all of `.loop`, and the log lives elsewhere under
  `.loop/`.** If #1 lands first, confirm its include-list names
  `config.json` specifically. If this ticket lands first, leave a note in
  §7's `stamp.py` region so #1's author keeps the log excluded. Coordinate
  so the include/exclude policy stays coherent across both tickets.
- **Reversibility.** High. The schema shrink is additive-tolerant (old
  files still parse); the log is new and side-effecting only on RED;
  reverting restores the self-report. No ledger migration.
- **Likeliest failure modes.** (1) Silently deciding a fork in §11 instead
  of blocking — the loop's `unresolved-design-fork` block exists for this.
  (2) Putting the log where the fingerprint would pick it up (regression of
  the §9 risk). (3) Breaking R-D by making `parse_reflection` reject the
  now-unknown `cycles`/`gates_red` keys — the parser must keep ignoring
  extra keys. (4) A RED-stamp append that raises and aborts stamping — the
  append must not turn a gate result into a crash.

## 10. Subtickets

Ordered, dependency-aware:

1. **Gate-failure history log (R-A).** Add the append-only writer/reader
   (form per Q1) and call it from `cmd_stamp` on a RED verdict. Test:
   log accumulates N events; GREEN appends nothing; append never crashes
   stamping. (Independent; no schema change yet.)
2. **Wire derivation into distill (R-B).** Read `review_cycles` and the
   log in `distill`; surface derived numbers in `DistillSummary` /
   `format_distill`. Depends on 1. Test: derivation matches reality and
   ignores the body.
3. **Shrink the schema (R-C, R-D).** Drop the numeric fields from
   `_REQUIRED_FIELDS`, `Reflection`, `parse_reflection`, and
   `scaffold_reflection` (per Q2/Q3); confirm old files still parse.
   Depends on 2 (so the numbers have a derived home before the
   self-reported ones are removed). Test: shrunk schema valid; old schema
   valid; scaffold emits no numeric fields.
4. **Docs + decision record.** Update `MANIFESTO.md` I13 and the role
   line, add the R sub-decision to `DECISIONS.md`, resolve Q4 in
   `.gitignore`. Depends on 1-3 landing.

## 11. Open questions

Route each to `DECISIONS.md` before pickup (fork-block discipline: an
unanswered fork is a `blocked` state, not a judgment call).

- **Q1. Storage form of the gate-failure log.** Per-slug JSON-lines file
  `.loop/history/<slug>.jsonl` vs a new list field on the ledger
  `TicketEntry`. *Recommendation:* per-slug `.jsonl`. It mirrors the
  per-slug evidence pattern (`verdicts/`, `reflections/`), keeps
  append-only semantics trivially (one line per event, no read-modify-write
  race), and keeps the churny high-frequency gate log out of the
  atomically-rewritten ledger that reconcile treats as durable truth.
- **Q2. Full-remove vs keep-as-hint for `cycles`/`gates_red`.** Delete the
  fields from the schema and dataclass entirely, or keep them as
  optional agent-provided hints that get reconciled against (and always
  overridden by) the derived truth. *Recommendation:* full-remove. Keeping
  a field the agent fills but the system overrides re-creates the exact
  "unverified self-report" this ticket deletes, and invites the agent to
  spend effort on a number that is thrown away. Derived-only is the honest
  contract. (R-D is satisfied either way, since the parser ignores unknown
  keys.)
- **Q3. Is `blockers` derived, kept as judgment, or left as-is?** The
  ledger records only the CURRENT blocker (`ledger.py:63`), not a history,
  so `blockers` is not cleanly derivable today. *Recommendation:* leave
  `blockers` in the schema as an agent-supplied field for THIS ticket
  (scope creep to derive it needs blocker-history persistence, a separate
  change) and note the limitation. Do not silently drop it.
- **Q4. Is `.loop/history/` git-tracked or gitignored?** It is evidence
  the reflection derives from (argues tracked, like `reflections/` and the
  ledger) yet churny per-gate-run state (argues ignored, like
  `stamp.json`). *Recommendation:* track it. `distill` reads it as durable
  evidence, and a peer reviewing a closed ticket should see the same
  failure history the derivation used; tracking matches R2's "committed
  per-slug evidence." Either way it stays out of the fingerprint (§9), so
  tracking does not risk staling stamps.
