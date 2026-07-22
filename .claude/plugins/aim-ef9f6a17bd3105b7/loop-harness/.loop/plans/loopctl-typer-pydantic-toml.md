# loopctl-typer-pydantic-toml: migrate the harness core off stdlib-only onto typer+rich, pydantic, and TOML config

## 1. Title

Rebuild `loopctl` on typer+rich, migrate `.loop/config.json` to
TOML validated by pydantic, and rework every launcher/hook so the
harness runs under the plugin's synced uv project env (which carries
the new deps) via `uv run --project "${CLAUDE_PLUGIN_ROOT}"` instead
of the system `python3`. Retire the "dependency-free / stdlib-only
core" value from MANIFESTO.md, README.md, and DECISIONS.md honestly.

## 2. Size / Effort

**L.** Three reasons it is large, not medium:

1. **It is a cross-cutting core rewrite, not a feature add.** Two core
   modules are rebuilt end to end (`config.py`, `cli.py`), and their
   public shapes (`LoopConfig`, `ReviewPass`, `ActionStage` dataclasses;
   the argparse dispatch) are imported by five other modules and eight
   test files.
2. **The launcher trap spans THREE shims, not one.** `config.py` is
   imported by `hooks.py`, `ctl.py`, `reconcile.py`, `stamp.py`, and
   `cli.py` (see §4). All three bootstrap shims
   (`scripts/loopctl.py`, `scripts/run_hook.py`, `scripts/run_git_hook.py`)
   transitively import `config.py`, so a pydantic import crashes the
   Claude Code hooks and the git backstop under the system `python3`,
   not just the CLI. Reworking invocation so the deps resolve (re-exec
   through `uv run --project`) touches `hooks/hooks.json`,
   `githook.py`'s managed-hook body, and the SessionStart context print.
3. **A format rename ripples through the doc/skill layer.** The literal
   `.loop/config.json` appears across four skills, two docs, two agents,
   and the fingerprint-binding logic; the honesty edits touch three
   value statements in two documents plus a new DECISIONS entry.

## 3. Triggered by

