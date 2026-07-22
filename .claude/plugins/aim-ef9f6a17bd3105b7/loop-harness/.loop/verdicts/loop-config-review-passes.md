verdict: pass
tree: 18b863cece9723fd84238d10d3147c95c99666a5

# Adversarial review — loop-config-review-passes

Reviewer: loop-reviewer (independent). Reviewed the uncommitted working-tree
diff against HEAD, scoped to `src/loop_harness/config.py` and
`tests/test_config.py`. Gates re-run independently.

## Premise

Sound. The ticket adds a config surface (`review_passes` + `require_review`)
without touching the commit gate — consumption is deferred to
`loop-commit-gate-n-verdicts` (non-goal §5). The diff honors that boundary:
`lifecycle.py`, `hooks.py`, `ctl.py` are untouched.

## Gate results (re-run by me)

1. `git add --intent-to-add -A . && uv run pytest` — GREEN, 133 passed in 22.31s.
2. `uvx prek run --all-files` — GREEN (ruff-lint Passed, ruff-format Passed,
   mypy Passed).

## Requirements audit

- Backward compat (focus 1): CONFIRMED sound. Absent `review_passes` key →
  `_parse_review_passes` returns `_DEFAULT_REVIEW_PASSES`
  (config.py:186-187); no config file → `LoopConfig()` carries the same
  default (config.py:120,138-139). Both yield the enabled adversarial pass.
  Pinned by `test_absent_review_passes_synthesizes_adversarial` and
  `test_missing_config_keeps_review_on`.
- Un-guessable opt-out (focus 2): CONFIRMED sound. `require_review` defaults
  true (config.py:121). Guard at config.py:153-157 raises `ConfigError` when
  no pass is enabled and `require_review` is true; the message names the
  `"require_review": false` escape hatch. `require_review:false` skips the
  guard, permitting zero enabled passes. Covered by
  `test_empty_review_passes_needs_explicit_opt_out`,
  `test_all_disabled_review_passes_needs_explicit_opt_out`,
  `test_review_disabled_with_explicit_opt_out`.
- Deviation on architectural baseline (focus 3): JUDGED SOUND, non-blocking.
  §6 (the binding Requirements section) states only the GENERIC rule — "a
  pass carrying `baseline` requires it non-empty when `enabled`" — not that
  the `architectural` id specifically demands a baseline. The implementation
  enforces exactly the generic rule (config.py:210-214) and defers
  architectural-needs-baseline to the future loop-architect agent that
  consumes `baseline`. Coupling the generic loader to a literal pass id would
  contradict the module's stated "harness is generic" principle
  (config.py:3). The generic rule is covered by
  `test_review_pass_empty_baseline_raises`. §8's "architectural-style pass
  enabled without baseline" reads as an illustration of the generic rule, not
  a demand to hardcode the id. The requirement is satisfied, not dropped.
- Strictness/validation (focus 4): CONFIRMED adequate. id kebab-case +
  uniqueness (config.py:197-203), non-empty agent (204-206), strict bool for
  `enabled` (207-209) — note `enabled: 1` is correctly rejected because
  `isinstance(1, bool)` is False, so JSON integers do not slip through as
  truthy. Non-dict entry rejected (194-195); non-list `review_passes`
  rejected (189-190); non-bool `require_review` rejected (151-152). No
  malformed input observed to slip through into a valid pass.
- Scope discipline (focus 5): CLEAN. `git status` shows only
  `src/loop_harness/config.py` and `tests/test_config.py` changed outside
  `.loop/` (ledger + leftover `reflection.md` correctly ignored per briefing).
  Every changed line traces to the ticket.
- Docstrings (focus 6): CONFIRMED. `ReviewPass` (numpy Attributes),
  `verdict_filename`, `enabled_review_passes`, `_parse_review_passes`, and the
  `_write` test helper all carry accurate numpy-style docstrings. The
  `verdict_filename` docstring honestly states the legacy `<slug>.md` fallback
  is recognized by the reader, "not produced here" — matching the resolution
  in Open Question §11 (verdict_filename returns the namespaced form; legacy
  acceptance deferred to the gate ticket).

## New-tests-fail-against-old-code check

All new tests import `ReviewPass`, which does not exist at HEAD, so the suite
would fail to import against the old module. Each new assertion also exercises
behavior (synthesis, guard, filtering, strict validation) absent from the old
code. The tests genuinely pin the new behavior.

## Non-blocking observations (no fix required)

- LOW: the baseline non-empty rule is enforced whenever `baseline` is present,
  regardless of `enabled` (config.py:210-214) — slightly stricter than §6's
  "when enabled". Harmless (stricter, and empty baseline is an authoring
  mistake either way); no test pins the disabled+empty-baseline case.
- LOW: `_ID_RE = ^[a-z0-9-]+$` (config.py:21) permits leading/trailing or
  consecutive dashes and a bare `-`. Still filesystem-safe, so acceptable.
- LOW: unknown keys inside a pass entry are silently ignored. The ticket does
  not require rejecting them, and this matches the existing lenient handling
  of unknown top-level keys in `gates` parsing.

## Verdict

PASS. Both gates green, all §6/§8 requirements met, backward compat and the
un-guessable opt-out are correctly implemented and tested, scope is clean, and
the one deliberate deviation is sound and consistent with the ticket's own §6
generic rule and the repo's "harness is generic" principle.
