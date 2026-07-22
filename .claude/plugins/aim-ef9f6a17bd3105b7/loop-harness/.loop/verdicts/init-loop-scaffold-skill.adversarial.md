verdict: pass
tree: 9ece3bdb9a2d388c62347a66b58137f779bf9506

# Adversarial review: init-loop-scaffold-skill

Ticket: `.loop/plans/init-loop-scaffold-skill.md`
Eval: `.loop/evals/init-loop-scaffold-skill.md`
Diff scope reviewed against HEAD: `skills/init-loop/SKILL.md` (new),
`tests/test_manifest.py`, `README.md`, `docs/onboarding.md`,
`docs/tutorials/custom-reviews-and-actions.md`. `.loop/ledger.json`
ignored (loopctl-managed lifecycle state).

## Premise

Sound. The ticket packages a scattered manual bootstrap (run `loopctl
init`, hand-edit placeholder gates, hand-recall gitignore rules) into
one guided skill, mirroring how `create-ticket` / `create-eval` /
`implement-ticket` already package their lifecycle steps. Markdown +
one test, no `src/` change. The §5 non-goals (no code change, no
commit, no Python auto-detection) are the right boundaries and the
diff honors all of them.

## Frozen decisions / repo constraints

- Front matter matches the existing shape (`name`, `description` only),
  as required by §6 authoring method and `skills/create-ticket/SKILL.md:1`.
  Verified: `skills/init-loop/SKILL.md:1-4`.
- Skills are glob-discovered (`.claude-plugin/plugin.json`
  `"skills": "./skills/"`); no manifest entry needed. Correct — none added.
- Slop scan (`.claude/rules/slop-scan-for-docs.md`): clean. 0 em-dashes,
  0 tier-1 slop terms, 0 British spellings, 0 ` -- ` prose, 0 smart
  quotes (unicode grep `none`). All prose lines wrap at 80; the only
  over-length line is the single-line YAML `description` (526 chars),
  which is exempt (baseline `create-ticket` description is 286 on the
  same line).

## Correctness of the diff (every backticked claim resolves)

Audited each harness behavior the skill cites against the real source:

- Refusal message: SKILL.md:28 quotes `already exists; edit it instead`
  — exact match to `src/loop_harness/config.py:391`
  (`ConfigError(f"{path} already exists; edit it instead")`). ✓
- `loopctl init` subcommand exists (`cli.py:192`, `cmd_init` at
  `cli.py:177`). ✓
- `loopctl stamp` subcommand exists (`cli.py:195`, `cmd_stamp` at
  `cli.py:48`, runs gates + writes evidence stamp). ✓
- `adversarial` pass enabled, `architectural`/`documentation` disabled:
  matches `EXAMPLE_CONFIG` `review_passes` at `config.py:36-45`
  (adversarial `enabled: True`, other two `enabled: False`). SKILL.md:65-70
  states exactly this. ✓
- Gitignore/commit contract (SKILL.md:72-83): ignore `.loop/stamp.json`,
  `.loop/HALT`, `.loop/handoff.log`; commit `.loop/config.json` and
  `.loop/ledger.json` — verbatim match to `README.md:80` contract. ✓
- SessionStart `ctl` path format: SKILL.md:37 says the hook prints
  `[loop] ctl: ...`; matches `src/loop_harness/hooks.py:490`
  (`f'[loop] ctl: python3 "{ctl_path}"'`). ✓
- `write_example_config`, `EXAMPLE_CONFIG`, `ConfigError`,
  `AskUserQuestion`, `justfile`/`Makefile`/`Cargo.toml`/`package.json`/
  `pyproject.toml` — all resolve to real symbols/manifests. No
  hallucinated `loopctl` subcommand or config key found (the top risk
  per §9). ✓

## Test quality

`tests/test_manifest.py:57-61` adds `test_init_loop_skill_is_present`,
asserting `skills/init-loop/SKILL.md` is a file — a faithful mirror of
`test_create_eval_skill_is_present` (`test_manifest.py:53-54`). It would
fail against the old tree (the file did not exist), so it is a real
regression guard, not a tautology. The existing
`test_skills_dir_is_declared_and_each_has_a_skill_md` also now covers the
new directory. Both green.

## Gates (re-run independently)

- `uv run pytest` (full suite): **all pass** (265 tests).
- `uvx prek run --all-files`: ruff-lint Passed, ruff-format Passed,
  mypy Passed.

## Scope

Every changed line traces to a §7 anchor: README Configure section +
"What ships" bullet, onboarding §6 scaffold line + skills enumeration,
tutorial "Before you start" prereq, and the manifest test. No `src/`
change. Docs are repointed consistently — each names the `init-loop`
skill as the guided path and keeps the raw `loopctl init` / `python3
<plugin-root>/scripts/loopctl.py init` as the labeled manual fallback,
so no competing setup story is left behind. The `.loop/ledger.json`
delta is loopctl lifecycle bookkeeping (stage `ready` → `adversarial-review`),
out of scope as briefed.

## Eval coverage

The skill's prose covers all six behavior rows and both guardrails of
`.loop/evals/init-loop-scaffold-skill.md`: repo-appropriate gate proposal
with operator confirmation (step 3 + `AskUserQuestion`), generic
"inspect the task runner" fallback with a no-fabrication rule (step 3,
`make verify` example), adversarial kept enabled (step 4), the three
gitignore entries + committed-config/ledger contract (step 5),
dry-stamp verification with red-stamp handling (step 6), stop-at-ready
handoff (step 7), overwrite refusal (step 1), and never-commit (step 7 +
Discipline).

## Findings

- **INFO (no fix required):** SKILL.md:42 describes the starter gates as
  `uv run pytest` and `uvx prek run --all-files`. The real
  `EXAMPLE_CONFIG` first gate is `git add --intent-to-add -A . && uv run
  pytest` (`config.py:29-32`) — the `git add --intent-to-add` prefix is
  dropped. This abbreviation is faithful to the ticket's own §4
  characterization (which lists the same abbreviated pair), and the
  point of the sentence is only that these are placeholders to replace,
  so it misleads no operator. Not a hallucinated command; both fragments
  are real. Recorded for transparency, not a required fix.

## Verdict

pass. Premise sound; frozen decisions honored; no hallucinated
paths/commands; the new test is a genuine guard that would fail on the
old tree; both gates green; scope clean; all eval rows covered.
