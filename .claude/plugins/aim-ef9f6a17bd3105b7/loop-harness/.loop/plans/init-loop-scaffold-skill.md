# init-loop-scaffold-skill: a guided `init-loop` skill that bootstraps the harness into a consumer repo

## 1. Title

Add a `init-loop` skill (a `SKILL.md`) that walks an operator through
bootstrapping the loop harness into a fresh consumer repo: refuse if
already configured, run `loopctl init`, propose real gate commands from
the repo's manifests, add the prescribed `.gitignore` entries, verify
with a dry `loopctl stamp`, and stop at "ready to commit" without
committing.

## 2. Size / Effort

**S–M.** One new markdown skill file plus four doc edits and one
manifest-test addition. The effort is prose precision and honest
citation of the harness behavior the skill orchestrates, not code. It
is not S because the skill must accurately mirror three existing
mechanisms (`write_example_config`'s refusal, the example config's
defaults, the README's gitignore contract) and four docs must be
repointed in step so the setup story is told once.

## 3. Triggered by

Operator request: consumers currently bootstrap the harness by running
`loopctl init` (or the raw `python3 <plugin-root>/scripts/loopctl.py
init`) by hand, then editing placeholder gates, then hand-remembering
the gitignore rules from the README. There is no guided path. A
`init-loop` skill turns that scattered, error-prone checklist into one
operator-collaborative flow, matching how `create-ticket` /
`create-eval` / `implement-ticket` already package the other lifecycle
steps as skills.

## 4. Context (today's state)

- Skills are auto-discovered from a glob, not individually listed:
  `.claude-plugin/plugin.json` declares `"skills": "./skills/"`. A new
  skill needs only a `skills/<name>/SKILL.md`; no manifest entry.
- Existing skills and their front-matter shape (`name`, `description`
  only): `skills/create-ticket/SKILL.md:1`,
  `skills/create-eval/SKILL.md:1`, `skills/implement-ticket/SKILL.md:1`.
  A skill may carry optional `assets/` and `references/` subdirs
  (`skills/create-eval/` has both); a body-only skill is fine
  (`skills/implement-ticket/` is just `SKILL.md`).
- The scaffold the skill drives: `cmd_init` in
  `src/loop_harness/cli.py:112` calls `write_example_config`, which
  refuses to overwrite an existing config —
  `src/loop_harness/config.py:391` raises
  `ConfigError(f"{path} already exists; edit it instead")`. The skill
  must mirror this refusal as its own first step, not depend on it
  silently.
- The starter config the skill writes and then edits:
  `EXAMPLE_CONFIG` at `src/loop_harness/config.py:28` ships placeholder
  gates (`uv run pytest`, `uvx prek run --all-files`), `require_eval:
  False`, and the `adversarial` review pass enabled with
  `architectural`/`documentation` disabled
  (`src/loop_harness/config.py:38`). The skill proposes real gates in
  place of the placeholders and leaves the `adversarial` default on.
- The gitignore / commit contract the skill must apply is stated in the
  README: `README.md:80` — commit `.loop/config.json` and
  `.loop/ledger.json`; gitignore `.loop/stamp.json`, `.loop/HALT`,
  `.loop/handoff.log`.
- Docs that currently lead with the manual `loopctl init` path and must
  be repointed at the skill:
  - `README.md:57` "Configure the consumer repo" opens with `python3
    <plugin-root>/scripts/loopctl.py init` (`README.md:60`).
  - `docs/onboarding.md:256` section 6 "Configuration" says "Scaffold a
    starter with `loopctl init`, then edit it" (`docs/onboarding.md:259`).
  - `docs/tutorials/custom-reviews-and-actions.md:15` "Before you
    start" tells readers to run the raw script
    (`docs/tutorials/custom-reviews-and-actions.md:22`).
- The manifest integrity suite that guards skill wiring:
  `tests/test_manifest.py:test_skills_dir_is_declared_and_each_has_a_skill_md`
  already asserts every skill subdir carries a `SKILL.md`, and
  `test_create_eval_skill_is_present` is the per-skill presence
  convention to mirror.

## 5. Non-goals / out of scope

- No change to `loopctl`, `write_example_config`, `cmd_init`,
  `EXAMPLE_CONFIG`, or any `src/loop_harness/` code. The skill
  orchestrates existing behavior; it does not alter it.
- The skill does NOT commit. It stops at "ready to commit
  `.loop/config.json` + `.loop/ledger.json`" and leaves the commit to
  the operator.
- No new `loopctl` subcommand and no automation of gate detection in
  Python. Gate proposal is the skill's own inspection-and-confirm prose,
  performed by the model at runtime.
- No auto-enabling of the `architectural` or `documentation` review
  passes, and no `require_eval` flip. The skill writes the example
  defaults (adversarial-only) unless the operator asks otherwise.
- Not a rewrite of the onboarding/tutorial docs beyond repointing the
  specific scaffold instructions named in §7.

## 6. Requirements & restrictions

The skill (`skills/init-loop/SKILL.md`) must, in prose the model
follows:

1. **Refuse cleanly when already configured.** If `.loop/config.json`
   exists, stop and tell the operator to edit it instead — mirroring
   `src/loop_harness/config.py:391`. Do not overwrite.
2. **Run `loopctl init`** to scaffold `.loop/config.json` from
   `EXAMPLE_CONFIG` (`src/loop_harness/cli.py:112`). Use the
   SessionStart-printed `ctl` path, per `skills/implement-ticket/SKILL.md`.
3. **Propose real gates from the repo's manifests.** Inspect
   `pyproject.toml`, `justfile`, `Makefile`, `package.json` and propose
   concrete gate commands (for example `uv run pytest`, `uvx prek run
   --all-files`, `cargo test`, `npm test`) replacing the placeholder
   defaults at `src/loop_harness/config.py:29`. Enumerate those three
   ecosystems as worked examples, then fall back to a generic "inspect
   the repo's task runner and propose its blessed invocation" rule so
   the skill degrades gracefully on repos without a named example,
   rather than maintaining an exhaustive matrix. Confirm with the
   operator before writing — the operator owns the substance, matching
   the collaboration discipline in `skills/create-eval/SKILL.md`.
4. **Keep the default `adversarial` review pass enabled** (the
   harness's mandatory default, `src/loop_harness/config.py:39`).
5. **Add the prescribed `.gitignore` entries** `.loop/stamp.json`,
   `.loop/HALT`, `.loop/handoff.log`, and state that
   `.loop/config.json` and `.loop/ledger.json` are committed, not
   ignored — per `README.md:80`.
6. **Verify with a dry `loopctl stamp`** so the config parses and goes
   green before handoff.
7. **Stop at "ready to commit"** — do not commit.

Authoring method:

- **Author the new skill with the `skill-creator` skill.** The
  implementer creates `skills/init-loop/SKILL.md` by invoking the
  `skill-creator` skill (Create new skills / modify existing ones), not
  by hand-writing the file from scratch, so the skill's structure,
  front matter, and description follow the same conventions
  `skill-creator` enforces. The seven-step flow (§6) and the citations
  are the content it must produce; the front-matter shape must still
  match the existing skills (see below).

Repo principles the change must respect:

- **Slop scan for docs** governs the new `SKILL.md` and every doc edit:
  run Layers 0–2 before declaring done (`.claude/rules/slop-scan-for-docs.md`).
- **Prek code quality / gates** are leading and must pass through the
  task runner (`.claude/rules/prek-code-quality.md`); prefer `just`
  recipes (`justfile`).
- **Simplicity & surgical changes** (`CLAUDE.md` §2–3): body-only skill
  if that suffices (no speculative `assets/`/`references/`); doc edits
  touch only the named scaffold lines.
- **Front matter must match the existing shape** (`name`, `description`
  only) as in `skills/create-ticket/SKILL.md:1`.

## 7. Code surface

- `skills/init-loop/SKILL.md` — **NEW.** The skill body: front matter
  (`name: init-loop`, a `description` naming the guided-bootstrap
  trigger, matching the shape at `skills/create-ticket/SKILL.md:1`)
  plus the ordered seven-step flow from §6. Body-only unless a
  reference file is genuinely warranted.
- `README.md:57` (through `README.md:81`) — repoint the "Configure the
  consumer repo" section: lead with the `init-loop` skill as the
  guided path; keep the raw `loopctl init` (`README.md:60`) as the
  manual fallback, and preserve the gitignore/commit contract at
  `README.md:80` (the skill now applies it, so the prose should say so).
- `README.md:105` (the "What ships" list, `README.md:105`–`README.md:113`)
  — add a `init-loop` bullet so the shipped-skills enumeration stays
  consistent with the new artifact.
- `docs/onboarding.md:256` (section 6, scaffold line at
  `docs/onboarding.md:259`) — point "Scaffold a starter" at the
  `init-loop` skill, with `loopctl init` as the underlying command.
- `docs/onboarding.md:680` (the skills enumeration at
  `docs/onboarding.md:680`–`docs/onboarding.md:681`) — add `init-loop`
  to the parenthetical list of skills the model runs.
- `docs/tutorials/custom-reviews-and-actions.md:15` ("Before you
  start", raw-init block at
  `docs/tutorials/custom-reviews-and-actions.md:22`) — demote the
  manual `python3 <plugin-root>/scripts/loopctl.py init` to a pointer at
  the `init-loop` skill.
- `tests/test_manifest.py` — add a `test_init_loop_skill_is_present`
  asserting `skills/init-loop/SKILL.md` exists, mirroring
  `test_create_eval_skill_is_present`. (Home for the test named in §8.)

## 8. Tests & validation gates

**Reality:** this is a markdown-only skill with no Python logic, so
there is no unit test for the skill's prose. The automated surface a new
skill directory touches is the manifest suite.

**Eval marker (the spec):** `.loop/evals/init-loop-scaffold-skill.md`
holds the scored Definition of Done: six behavior rows (gate proposal,
generic fallback, adversarial pass kept on, gitignore/commit contract,
dry-stamp verification, stop-at-ready) plus two deterministic guardrails
(refuses to overwrite an existing config; never commits). Keep this file
and §6 in step by hand.

Repo gates (discovered from `.loop/config.json` and `justfile`), all run
through the task runner per `.claude/rules/prek-code-quality.md`:

- `just check` → `git add --intent-to-add -A .`, then `uv run pytest`,
  then `uvx prek run --all-files` (`justfile`).
- `just stamp` → `uv run loopctl stamp` records the evidence stamp.
- prek hooks (`.pre-commit-config.yaml`): `ruff-lint`, `ruff-format`,
  `mypy` — Python-typed hooks; they do not touch the new markdown, but
  the added test in `tests/test_manifest.py` must pass all three.

Tests to add / must-stay-green:

- `tests/test_manifest.py::test_init_loop_skill_is_present` — **NEW**,
  asserts the new skill's `SKILL.md` resolves (mirrors
  `test_create_eval_skill_is_present`). Home declared in §7.
- `tests/test_manifest.py::test_skills_dir_is_declared_and_each_has_a_skill_md`
  — existing; the new `skills/init-loop/` directory must contain
  `SKILL.md` or this fails. No manifest edit is needed (skills are a
  glob), so verify by running the suite green.

Doc gates (apply to `SKILL.md` and every edited `.md`, per
`.claude/rules/slop-scan-for-docs.md`): Layer 0 (no identity leaks, no
hallucinated paths/commands — every backticked path and command must
resolve), Layer 1 (thesis-first, sentence weight), Layer 2 (80-char
wrap, em-dash and slop scans).

## 9. Risk assessment

- **Blast radius: low.** One new skill file plus doc/test edits. No
  `src/` change, so no runtime behavior of `loopctl` or the harness
  moves.
- **Reversibility: high.** Deleting the skill dir and reverting the doc
  edits fully restores today's state; nothing persists in the ledger or
  stamp from authoring a skill.
- **Likeliest failure modes:**
  1. **Hallucinated command/path in the SKILL prose** (for example a
     `loopctl` subcommand that does not exist, or a wrong config key).
     Mitigation: cite against `src/loop_harness/cli.py:127`+ subcommand
     registrations and `EXAMPLE_CONFIG`; Layer 0 slop scan.
  2. **Docs drift** — repointing one doc but not the others leaves two
     competing setup stories. Mitigation: §7 names all four doc anchors;
     edit them together.
  3. **The manifest test fails** because the new dir lacks a `SKILL.md`
     during a partial commit. Mitigation: the `SKILL.md` is the first
     artifact written.
  4. **Over-scoping the skill** into committing or auto-detecting gates
     in Python, violating §5. Mitigation: the "stop at ready to commit"
     and "propose, do not decide" boundaries are explicit.

## 10. Subtickets

1. **Author `skills/init-loop/SKILL.md` via the `skill-creator` skill**
   (per §6 "Authoring method"), with front matter and the ordered
   seven-step flow (§6), citing the harness behaviors it orchestrates. →
   verify: front matter matches the existing shape; all backticked
   paths/commands resolve.
2. **Add `test_init_loop_skill_is_present`** to
   `tests/test_manifest.py`. → verify: `uv run pytest
   tests/test_manifest.py -q` green.
3. **Repoint the README** — "Configure the consumer repo"
   (`README.md:57`) and the "What ships" list (`README.md:105`). →
   verify: the skill is the lead path; gitignore contract preserved.
4. **Repoint the docs** — `docs/onboarding.md:256` scaffold line and
   `docs/onboarding.md:680` skills list, and
   `docs/tutorials/custom-reviews-and-actions.md:15` prereq block. →
   verify: each names the `init-loop` skill.
5. **Run the gates** — `just check` and `just stamp`; run the slop scan
   on every edited `.md`. → verify: suite green, stamp green, slop
   layers pass.

Ordering: 1 before 2 (test needs the file); 1 before 3–4 (docs point at
the skill's name); 5 last.

## 11. Open questions

All three forks are RESOLVED by the operator; recorded here as settled so
the implementer treats them as decided, not open.

1. **The skill's name — RESOLVED: `init-loop`.** Verb-noun, consistent
   with `create-ticket` / `create-eval` / `implement-ticket`. The name is
   baked into the skill dir, the front matter, the manifest test, and the
   four doc anchors in §7; use `init-loop` everywhere.
2. **Gate auto-detection breadth — RESOLVED: three examples + generic
   fallback.** The prose enumerates Python (`uv run pytest`, `uvx prek`),
   Rust (`cargo test`), and JS (`npm test`) as worked examples, then falls
   back to a generic "inspect the repo's task runner and propose its
   blessed invocation" rule (folded into §6 requirement 3). No broader
   explicit ecosystem list.
3. **Consistency edits — RESOLVED: include them.** The README "What
   ships" bullet (`README.md:105`) and the onboarding skills-list entry
   (`docs/onboarding.md:680`) are in scope (already listed in §7), so the
   shipped-skills enumerations stay consistent with the new artifact.
