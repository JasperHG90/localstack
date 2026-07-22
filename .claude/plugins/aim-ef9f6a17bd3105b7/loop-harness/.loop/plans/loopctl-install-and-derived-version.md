# loopctl-install-and-derived-version: a documented `uv tool install` path for the `loopctl` CLI, with the package version single-sourced from `plugin.json`

## 1. Title

Give `loopctl` a first-class standalone install path (`uv tool
install`) surfaced in the README and a `just` recipe, and make
`pyproject.toml` derive its version from `.claude-plugin/plugin.json`
so the one number the `release-claude-code-plugin` skill already bumps
is authoritative for both the plugin and the installable package.

## 2. Size / Effort

**S.** Three small edits (`pyproject.toml` version stanza, `justfile`
recipes, `README.md` prose) plus one deterministic wiring test. The
effort is packaging precision (hatchling's regex version source, wired
at the exact `path`/`pattern`) and honest README prose, not new code.

## 3. Triggered by

Operator request: the repo needs (1) a way to install `loopctl` as a
standalone tool, and (2) a way to bump the Claude Code plugin's
version. `loopctl` is already a packaged entry point but has no
documented install path, and the version lives in two files that drift
by hand.

## 4. Context (today's state)

- `loopctl` is **already** a console entry point:
  `pyproject.toml:15` `[project.scripts]` maps `loopctl =
  "loop_harness.cli:main"`. The package builds with hatchling
  (`pyproject.toml:18`). So "install it as a tool" needs no new
  packaging — only a documented invocation and a recipe.
