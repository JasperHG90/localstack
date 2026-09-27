# CLAUDE.md

The project overview and where each topic is documented: `AGENTS.md`. What
goes in each folder: `.claude/rules/monorepo-layout.md`. Gates, from the repo
root: `uvx prek run --all-files`, `uv run --directory packages/<name> pytest
-q` for each distribution, and `uv run --directory tests pytest -q` for the
repository itself.

Below are the repo-wide constraints an agent gets wrong by guessing. Each names
the file that owns the detail, and the reasoning is in `.okf/`.

- **Releases are cut by a human, per artifact.** Tags are `<family>-X.Y.Z` with
  no `v`. A manual run picks an increment, which
  `scripts/next_release_version.py` applies to the newest tag, or takes a
  typed version. `scripts/resolve_release_artifact.py` owns the family map
  and maps a tag to one artifact. See
  `docs/reference/releases.md`.
- **Templates and artifacts move together.** `scripts/check_version_coupling.py`
  refuses a commit whose SDK imports, majors or archetype sources disagree.
- **Tool config is top-level, mypy runs per environment.** `[tool.ruff]` and
  `[tool.mypy]` sit in the root `pyproject.toml` only. Each mypy hook passes
  `--config-file` naming the root file and runs inside a package's or the
  tests project's environment, because `uvx mypy` reports a vacuous zero. CI
  does not run mypy.
- **Every file in `scripts/` is a uv script.** Its PEP 723 block declares its
  Python and dependencies, and every caller, shipped hooks included, runs it
  with `uv run --script`.
- **Workflows are linted, by actionlint, in two trees:** this repo's
  `.github/workflows/` and the golden fixture's rendered agent repo, both
  through `scripts/check_workflows.py`. CI runs no pre-commit hooks.
- **`scaffold spoke` clones `gcp-tf-template` itself** into a new directory and
  never writes onto an existing clone. See
  `.okf/decisions/0011-scaffold-is-scaffold-not-merge.md`.
- **The harness plugin is the only install channel.** The manifests in
  `.claude-plugin/` name the `skills/` directory, so adding a skill needs no
  manifest edit. See
  `.okf/decisions/0007-skills-ship-only-as-harness-plugins.md`.
- **Shipped hooks only refuse what a CLI verb already refuses**, and name that
  verb. One manifest per harness: `hooks/claude-hooks.json` and
  `hooks/hooks.json`. Anchor every matcher. Every hook fails open and says so
  on stderr. A missing script fails closed, because `uv run --script` exits 2. The
  contract is in `scripts/cli_owned_guard.py`.
- **The hub owns the team file's shape.** `team init` and `team edit` read
  `schema/teams.schema.json` from the local hub clone, so never copy the shape
  here. Edits go through `yaml_edit.py`, which changes only the target value,
  because the file carries comments people wrote. `gh pr checks --json` exits 0
  on a failing PR, so `hub_checks.py` reads the payload.
- **A team's pending change is its pull request on the hub**, from
  `register-<team>`, and `--team` finds it by that name, so the CLI keeps no
  state. Every read of the hub clone names a commit, because a fetch never
  moves the checked-out files. See
  `.okf/decisions/0047-a-team-s-pending-change-is-its-hub-pull-request.md`.
- **Datadog is LLM Observability, not APM.** Agents import
  `agentic_platform_sdk.autotrace` first, which starts `ddtrace.auto` from
  `DD_LLMOBS_ENABLED`, as rail-store-buddy does. The archetype's `datadog`
  input sets `DD_SERVICE`, which ddtrace uses as `ml_app`, to the service name
  and turns trace propagation off, so no header can pick another team's
  dataset. LLM Obs spans carry prompts and responses on purpose. See
  `packages/agentic-platform-sdk/README.md` and ADR 0038.
- **The only `CLAUDE.md` is this one.** Tests refuse a nested one. `.gitignore`
  un-ignores `.claude/` files by name, so a new rule needs an entry there.
- **Tests of anything but a distribution's own code live in `tests/`**, one
  uv project that is not a distribution. Harness cases install the tracked
  paths, with their working-tree contents, inside the harness's shakedown image through testcontainers, selected
  with `-m "container and claude_code"` or `gemini_cli`.
