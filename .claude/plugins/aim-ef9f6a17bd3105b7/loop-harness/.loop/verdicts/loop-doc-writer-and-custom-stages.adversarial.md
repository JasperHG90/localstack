verdict: pass
tree: 9dd36497c31e6d93bd7ed7ecd5dc9010076fba75

# Adversarial review: loop-doc-writer-and-custom-stages

Reviewed the uncommitted working-tree diff vs HEAD (excluding `.loop/`)
against the ticket contract at
`~/.claude/plans/loop-doc-writer-and-custom-stages.md`. Premise is sound:
the change ships an advisory doc-writer action agent, wires action-stage
dispatch into the implement-ticket skill as prose, and documents the
selectable-review + action-stage surface. No code (`config.py`,
`hooks.py`, `lifecycle.py`) is touched, matching non-goals §5. Doc
accuracy — the flagged main risk — holds up under cross-checking.

## Gate results (re-run independently)

- `git add --intent-to-add -A . && uv run pytest` -> GREEN, 157 passed.
- `uvx prek run --all-files` -> GREEN (ruff-lint, ruff-format, mypy all Passed).

## Doc-accuracy cross-check (no hallucinations found)

- README `review_passes` example: ids `adversarial`/`architectural`/
  `documentation`, agents `loop-reviewer`/`loop-architect`/
  `loop-doc-reviewer`, `baseline: "MANIFESTO.md"` all match
  `config.py` `EXAMPLE_CONFIG` (config.py:36-45) and the on-disk agent
  frontmatter (`agents/loop-*.md` name lines) and manifest
  (`plugin.json:12-18`). The `require_review:false` opt-out and its
  loud-error semantics match the `require_review` guard
  (config.py:207-212) and the session-start warning (hooks.py:256-263).
  Architectural = "reviews the diff against a baseline doc" and
  documentation = "fails when documented behavior drifts" match those
  agents' descriptions.
- README `action_stages` example uses JSON key `type` (agent/skill),
  `ref`, `after` — matches `_parse_action_stages` (config.py:296-338).
  Correctly surfaces the user-facing `type` even though the dataclass
  field is `kind` (config.py:126-131). "Stage ids are unique across both
  lists" matches the cross-list uniqueness check (config.py:319-323).
- DECISIONS S2 (fail-safe to adversarial, never zero) matches
  `enabled_passes_failsafe` (hooks.py:189-201). S3 (advisory-by-honesty,
  no ledger marker, tree-mutating runs at `after: implementing`) matches
  the non-goals and the ActionStage docstring (config.py:107-116). S4
  (`type` is `agent`/`skill`, not `hook`; hooks stay `hooks/hooks.json`)
  matches the type validation (config.py:329-333) and the real
  `hooks/hooks.json` on disk.
- Anchors `implementing` and `done` used in SKILL/README are valid
  `_ANCHOR_VALUES` (all Stage values but BLOCKED; ledger.py:25-32).

## Contract checks

- `agents/loop-doc-writer.md`: frontmatter `name: loop-doc-writer`,
  `tools: Read, Grep, Glob, Edit, Write` per §6; body scopes edits to
  docs only, writes NO verdict, instructs running before the stamp, and
  states the enforced check is the documentation review pass — consistent
  with the SKILL "tree-mutating action runs at after:implementing" rule
  (SKILL.md:44-48, 101-107) and DECISIONS S3.
- Manifest integrity: `loop-doc-writer` declared in `plugin.json:18`,
  file present on disk, plugin.json valid JSON, bidirectional invariant
  held (test_manifest.py new test passes within the green suite).
- SKILL coherence: the new "Action stages" section and step 2 dispatch do
  not contradict the config schema or the already-shipped review step 5
  (SKILL.md:57-71). The "enable the documentation review pass to guarantee
  freshness; the doc-writer only writes them" guidance correctly maps the
  advisory writer vs. the enforced documentation review pass.

## Test quality / scope

- `test_ctl.py::test_action_stage_doc_edits_ride_the_stamped_tree` is
  non-vacuous: the pre-stamp `DOCS.md` write rides the stamped/verdict
  tree so `advance ... commit` is authorized, and a post-stamp edit drives
  `verify_stamp(...).status is StampStatus.STALE`. Both assertions are
  real; this pins the sole mechanically-testable property of action
  stages, exactly as §8 scopes it (the "did the agent run" half is
  correctly not asserted). It exercises existing tree-binding rather than a
  new source path, which is expected: this ticket's substance is
  prose/config-driven, so no new code branch exists to distinguish.
- Scope: exactly the 7 declared files change; every added line traces to
  §6/§7. `test_manifest.py` addition matches §7. Placing the integration
  test in `test_ctl.py` (not the §7-listed `test_manifest.py`) follows the
  mirror-the-source convention for a lifecycle/tree-binding property and is
  acceptable, consistent with the prior-ticket precedent noted in the brief.

## Slop

New prose in the agent, SKILL, README, and DECISIONS: 0 new em-dashes, no
` -- ` prose dashes, no tier-1 slop, no British spellings ("honoring",
"honor", "behavior" are American). No new unevidenced quality claims in the
README. Semicolons in the new prose match the repo's established voice
(low-confidence, surfaced not required).

## Findings

None confirmed at severity. Nit (non-blocking): the SKILL clause "enable
the documentation review pass, whose verdict gates the commit; the
doc-writer action only writes them" uses a semicolon splice consistent with
existing house style; leave as-is.

Recommendation: pass.
