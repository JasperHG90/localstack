verdict: pass
tree: f3df0e128ec73c47f282fa7ad281a2ffe74f844b

# Adversarial review: reflection ticket

Reviewed the 9 in-scope files against `tickets/reflection.md` and the frozen
forks in `DECISIONS.md` section R (R1-R4). Both gates re-run independently and
pass; the tree fingerprint I computed matches the one I was given.

## Gate re-run (independent)

- `git add --intent-to-add -A . && uv run pytest` -> all tests pass (green).
- `uvx prek run --all-files` -> ruff-lint / ruff-format / mypy(strict) all Passed.
- `python3 scripts/loopctl.py verify` -> `ok`; `tree_fingerprint(.)` ->
  `f3df0e128ec73c47f282fa7ad281a2ffe74f844b` (exact match).

## Premise / decision-record conformance

- **R1 (enforce at finish, no new stage).** Enforcement lives in
  `ctl.done()` (`src/loop_harness/ctl.py:118-121`), placed after the
  slug-anchored-commit check, refusing when `verify_reflection(...).ok` is
  false. No `Stage` enum value added; `hooks.py` stage-classification sets are
  untouched (hooks.py not in the diff at all). Matches the non-goal.
- **R2 (committed per-slug files + stage into amend).** `cmd_finish` stages
  the artifact: `_git(repo, "add", ".loop/ledger.json", str(REFLECTIONS_DIR / f"{slug}.md"))`
  (`src/loop_harness/cli.py:69`), so the reflection rides the ticket commit.
  `test_finish_folds_ledger_into_the_slug_commit` asserts
  `git cat-file -e HEAD:.loop/reflections/<slug>.md` returns 0 and that the
  amend adds no extra commit (`rev-list --count == 2`). Failure mode #1 is
  closed and pinned.
- **R3 (controlled vocab + `other:` escape hatch).** `_valid_friction`
  (`reflection.py:221-225`) accepts a vocab term OR `other:` with a non-empty
  suffix; bare `other:` is rejected (`len(tag) > len(OTHER_PREFIX)`). Pinned by
  the `friction: [other:]` parametrize case. `distill` counts tags via
  `Counter` without interpreting them (failure mode #3 closed).
- **R4 (operator-run distill to ticket-planner).** `distill` / `format_distill`
  aggregate only; no automatic ticket creation. `format_distill` names the
  `ticket-planner` agent and hands it ranked friction.

## Enforcement refusal (both branches)

`verify_reflection` returns ABSENT (no file) and INVALID (schema failure), both
with `ok == False`, so `done()` refuses both. Confirmed by:
- `tests/test_ctl.py` full-lifecycle test: `pytest.raises(SystemExit, match="reflection absent")`
  before the reflection is written, then green after.
- `tests/test_cli.py::test_finish_refuses_without_a_reflection`: asserts the
  refusal AND that the stage stays `COMMIT` (ledger not mutated, since the check
  raises before `save_ledger`). These would fail against the old `done()`/
  `cmd_finish`, so they pin real behavior, not vacuous.

## Schema strictness balance (failure mode #2)

`parse_reflection` validates required-field presence, slug match, non-negative
ints, and the blocker/friction vocabularies only — never prose. Empty lists
pass (`_parse_list` returns `[]` for `[]`), and absent `harness_change` yields
`None` (not in `_REQUIRED_FIELDS`, read via `.get`). A freshly scaffolded,
unedited reflection is already schema-valid, so the schema cannot wedge `done`.
Pinned by `test_empty_lists_and_absent_harness_change_are_valid`.

## Test quality

Not vacuous. Distill test pins aggregation, frequency ranking
(`friction[0] == ("prek-first-pass-rewrite", 2)`), `other:` counting, blocker
counting, harness-change collection, and skip-invalid reporting
(`skipped == ("broken",)`). Three verdict branches each covered
(absent/invalid/valid). Scaffold test drives the real ledger to
`review_cycles == 1` and asserts the prefill plus the overwrite refusal
(`FileExistsError`). State-guard parity added: `.loop/reflections/some-ticket.md`
in the allow-list parametrize; the guard blocks only `{ledger.json, stamp.json}`
inside `.loop`, so reflections stay writable — this is a deliberate regression
guard per the ticket ("a future guard tightening cannot silently break it").

## Scope / hygiene-leakage

The 7 tracked-file diffs are surgical and every changed line traces to the
ticket. The `_drive_to_slug_commit` extraction in `test_cli.py` is shared setup
serving both the reworked fold test and the new refusal test — in scope. The two
new files (`reflection.py`, `test_reflection.py`) are the ticket's new module and
its mirror. The only other working-tree entry, `.loop/ledger.json`, is this
ticket's own loop-run state (the plugin running through its own loop); it is
excluded from the tree fingerprint and is not source/hygiene leakage. Module is
stdlib-only (collections/dataclasses/enum/pathlib + internal `ledger`) and
domain-agnostic. numpy-convention docstrings present on every new object (D1
green) and describe contracts, not types.

## Contract parity

`README.md` documents `reflect`/`distill` in the command list, "What ships",
and the "Extending" section, and correctly replaces the stale
"Planned (not yet built)" caveat with the now-built transition-level check.
`SKILL.md` adds step 7 (Reflect) and renumbers Close to step 8, matching the
enforced mechanism (finish requires a valid reflection and folds it in). No
hallucinated paths or commands.

## Findings

None blocking. No required fixes.