- The plugin/hook path is deliberately **zero-install**:
  `scripts/loopctl.py:1` bootstraps `sys.path` so the SessionStart
  hook (`src/loop_harness/hooks.py:489`) can print the script path with
  no install. `README.md:155` states this ("consumers need no install
  step"). The new install path is an *additional, optional* way to get
  `loopctl` on `PATH` for standalone use; it does not replace the
  zero-install plugin path.
- The version lives in **two** tracked files that must agree:
  `pyproject.toml:3` (`version = "0.1.0"`) and
  `.claude-plugin/plugin.json:4` (`"version": "0.1.0"`). Nothing in
  `src/loop_harness/` reads the package version at runtime (no
  `__version__`, no `importlib.metadata` call), so the pyproject
  version matters only at build/install time.
- `.claude-plugin/marketplace.json` carries **no** `version` field, so
  it is out of the sync problem.
- The bump mechanism already exists as an aim-vendored skill:
  `release-claude-code-plugin` (`aim.toml:155`, installed to the
  gitignored `.claude/skills/release-claude-code-plugin/SKILL.md`).
  Per that skill, `plugin.json` is the source of truth; it bumps
  `plugin.json`, syncs a `marketplace.json` version only if one exists,
  then commits and pushes in one shot. It does **not** touch
  `pyproject.toml`, and being vendored under gitignored `.claude/`, it
  is not ours to edit.
- `justfile` today holds `check` and `stamp` recipes only; it declares
  itself the repo's own dev recipes ("Consumers use loopctl directly").
- The manifest-integrity suite `tests/test_manifest.py:15` already
  loads `plugin.json` and asserts wiring the schema check misses; it is
  the established home for a version-derivation guard.

## 5. Non-goals / out of scope

- No new bump script or `loopctl` subcommand. Version bumping stays the
  `release-claude-code-plugin` skill's job; this ticket only makes its
  single `plugin.json` edit authoritative for `pyproject.toml` too.
- No git tag / CI release flow (that is the separate `release` skill).
- No change to `scripts/loopctl.py`, the SessionStart hook, or the
  zero-install plugin path. It stays exactly as-is.
- No `version` field added to `marketplace.json`.
- No change to `src/loop_harness/` runtime code.

## 6. Requirements & restrictions

- **R1 — single source of truth.** `pyproject.toml` must derive its
  version from `.claude-plugin/plugin.json` via hatchling's dynamic
  version, so the skill's one edit to `plugin.json` flows to the
  installable package with no second commit. (`pyproject.toml:3` static
  version removed; hatchling backend already present at
  `pyproject.toml:18`.)
- **R2 — documented standalone install.** The README must show how to
  install `loopctl` as a tool, both from a clone/local checkout and
  from the git remote
  (`github.com/JasperHG90/loop-engineering-harness`), using `uv tool
  install` per the repo's uv-first convention
  (`.claude/rules/uv-installer.md`; `justfile` already uses `uv`).
- **R3 — a recipe.** `just install` (and an editable variant) must run
  the blessed `uv tool install` invocation, matching how `justfile`
  already encodes the blessed `check`/`stamp` calls.
- **R4 — the zero-install path stays honest.** The `README.md:155`
  claim that consumers need no install step must remain true: the new
  text frames `uv tool install` as optional and additive, scoped to
  standalone CLI use, not the plugin path.
- **R5 — surgical + gates green.** Every changed line traces to this
  ticket; `uv run pytest` and `uvx prek run --all-files` stay green
  (`.loop/config.json` gates).

## 7. Code surface

- `pyproject.toml:1-3` — remove `version = "0.1.0"` from `[project]`;
  add `dynamic = ["version"]`. Add a `[tool.hatch.version]` table with
  `path = ".claude-plugin/plugin.json"` and `pattern =
  '"version":\s*"(?P<version>[^"]+)"'` (hatchling's default regex
  source, named group `version`). No other stanza changes.
- `justfile` — add `install` (`uv tool install --force .`) and
  `install-editable` (`uv tool install --force --editable .`) recipes,
  in the existing recipe style with a one-line doc comment each.
- `README.md:43-55` (Install) — add a short subsection documenting
  `uv tool install` for the standalone `loopctl` CLI: local
  (`uv tool install .` / `just install`) and from git
  (`uv tool install git+https://github.com/JasperHG90/loop-engineering-harness.git`),
  framed as optional/additive per R4.
- `README.md:147-156` (Development) — add a one-paragraph "Releasing"
  note: bump the plugin version with the `release-claude-code-plugin`
  skill (edits `plugin.json`); `pyproject.toml` derives from it
  automatically, so there is one number to change.
- `tests/test_manifest.py` — add `test_pyproject_version_derives_from_plugin_json`:
  read `[tool.hatch.version]` `path` + `pattern` from `pyproject.toml`
  (via `tomllib`), apply the regex to the pointed-at file, and assert
  the captured `version` equals `MANIFEST["version"]`; also assert
  `[project]` declares `dynamic` containing `"version"` and carries no
  static `version` key. This reproduces hatchling's own resolution, so
  it fails if the wiring drifts or the two numbers diverge.

## 8. Tests & validation gates

- **Repo gates (from `.loop/config.json`):**
  `git add --intent-to-add -A . && uv run pytest`, then
  `uvx prek run --all-files`. Both must pass; `loopctl stamp` records
  the evidence.
- **New test:** `test_pyproject_version_derives_from_plugin_json` in
  `tests/test_manifest.py` (§7) — deterministic, no build required.
- **Manual build check (verification, not a gate):**
  `uv build` produces `loop_harness-0.1.0-*.whl` (version pulled from
  `plugin.json`); temporarily bumping `plugin.json` to `0.1.1` and
  rebuilding yields `loop_harness-0.1.1`, then revert. Confirms the
  derivation end to end.
- **Review gates:** `loop-reviewer` (adversarial) and `loop-architect`
  (architectural, baseline `MANIFESTO.md`) per `.loop/config.json`
  `review_passes`. README edits also carry the doc slop-scan
  (`.claude/rules/slop-scan-for-docs.md`).

## 9. Risk assessment

- **Blast radius:** tiny. Build-time metadata + docs + one test. No
  runtime code path changes; nothing in `src/` reads the version.
- **Reversibility:** trivial — revert three files and the test.
- **Likeliest failure modes:** (a) the hatchling regex `pattern`
  mis-captures (wrong group name or greedy match) → the manifest test
  catches it deterministically; (b) `uv tool install git+…` failing
  because `plugin.json` is untracked → not a risk, it is tracked
  (`git ls-files .claude-plugin/plugin.json`); (c) the README overstates
  the install path and contradicts the zero-install claim → R4 guards
  the framing, and the architectural review checks it.

## 10. Subtickets

1. Rewire `pyproject.toml` to the dynamic hatchling version. → verify:
   `uv build` emits `loop_harness-0.1.0-*.whl`.
2. Add the `test_pyproject_version_derives_from_plugin_json` guard. →
   verify: `uv run pytest tests/test_manifest.py` green. Single-sourcing
   makes divergence structurally impossible, so the test instead guards
   the two real post-change risks: the regex still resolves (a broken or
   greedy `pattern` fails it) and no static `version` key reappears
   alongside the dynamic one.
3. Add `install` / `install-editable` recipes to `justfile`. → verify:
   `just install` puts `loopctl` on `PATH` (`loopctl --help`).
4. Document the standalone install and the releasing note in
   `README.md`. → verify: slop-scan clean; the zero-install claim still
   holds.

## 11. Open questions

None. The two forks the request left open were settled with the
operator before this ticket:

- **Install method** → `uv tool install` recipe (leverages the existing
  entry point; matches the repo's uv convention), plus README docs
  including the git-remote form so users can install without a clone.
- **Version sync** → derive `pyproject.toml` from `plugin.json` (single
  source of truth), rather than a drift-guard hook or a parallel bump
  script — so the existing `release-claude-code-plugin` skill remains
  the sole bump mechanism.
