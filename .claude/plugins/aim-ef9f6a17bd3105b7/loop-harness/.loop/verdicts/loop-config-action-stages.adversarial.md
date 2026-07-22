verdict: pass
tree: b9c07be3a0e34cd934fed005640fdc042ea15c56

# Adversarial review — loop-config-action-stages

Reviewed the uncommitted working-tree diff vs HEAD for
`src/loop_harness/config.py` and `tests/test_config.py` against the ticket at
`~/.claude/plans/loop-config-action-stages.md`. Both gates re-run independently
and green.

## Gate results (re-run, not trusted from hand-off)

- `git add --intent-to-add -A . && uv run pytest` → **155 passed** in ~29s.
- `uvx prek run --all-files` → **ruff-lint Passed, ruff-format Passed, mypy
  Passed**.

## Premise & scope

Premise is sound: additive, strictly-validated config surface with no runtime
consumer yet, mirroring the existing `_parse_review_passes` shape. Scope is
clean — `git status` shows only `src/loop_harness/config.py` and
`tests/test_config.py` modified outside `.loop/` (269 insertions, 1 deletion).
No dispatch logic, no SKILL.md, no new agents, no `mutates_tree` field. §5
non-goals respected.

## Findings

### 1. Anchor set derives from the enum, no circular import — CONFIRMED (good)
`_ANCHOR_VALUES = frozenset(s.value for s in Stage if s is not Stage.BLOCKED)`
(`config.py:26`) derives from `loop_harness.ledger.Stage` (`config.py:18`), not
a hardcoded copy. Excluding `BLOCKED` yields exactly the ticket §4 spine set
(`ready, implementing, gates, self-review, adversarial-review, commit, done`).
`ledger.py` imports only stdlib (`json, os, tempfile, dataclasses, enum,
pathlib, typing`) — it does not import `config`, so the new
`config → ledger` edge introduces no cycle. Verified by grep and by the green
import-time test run.

### 2. `kind` vs `type` deviation — SOUND (good judgment)
The dataclass field is `kind` (`config.py:140`) while the user-facing JSON key
remains `type` (`entry.get("type")`, `config.py:320`). This avoids shadowing the
`type` builtin / ruff A003 without a `# noqa`, honoring the no-silencing-a-lint
rule. The mapping is documented in the `ActionStage` docstring (`config.py:127-129`)
and the round-trip test constructs `ActionStage(kind="agent", ...)` from JSON
`type` (`test_config.py:280-286`). Correct call.

### 3. Backward compat — CONFIRMED
Absent `action_stages` key returns `()` (`config.py:299-300`), covered by
`test_absent_action_stages_is_empty` (`test_config.py:295-298`).

### 4. Validation paths — 7 of 9 covered by test (2 defensive branches uncovered) — LOW
Confirmed each of the following both exists in code and raises, and each test
would fail against pre-change code (ActionStage / action_stages did not exist):
- non-list → `test_action_stage_not_a_list_raises` (`config.py:302-303`)
- bad `type` → `test_action_stage_bad_type_raises` (`config.py:320-324`)
- empty `ref` → `test_action_stage_empty_ref_raises` (`config.py:325-327`)
- bad `after` → `test_action_stage_bad_anchor_raises` (`config.py:328-333`)
- duplicate id within list → `test_action_stage_duplicate_id_raises`
  (`config.py:314-318`), asserts `match="duplicate"`
- id colliding with a review-pass id → `test_action_stage_id_colliding_with_review_pass_raises`;
  global uniqueness seeded via `seen = set(taken_ids)` (`config.py:305`) with
  `taken_ids = {p.id for p in review_passes}` (`config.py:220`). Resolves the
  §11 open question as "validate in the ticket landing second." Correct.
- non-bool `enabled` → `test_action_stage_non_bool_enabled_raises`
  (`config.py:334-338`)

Two rejection branches are correct in code but have no dedicated test:
- **non-object entry** (`config.py:307-308`): no test feeds a list whose element
  is not a dict (e.g. `"action_stages": ["x"]`).
- **non-kebab / non-string `id`** (`config.py:310-313`): `bad_type`/`empty_ref`
  tests all use a valid `id="x"`; nothing exercises an id like `"Bad Id"` or a
  missing id.

The ticket §8 required-test list (`bad type, empty ref, after not a spine value,
duplicate id`) is fully satisfied, so this does not block. Recommended (not
required): add two cases mirroring the `_parse_review_passes` coverage to pin
these branches.

### 5. EXAMPLE_CONFIG `report-out` — informational
Ticket §6 asked for "a commented example custom report-out." JSON has no
comment syntax, so it ships as a real disabled entry with placeholder ref
`your-report-skill` (`config.py:54-60`). Reasonable interpretation; it
re-parses cleanly and `test_example_config_carries_action_stages` asserts
`enabled_action_stages() == ()` (both examples ship opt-in/disabled).

### 6. Test quality — good
Round-trip test asserts full frozen-dataclass equality on the parsed tuple
(non-vacuous) and that `enabled_action_stages()` filters
(`test_config.py:275-291`). Docstrings present on the new dataclass, method,
parser, and every test per `.claude/rules/python-docstrings.md`.

## Verdict

**pass.** Correctness, validation, anchor-from-enum, backward compat, and
non-goals all hold; both gates are green; the diff traces entirely to the
ticket. The only finding is a low-severity test-coverage gap on two defensive
branches (non-object entry, non-kebab id) that the contract §8 did not require
— worth adding but not blocking.