Operator decision (an architectural pivot, resolved before this ticket):
the harness should adopt real dependencies for a better CLI and typed,
validated config. The "dependency-free / stdlib-only core" value is
being retired deliberately. The WHAT is settled (typer+rich, pydantic,
TOML, run under the plugin's synced uv project env). All four finer
sub-forks (§11 Q1–Q4) are now RESOLVED by the operator and folded into
the sections below; the implementer should not hit an
`unresolved-design-fork` on any of them.

## 4. Context (today's state)

- **CLI is argparse, ~273 lines.** `src/loop_harness/cli.py:188-269`
  builds one `ArgumentParser` with a required subparser and dispatches
  by `args.cmd`. The full subcommand surface (for typer parity) is 19
  commands, declared at `cli.py:192-224`: `init`, `install-git-hook`,
  `uninstall-git-hook`, `stamp`, `verify`, `reconcile`, `ledger`,
  `register <slug>`, `advance <slug> <stage>`, `block <slug> <code>
  <reason>`, `done <slug>`, `drop <slug>`, `finish <slug>`, `reflect
  <slug>`, `eval <slug>`, `distill`, `halt [reason]`, `resume`,
  `status`. Several delegate rather than own logic: `verify` →
  `stamp_mod.main(["verify"])` (`cli.py:237`), `reconcile` →
  `reconcile.main()` (`cli.py:239`), `ledger` →
  `hooks.main(["session-start"])` (`cli.py:241`), `halt`/`resume`/`status`
  → `halt.main(...)` (`cli.py:266-269`). `advance` restricts `stage` to
  a `choices` set (`cli.py:203-205`); `block` restricts `code` to
  `BlockerCode` values (`cli.py:208`). Parity means preserving these
  constraints, delegations, exit codes, and stdout/stderr split.
- **Config is JSON via stdlib, parsed by hand.**
  `src/loop_harness/config.py:20` `CONFIG_FILE = Path(".loop") /
  "config.json"`. `EXAMPLE_CONFIG` is a dict literal
  (`config.py:28-64`). The three config shapes are frozen dataclasses:
  `ReviewPass` (`config.py:71`), `ActionStage` (`config.py:115`),
  `LoopConfig` (`config.py:148`). `load_config` (`config.py:208`) does
  `json.loads` then ~160 lines of manual type-checking across
  `load_config`, `_parse_review_passes` (`config.py:272`), and
  `_parse_action_stages` (`config.py:319`), each raising `ConfigError`
  with a specific message. `write_example_config` (`config.py:379`) does
  `json.dumps(EXAMPLE_CONFIG, indent=2)`. Fields on `LoopConfig`:
  `gates`, `plans_dir`, `notify_title`, `max_review_cycles`,
  `review_passes`, `require_review`, `require_eval`, `action_stages`,
  `fingerprint_ignore` (`config.py:189-197`). The many hand-written
  `ConfigError` messages carry behavior (they explain WHY a shape is
  rejected, e.g. "a bare string would char-split into nonsense gates");
  pydantic validators must preserve equivalent loud, specific errors,
  not collapse to a generic pydantic traceback.
- **Config is read by five modules, written by one.** Importers of
  `loop_harness.config`: `hooks.py:41`, `ctl.py:21`, `reconcile.py:16`,
  `stamp.py:25`, `cli.py:20`. The only writer is
  `write_example_config` (called by `cli.py:177` `cmd_init`). So a TOML
  *reader* (stdlib `tomllib`, 3.11+) covers every read path; only
  `init` writes, and it writes one fixed document, now serialized with
  the `tomli-w` writer dep (§11 Q1, RESOLVED: add `tomli-w`). Per Q2
  (RESOLVED: clean cutover, no legacy detection), `load_config` reads
  ONLY `.loop/config.toml`; there is no dual-format reader and no
  special-cased error for a stale `.loop/config.json`.
- **The fingerprint binds the config file by name.**
  `stamp.py:127-128` re-adds `CONFIG_FILE.as_posix()` into the tree
  hash after stripping `.loop/`, so a config edit stales the stamp
  (DECISIONS.md §F). Renaming the `CONFIG_FILE` constant flows here
  automatically, but the migration must ensure exactly one config file
  exists post-cutover (a stale `config.json` beside a new `config.toml`
  would leave the old one unbound and confusing).
- **Three stdlib shims bootstrap `sys.path` and run under system
  `python3`.**
  - `scripts/loopctl.py:14-17` inserts `src/` and imports
    `loop_harness.cli.main`; its import guard at `:16-24` fails open
    loudly. Printed into the agent context by `hooks.py:489-490` as
    `[loop] ctl: python3 "<...>/scripts/loopctl.py"`.
  - `scripts/run_hook.py` imports `loop_harness.hooks.main`; invoked by
    `hooks/hooks.json` for all four events as
    `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/run_hook.py" <entry>`
    (`hooks.json:9,21,31,42`: session-start, pre-commit-gate,
    state-guard, stop-check).
  - `scripts/run_git_hook.py` imports `loop_harness.githook.pre_commit`;
    invoked by the managed `.git/hooks/pre-commit` whose body is written
    at `githook.py:76-81` (the `exec python3 "{shim}"` line is
    `githook.py:80`).
  All three already fail OPEN loudly on `ImportError` (the loop is "NOT
  active" with a stderr note). Today that guards a too-old python; after
  this change the shims re-exec through `uv run --project` (§11 Q3), so
  the same loud fail-open must also cover "`uv` not on PATH."
- **The uv project env is the dep-carrying interpreter.**
  `pyproject.toml:15-16` `[project.scripts] loopctl =
  "loop_harness.cli:main"`. The `justfile` already blesses the
  project-env invocation for its own gates: `check` runs `uv run
  pytest` (`justfile:4-7`) and `stamp` runs `uv run loopctl stamp`
  (`justfile:10-11`), both resolving against the synced project env.
  Separately, `justfile:14-19` `install` / `install-editable` recipes
  run `uv tool install --force [--editable] .`; those are an OPTIONAL
  standalone-CLI convenience (README frames them "the plugin path needs
  no install") and are NOT the harness/hook mechanism. Per §11 Q3/Q4
  (RESOLVED), the harness and hooks acquire deps via `uv run --project
  "${CLAUDE_PLUGIN_ROOT}"` against the project env that `uv sync`
  populates, not via any global `uv tool install`. `pyproject.toml:25-27`
  derives the version from `plugin.json`; `pyproject.toml:6` is
  `dependencies = []` today.
- **The "dependency-free" value is stated in five places across two
  documents.** MANIFESTO.md:34 (philosophy, "deliberately
  dependency-free"), MANIFESTO.md:40 (Architecture §2, "a stdlib-only
  Python package"), MANIFESTO.md:238 (Values §4, "Dependency-free
  core"). README.md:55 ("stdlib-only: the system `python3` (3.11+) is
  the only requirement"), README.md:68 ("zero-install invocation
  path"), README.md:168-169 ("deliberately dependency-free ... keep it
  that way"). DECISIONS.md uses lettered sections each anchored to a
  ticket (§R, §S, §F, §G, §P, §Q); a new entry follows that pattern.
- **This repo's own config drives the loop.** `.loop/config.json` has
  `plans_dir: .loop/plans`, `require_eval: true`, and two review passes
  (`adversarial` → loop-reviewer, `architectural` → loop-architect,
  baseline `MANIFESTO.md`). This file is itself migrated by the ticket
  (dogfood clean cutover, §11 Q2 RESOLVED).

## 5. Non-goals / out of scope

- No change to the loop's *behavior*: stage transitions, gate policy,
  fingerprint algorithm, fail-open direction, and the commit-gate
  decision logic stay byte-for-byte in meaning. This is a substrate
  migration, not a semantics change.
- No new config *fields* or CLI *commands*. Parity only.
- No new `loopctl` subcommand group for hooks. Q3 routes hooks through
  `uv run --project`, so `[project.scripts]` gains no hook entry point.
- No global `uv tool install` in the harness or hook path (Q3). The
  optional standalone-CLI `install` recipes in the `justfile` stay as-is
  but are not the harness mechanism.
- No change to `plugin.json` / marketplace / version-derivation wiring.
- No general refactor of the five config-consuming modules beyond the
  minimum the type change forces (e.g. attribute access stays the same
  if pydantic models keep the same field names).
- No config-migration tool, no JSON-compat reader, and no legacy-JSON
  detection/error path (Q2, RESOLVED: clean cutover). `load_config`
  reads only `.loop/config.toml`; a stray `config.json` is simply
  ignored, not diagnosed.

## 6. Requirements & restrictions

- **R1 — the four deps enter via `uv add`, into `pyproject.toml`.**
  typer, rich, pydantic, and `tomli-w` are added with `uv add` so they
  land in `[project.dependencies]` and `uv.lock`, never `uv pip`
  (`.claude/rules/uv-installer.md`). `pyproject.toml:6` moves from
  `dependencies = []` to the pinned four-dep set (§11 Q1 RESOLVED: add
  `tomli-w`).
- **R2 — CLI parity is exact and verified.** Every one of the 19
  subcommands at `cli.py:192-224` keeps its name, positional arguments,
  `choices` constraints (`advance` stage, `block` code), delegations
  (§4), exit codes, and stdout-vs-stderr routing. rich is for
  presentation only and must not change a command's exit code or the
  machine-readable lines other code parses (e.g. `hooks.main` output
  consumed via `ledger`).
- **R3 — config validation stays loud and specific; the reader is
  TOML-only.** pydantic models replace the dataclasses, but the
  rejection messages must remain as actionable as the current
  hand-written `ConfigError` strings (`config.py:224-253` and the two
  parsers). A malformed config must still fail SAFE toward more review,
  never silently green (MANIFESTO.md:30-32 "Fail safe, never fail
  open"). Preserve the `require_review`-with-no-enabled-pass hard error
  (`config.py:246-250`) and the empty-`fingerprint_ignore`-pattern guard
  (`config.py:235-240`). `load_config` reads ONLY `.loop/config.toml`
  via `tomllib`; there is NO legacy `.loop/config.json` branch and NO
  bespoke error for a stale JSON file (Q2). A missing `config.toml`
  yields safe defaults with zero gates, exactly as today.
- **R4 — `write_example_config` serializes via `tomli-w`.** `init`
  writes the one fixed document by dumping `EXAMPLE_CONFIG` (kept as the
  dict source of truth) through `tomli_w.dump`, not a hand-authored
  template string (§11 Q1). A round-trip test proves `load_config`
  re-parses it into the documented defaults.
- **R5 — the launcher path re-execs through `uv run --project`, and a
  missing `uv` fails OPEN loudly.** The SessionStart/PreToolUse/Stop
  hooks and the git backstop must execute their real work under the
  plugin's synced project env, acquired by re-execing via `uv run
  --project "${CLAUDE_PLUGIN_ROOT}"`, not under the system `python3`.
  Each shim stays a stdlib launcher that the system `python3` can always
  START (so the shim itself never needs the deps). When `uv` is absent
  from PATH, every entry fails open with a clear "loop NOT active: `uv`
  not found; run init-loop" message on stderr, exit 0, never a bare
  traceback and never a silent block. This preserves the fail-open
  invariant (MANIFESTO.md:240-241, "Hooks fail open on internal
  error"). (§11 Q3 RESOLVED, overriding the fold-into-loopctl
  global-install recommendation.)
- **R6 — the docs stop lying.** The three "dependency-free / stdlib-only"
  statements (MANIFESTO.md:34,40,238) and the three README claims
  (README.md:55,68,168-169) are revised to state the truth: the core now
  has dependencies and the harness requires `uv` plus the synced project
  env at the plugin checkout. A DECISIONS.md entry records the pivot in
  the repo's established lettered-section-with-ticket-anchor pattern.
  Doc edits pass the slop-scan (`.claude/rules/slop-scan-for-docs.md`).
- **R7 — init-loop makes the repo ready under the same mechanism.**
  Because the loop is now inert without the synced env, init-loop runs
  `uv sync` on the plugin project (so the env exists) and verifies `uv
  run --project "${CLAUDE_PLUGIN_ROOT}" loopctl` resolves before
  declaring the repo ready, rather than leaving setup as prose the
  operator can skim past. It does NOT run `uv tool install` (§11 Q4
  RESOLVED, reconciled to Q3: init-loop and the hook path use the SAME
  synced-project-env mechanism).
- **R8 — every touched Python object stays fully typed and
  documented.** New pydantic models, typer commands, and helpers carry
  numpy-convention docstrings (`.claude/rules/python-docstrings.md`) and
  complete type hints (`.claude/rules/python-type-hints.md`); the
  pydantic mypy plugin is enabled so the generated `__init__` is checked
  (`.claude/rules/python-type-hints.md`, Pydantic section). ruff `D1`
  and mypy `--strict` are gates (`pyproject.toml`
  `[tool.ruff.lint]:42`, `[tool.mypy]:49-52`).
- **R9 — surgical, gates green, no skips.** Every changed line traces to
  this ticket (CLAUDE.md §3). The repo gates
  (`git add --intent-to-add -A . && uv run pytest`, then
  `uvx prek run --all-files`) go green with no `# type: ignore`,
  `skip`, or `--no-verify` used to force them
  (`.claude/rules/prek-code-quality.md`,
  `.claude/rules/pre-existing-issues.md`).
- **R10 — adversarial review before done.** Run the adversarial review
  (`.claude/rules/adversarial-reviews.md`) plus the repo's configured
  `architectural` pass against MANIFESTO.md, since this ticket edits the
  baseline itself.

## 7. Code surface

- `pyproject.toml:6` — `dependencies = []` → add typer, rich, pydantic,
  `tomli-w` (via `uv add`; pinned floors). `[tool.mypy]` (`:49-52`) —
  add `plugins = ["pydantic.mypy"]`. `[project.scripts]` (`:15-16`) —
  `loopctl` stays as-is; NO new hook entry point (Q3 uses `uv run
  --project`, not a `loopctl hook` subcommand).
- `src/loop_harness/config.py` — full rewrite. `CONFIG_FILE:20`
  `config.json` → `config.toml`. `EXAMPLE_CONFIG:28-64` stays the dict
  source of truth. `ReviewPass:71`, `ActionStage:115`, `LoopConfig:148`
  frozen dataclasses → pydantic `BaseModel`s (keep field names so the
  five importers need no attribute changes; keep
  `enabled_review_passes`/`enabled_action_stages` and
  `verdict_filename`). `load_config:208` → `tomllib.load` + pydantic
  validation, translating `ValidationError` into the existing loud
  `ConfigError` messages (R3); reads ONLY `config.toml`, no
  legacy-JSON branch (Q2). `_parse_review_passes:272` /
  `_parse_action_stages:319` → pydantic validators (preserve the
  cross-field uniqueness of ids across passes and stages,
  `config.py:341,350-354`, and the `after` anchor check,
  `config.py:365-369`). `write_example_config:379` → dump
  `EXAMPLE_CONFIG` through `tomli_w.dump` (R4).
- `src/loop_harness/cli.py` — rebuild on typer+rich, preserving §4's
  surface (R2). Keep the `cmd_*` helpers' logic and delegations; replace
  only the argparse plumbing (`:188-225`) and the dispatch chain
  (`:228-269`). No hook subcommand group.
- `src/loop_harness/stamp.py:25,127-128` — `CONFIG_FILE` import and the
  fingerprint re-bind; verify the rename flows and the bound path is the
  new `config.toml`. No logic change expected.
- `scripts/loopctl.py`, `scripts/run_hook.py`, `scripts/run_git_hook.py`
  — rework each into a re-entrant stdlib launcher: when started by the
  system `python3` (deps absent), locate `uv` (`shutil.which("uv")`); if
  absent, fail open loudly (exit 0, stderr "loop NOT active: `uv` not
  found; run init-loop"); otherwise re-exec `uv run --project
  "${CLAUDE_PLUGIN_ROOT}" ...` into the synced env, where the deps
  resolve and the real entry (`cli.main` / `hooks.main` /
  `githook.pre_commit`) runs. Keep the existing loud `ImportError`
  fail-open as the inner guard. `${CLAUDE_PLUGIN_ROOT}` is the plugin
  root the shim already derives from its own path.
- `hooks/hooks.json:9,21,31,42` — the four `command` strings continue to
  invoke `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/run_hook.py" <entry>`
  (the system `python3` STARTS the shim, which re-execs `uv run
  --project`). They must reference no `uv tool install` and no global
  `loopctl`. If the shim signature is unchanged, these strings may not
  change at all; the routing change lives in the shim.
- `src/loop_harness/hooks.py:489-490` — the `[loop] ctl:` context line
  must print the new blessed invocation, `uv run --project
  "{plugin_root}" loopctl`, not `python3 scripts/loopctl.py`.
- `src/loop_harness/githook.py:76-81` — `_hook_body` keeps `exec python3
  "{shim}"` (line `:80`) pointing at `run_git_hook.py`, which re-execs
  `uv run --project` per above; `MARKER` and the install/uninstall
  refusal logic stay.
- `justfile` — add a `sync` recipe (`uv sync`) that init-loop and the
  ticket bless as the harness setup step; leave the optional `install` /
  `install-editable` recipes (`:14-19`) intact but do not present them as
  the harness/hook mechanism (see the operator flag in the handback).
- `MANIFESTO.md:34,40,238` — revise all three "dependency-free /
  stdlib-only" statements; reconcile the §2 Architecture prose
  (`:40`, "a stdlib-only Python package").
- `README.md:55,68,168-169` — revise the three zero-install/stdlib-only
  claims to state the `uv` + synced-project-env requirement. The
  optional standalone `uv tool install` prose (README.md:63-64,176) is
  already framed as optional/additive and is out of scope, but must not
  be left contradicting the revised claims.
- `DECISIONS.md` — add a new lettered section (ticket-anchored to this
  slug) recording the pivot: what value was dropped and why, and the
  `uv run --project` launcher-routing decision.
- `.loop/config.json` → `.loop/config.toml` — convert this repo's own
  config (clean cutover, §11 Q2); delete the JSON so only one file is
  bound by the fingerprint.
- Skills/docs/agents carrying the literal `.loop/config.json`:
  `skills/init-loop/SKILL.md` (config.json→toml throughout, AND replace
  the setup mechanic: add a `uv sync` step and a `uv run --project
  "${CLAUDE_PLUGIN_ROOT}" loopctl` verify before ready, since the loop
  is now inert without the synced env — Q4),
  `skills/create-ticket/SKILL.md:34,125`,
  `skills/create-eval/SKILL.md:22,82`,
  `skills/implement-ticket/SKILL.md:77,124`,
  `docs/onboarding.md` (the `config.json` mentions incl. the fingerprint
  "except config.json" text at `:179` and the `config.py` row at `:677`),
  `docs/tutorials/custom-reviews-and-actions.md` (incl. the
  `python3 -m json.tool .loop/config.json` validation commands at
  `:122,232`, which become a TOML-parse check),
  `agents/loop-reviewer.md:16`, `agents/ticket-planner.md:20`.

### Test homes (every named test below lives here)

- `tests/test_config.py` — pydantic validation + TOML round-trip. Its
  `_write` helper (`test_config.py:20-24`, currently JSON) becomes TOML.
- `tests/test_cli.py` — typer parity. Its `_configure` helper
  (`test_cli.py:19-23`, currently JSON) becomes TOML.
- `tests/test_manifest.py` — hooks-wiring + deps guard.
- `tests/test_githook.py` — managed-hook-body invocation assertion.
- `tests/test_hooks.py` — SessionStart `[loop] ctl:` line assertion.
- `tests/test_launcher.py` (new) — launcher `uv`-absent fail-open.

## 8. Tests & validation gates

- **Repo gates (from `.loop/config.toml` post-cutover; today
  `.loop/config.json`):** `git add --intent-to-add -A . && uv run
  pytest`, then `uvx prek run --all-files` (ruff-lint, ruff-format, mypy
  per `.pre-commit-config.yaml`). Prefer the `just check` recipe, which
  encodes the blessed invocation (`.claude/rules/prek-code-quality.md`).
  `loopctl stamp` records the evidence.
- **Config tests (`tests/test_config.py`):** (1) round-trip —
  `write_example_config` emits TOML (via `tomli-w`) that `load_config`
  re-parses into the documented defaults; (2) every field parses (gates,
  plans_dir, notify_title, max_review_cycles, review_passes,
  require_review, require_eval, action_stages, fingerprint_ignore); (3)
  each rejection path still raises `ConfigError` with a specific message
  — malformed gates, bare-string gates, empty `fingerprint_ignore`
  pattern, duplicate pass/stage id, unknown `after` anchor,
  `require_review` with no enabled pass; (4) a missing `config.toml`
  yields safe defaults with zero gates. There is NO legacy-JSON error
  test: per Q2 the reader ignores a stray `config.json` entirely rather
  than diagnosing it. Extend the existing suite rather than replacing
  it; keep the behavioral assertions, swap the serialization.
- **CLI parity tests (`tests/test_cli.py`):** a parametrized test that
  every subcommand in §4's list dispatches and returns the expected exit
  code in a real temp repo (extend the existing end-to-end style); keep
  asserting `advance`'s stage `choices` and `block`'s code `choices` are
  enforced; assert the `ledger`/`verify`/`reconcile`/`halt` delegations
  still produce their downstream output.
- **Hooks-wiring + deps guard (`tests/test_manifest.py`):** assert every
  `command` in `hooks/hooks.json` invokes the `scripts/run_hook.py` shim
  and references no `uv tool install` / no global `loopctl`; assert each
  shim source (`scripts/loopctl.py`, `run_hook.py`, `run_git_hook.py`)
  re-execs via `uv run --project` with `${CLAUDE_PLUGIN_ROOT}`; assert
  `pyproject.toml` `[project.dependencies]` contains typer, rich,
  pydantic, AND `tomli-w` (mirrors the existing manifest-wiring tests at
  `test_manifest.py:87`).
- **Managed-hook body test (`tests/test_githook.py`):** the installed
  `.git/hooks/pre-commit` body invokes the `run_git_hook.py` shim and
  still carries the `MARKER`; install/uninstall refusal semantics
  unchanged.
- **SessionStart context test (`tests/test_hooks.py`):** the
  session-start output's `[loop] ctl:` line prints `uv run --project
  "..." loopctl`, not `python3 scripts/loopctl.py`.
- **Launcher `uv`-absent fail-open test (`tests/test_launcher.py`,
  new):** run the real shim process with a PATH that omits `uv`; the
  entry exits 0 (fail open) and prints a loud "loop NOT active: `uv` not
  found" message to stderr (R5) — never raises, never blocks. Exercise
  the real shim process, do not mock `shutil.which` / the import
  machinery. Cover `run_git_hook.py` as well so the git backstop's
  `uv`-absent path is proven.
- **Doc gate:** MANIFESTO.md and README.md edits run the three-layer
  slop-scan (`.claude/rules/slop-scan-for-docs.md`); no surviving
  "dependency-free / stdlib-only" claim, no dead `config.json` reference.
- **Review gates:** `loop-reviewer` (adversarial) and `loop-architect`
  (architectural, baseline `MANIFESTO.md`) per `.loop/config`
  `review_passes`.
- **Eval marker (the acceptance layer):**
  `.loop/evals/loopctl-typer-pydantic-toml.md` — 14 deterministic/100%
  scenarios covering the three guardrails (config fails loud, launcher
  fails open, docs stop lying), all five `ConfigError` branches, both
  launcher shims, CLI parity + rich-bleed, config round-trip,
  safe-defaults, and the SessionStart invocation line. `require_eval` is
  set, so the loop refuses pickup until this marker validates
  (`loopctl eval loopctl-typer-pydantic-toml` → `valid`).

## 9. Risk assessment

- **Blast radius: the harness's own bootstrap, in every consumer repo.**
  This is the highest-stakes surface in the codebase. If the launcher
  rework is wrong, the SessionStart hook, the commit gate, the state
  guard, the stop check, and the git backstop all stop loading wherever
  the plugin is installed — the loop silently goes inert. The fail-open
  design means a broken interpreter selection does not *block* commits,
  but it does *disable the gate*, which is the failure the loud stderr
  message (R5) exists to make visible. This is why the launcher subticket
  ships the `uv`-absent fail-open test.
- **New hard prerequisites, and the Q3 tradeoffs they lock in.**
  Post-change the harness REQUIRES (a) `uv` on PATH for every hook fire
  and (b) a synced project env at the plugin checkout. `uv run
  --project "${CLAUDE_PLUGIN_ROOT}"` re-exec adds per-fire overhead and
  may trigger a sync if the env is stale, so hooks are slower than the
  old direct `python3` call and couple to the plugin dir being present,
  writable, and synced. A consumer who updates the plugin without
  re-running init-loop gets an inert loop until the env is re-synced.
  The init-loop `uv sync` + verify step (R7) and the loud message are
  the mitigations; the "no install step" promise is gone.
- **Reversibility.** Medium. The change is a single ticket/commit and
  revertible in git, but once a consumer's `.loop/config.json` is
  converted to `.loop/config.toml` and committed, rolling back the code
  without rolling back the config leaves a repo whose config the old
  code cannot read. Reversibility is clean only if code and config move
  together.
- **Likeliest failure modes.** (a) A pydantic model silently *accepts*
  a shape the old hand-parser rejected (e.g. coerces a bare-string
  `gates` field), turning a loud failure into a wrong-gates green — R3
  and the config rejection tests guard this. (b) rich formatting bleeds
  into a machine-parsed CLI line and breaks a delegation
  (`ledger`/`reconcile`) — R2 and the parity tests guard this. (c) `uv`
  is absent, or `uv run --project` fails to resolve the env, so every
  hook fails open and the loop is silently inert — the launcher
  `uv`-absent test and the loud message guard this. (d) A stale
  `.loop/config.json` left beside the new `.loop/config.toml` stays
  unbound by the fingerprint and confuses reviewers — the cutover
  subticket deletes it.

## 10. Subtickets (ordered, dependency-aware)

1. **Add deps + tooling.** `uv add typer rich pydantic tomli-w`; enable
   the pydantic mypy plugin in `pyproject.toml`. → verify: `uv.lock` and
   `[project.dependencies]` list all four; `uv sync`; `uv run python -c
   "import typer, rich, pydantic, tomli_w"` succeeds.
2. **Config module → TOML + pydantic** (`config.py`, `test_config.py`).
   Preserve every rejection message and default; `write_example_config`
   dumps via `tomli-w`; `load_config` reads only `config.toml` (no
   legacy branch). → verify: `uv run pytest tests/test_config.py` green,
   including all `ConfigError` paths.
3. **CLI module → typer + rich** (`cli.py`, `test_cli.py`). Parity for
   all 19 subcommands, delegations, and exit codes. → verify:
   `uv run pytest tests/test_cli.py` green; each subcommand dispatches.
4. **Launcher / hook rework** (`scripts/loopctl.py`,
   `scripts/run_hook.py`, `scripts/run_git_hook.py`, `hooks/hooks.json`,
   `hooks.py:489-490`, `githook.py:76-81`, `justfile` `sync` recipe;
   `skills/init-loop` gains the `uv sync` + verify step;
   `test_manifest.py`, `test_githook.py`, `test_hooks.py`, new
   `test_launcher.py`). Re-exec through `uv run --project
   "${CLAUDE_PLUGIN_ROOT}"`; fail open loudly when `uv` is absent. →
   verify: manifest + launcher tests green; a fresh clone with `uv`
   removed from PATH prints the loud "loop NOT active" message and
   blocks nothing.
5. **Cut over this repo's own config** (`.loop/config.json` →
   `.loop/config.toml`; confirm `stamp.py` binds the new path). →
   verify: `uv run loopctl stamp` green under the TOML config; only one
   config file exists.
6. **Honesty edits + doc/skill ripple** (`MANIFESTO.md:34,40,238`,
   `README.md:55,68,168-169`, new `DECISIONS.md` section, and every
   `.loop/config.json` reference in §7's skill/doc/agent list). →
   verify: slop-scan clean; no surviving stdlib-only claim; no dead
   `config.json` reference (`grep -rn "config.json" skills docs agents`
   returns only intentional historical mentions, if any).

## 11. Open questions

All four sub-forks are RESOLVED by the operator (recorded here as an
audit trail; the resolutions are folded into §4–§10). The original
recommendation is retained under each so the override is visible.

- **Q1 — TOML *writer* dependency: needed or not?** *Original
  recommendation: no writer dep, emit a hand-authored template string.*
  **RESOLVED (operator, OVERRIDES recommendation): ADD `tomli-w`.** The
  dependency set is now four: typer, rich, pydantic, `tomli-w`.
  `write_example_config` serializes `EXAMPLE_CONFIG` programmatically
  via `tomli_w.dump` rather than a template string. Folded into R1, R4,
  §7 (pyproject, config.py), §8 (round-trip + deps tests), §10 (ST1–2).
- **Q2 — clean cutover vs. a JSON-compat reader.** *Original
  recommendation: clean cutover, but with `load_config` raising a loud
  `ConfigError` on a legacy `.loop/config.json`.* **RESOLVED (operator,
  OVERRIDES the legacy-detection half): greenfield clean cutover, NO
  migration and NO legacy detection.** `load_config` reads only
  `.loop/config.toml`; there is no dual-format reader and no special
  error for a stale `config.json` (it is ignored). This repo's own
  `.loop/config.json` is still converted (§10 ST5). Folded into §5
  (non-goals), R3, §8 (no legacy-error test).
- **Q3 — how the hooks acquire a dep-carrying interpreter.** *Original
  recommendation: fold hook entry points into `loopctl` subcommands and
  have the shims discover a globally-installed `loopctl`.* **RESOLVED
  (operator, OVERRIDES recommendation): `uv run --project` shim.** Hooks
  and the git backstop re-exec via `uv run --project
  "${CLAUDE_PLUGIN_ROOT}"` into the plugin's synced project env. No
  global `uv tool install`, no `loopctl hook` subcommand. Tradeoffs
  (requires `uv` on PATH; requires a synced env at the plugin checkout
  on every hook fire; per-fire overhead) recorded in §9; `uv`-absent
  fail-open is a named test (§8, §7 shims). Folded into §1, §2, R5, §7,
  §9, §10 (ST4).
- **Q4 — does init-loop install the tool, or only instruct?** *Original
  recommendation: init-loop runs `uv tool install` and verifies
  `loopctl` resolves.* **RESOLVED (operator, RECONCILED to Q3):
  init-loop runs `uv sync` on the plugin project and verifies `uv run
  --project "${CLAUDE_PLUGIN_ROOT}" loopctl` resolves before declaring
  the repo ready — NOT `uv tool install`.** init-loop and the hook path
  use the SAME synced-project-env mechanism. Folded into R7, §7
  (justfile `sync` recipe, init-loop skill), §10 (ST4). Operator flag:
  the `justfile` `install` / `install-editable` recipes (`:14-19`) still
  bless `uv tool install`, but they are an optional standalone-CLI path
  and do not feed the harness/hook mechanism, so they do not conflict;
  they are left intact and a `sync` recipe is added alongside.
