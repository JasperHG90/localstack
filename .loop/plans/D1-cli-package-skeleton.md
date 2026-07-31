---
epic = "cli"
depends_on = []
priority = 47
tags = ["cli", "python", "tooling"]
summary = """
Create the cli/ Python package, its `localstack` entrypoint, and the ruff,
mypy and pytest gates this repo does not have yet. Skeleton only: no login,
no read commands, no TUI, no breakglass. Those are D2 to D5. The value is
that this is the repo's first Python packaging, so the layout, the install
path and the gate wiring get decided once instead of four times.
"""
---

# D1: CLI package skeleton

## Title
Create `cli/` as a real Python package with a working `localstack`
entrypoint and the lint, type and test gates the repo currently lacks, so
D2 to D5 have a place to land and a gate that catches them.

## Size / Effort
**M.** Few lines, several decisions. This is the first Python packaging in
the repo: a new manifest, a lock file, three new pre-commit hooks in a
config that has no Python gates today, and two doc updates. The code itself
is a `--version`, a `--help` and a 20-line config reader.

## Triggered by
Operator wants a `localstack` developer CLI for this cluster: a `login`
that authenticates to Vault and brokers Nomad and Consul tokens, read-only
convenience commands, a Textual health panel, and a `breakglass`. D1 is the
skeleton for all of it. The operator's first instinct was a single-file uv
script and they rejected it: a Textual TUI plus four typer groups outgrows
one file, and the repo's testing rule needs a place to put mirrored tests.

## Context (today's state)
- **No Python packaging anywhere in the repo.** No `pyproject.toml`, no
  `uv.lock`, no `setup.py` outside `.cache/`. The only `.py` files are under
  `.claude/` (untracked, `.gitignore:19`) and `.loop/evals/`.
- `requirements.txt` at the repo root lists `duckdb[all]`, `pendulum`,
  `httpx`, `ipykernel`, `hvac`. Nothing installs it. Its only mention in the
  repo is a code sample at `docs/nats-postgres-cdc-bridge.md:199`. It is not
  a project manifest. Leave it alone.
- `.python-version` is `3.12`; `AGENTS.md:134` states the same.
- **Python coverage in pre-commit is two hooks**: `check-ast`
  (`.pre-commit-config.yaml:7`) and `debug-statements` (`:11`). A grep for
  `ruff` and `mypy` across `justfile`, `.pre-commit-config.yaml` and
  `AGENTS.md` returns nothing. No pytest anywhere.
- **Local-hook pattern to copy**: `.pre-commit-config.yaml:14-33`. Shape is
  `repo: local`, `language: system`, a `types:` filter, and
  `pass_filenames: false` for whole-tree tools. `terraform-validate`
  (`:28-33`) shells out to `scripts/tf_validate.sh`.
- `.pre-commit-config.yaml:1` excludes only `^\.(claude|loop)/`, so a new
  `cli/` tree is already in scope for every existing hook, including
  `end-of-file-fixer` (`:13`).
- **Root justfile**: `set shell := ["bash", "-uc"]` (`:1`), aliases
  (`:3-7`), `format` (`:10-11`), `setup` (`:14-15`), `pre_commit`
  (`:18-19`, runs `pre-commit run --all-files`), `unseal_vault` (`:22-23`),
  `worktree_setup` (`:30-32`).
- **Per-directory justfiles are the convention** (`AGENTS.md:129`).
  Existing ones: `bootstrap/justfile`, `deployments/infrastructure/justfile`
  (style reference at `:1-5`), `deployments/applications/justfile`,
  `applications/migrations/justfile`.
- **The loop's only gate is `just pre_commit`** (`.loop/config.json:2-4`).
  A test suite not reachable from that command is a suite the loop never
  runs. `require_eval` is `true` (`.loop/config.json:6`).
- **Dev container already has the tooling**: uv pinned to 0.11.16
  (`.devcontainer/Dockerfile:7`), pre-commit installed as a uv tool (`:21`),
  and `RUFF_CACHE_DIR` exported (`:3`) even though no ruff config exists.
  `prek` is not installed on PATH; `pre-commit` is. The blessed invocation
  is `just pre_commit`.
- **Cluster addresses are already in the process env.** `VAULT_ADDR`,
  `NOMAD_ADDR`, `CONSUL_HTTP_ADDR`, `VAULT_TOKEN` and `NOMAD_TOKEN` are set
  in the dev shell, fed from `.devcontainer/.env` through `runArgs
  --env-file` (`.devcontainer/devcontainer.json:37-40`). The shape is
  documented at `.devcontainer/.env.example:2-11`.
- **`cli/.venv` is already ignored.** `.gitignore:3` is a bare `.venv` with
  no slash, so git matches it at any depth: `git check-ignore -v cli/.venv`
  reports `.gitignore:3`. `cli/pyproject.toml` and `cli/uv.lock` are not
  ignored. No `.gitignore` change is needed.
- `.devcontainer/devcontainer.json:31` sets `python.pythonPath` to
  `/home/vscode/workspace/.venv/bin/python`, a root venv that does not
  exist and never has.
- **No CI runs tests.** `.github/workflows/` holds `claude-ollama.yaml` and
  `hermes-interactive.yaml`, both Claude bots on issue and PR events.
- **Loop worktrees cannot see `.claude/rules/`.** `.claude` is gitignored
  (`.gitignore:19`) and `git worktree add` checks out tracked files only.
  Confirmed: `.loop/worktrees/F2-foundation-vault-oidc-provider/` has no
  `.claude`. The rules that constrain this ticket are therefore restated in
  full below, not merely cited.

## Non-goals / out of scope
- No `login`, no Vault authentication, no Nomad or Consul token brokering,
  no HTTP client for any of the three. That is D2.
- No read-only commands and no typer sub-groups. That is D3. Do not
  scaffold empty groups "ready for D3": an empty group is a guess about
  D3's shape.
- No Textual TUI and no `textual` dependency. That is D4.
- No `breakglass`. That is D5.
- No root `pyproject.toml`, no uv workspace, no edit to `requirements.txt`,
  no packaging for anything outside `cli/`.
- No CI workflow. The repo has no test CI and this ticket does not add one.
- No publishing to any package index. The CLI is installed from the working
  tree only.
- No changes to the existing pre-commit hooks, terraform, Nomad job files
  or Ansible.
- No edit to `.loop/config.json`. Its gate list is operator config.

## Requirements & restrictions
1. **Package under `cli/`, src layout, its own `cli/pyproject.toml`.**
   Operator decision, already made. Do not re-open it, and do not add a
   root manifest.
2. **Console script named `localstack`**, declared in
   `[project.scripts]`. Operator-given.
3. `requires-python = ">=3.12"`, matching `.python-version` and
   `AGENTS.md:134`.
4. **Dependencies go in with `uv add`**, never `uv pip`, so they land in
   `cli/pyproject.toml` rather than only in an environment. Restated from
   `.claude/rules/uv-installer.md`, which the implementer's worktree cannot
   read. Do not hand-write the dependency table.
   - Runtime: `typer`. Add `rich` only if the code imports it directly;
     typer already pulls it in.
   - Dev (`uv add --dev`): `pytest`, `mypy`, `ruff`.
5. **Commit `cli/uv.lock`.** It is the single pin for every tool version
   the gates run, and a fresh worktree needs it to build an environment.
6. **Tests mirror the source tree** and run through `uv`, never a bare
   `pytest`. `cli/src/localstack_cli/config.py` is tested in
   `cli/tests/test_config.py`. Restated from
   `.claude/rules/python-testing.md`.
7. **Register the live-cluster marker now.** Any test that touches the real
   cluster must carry a marker and be excluded from the default run through
   `addopts`. D1 adds no such test, but it declares the marker (`cluster`)
   and the `addopts` exclusion in `cli/pyproject.toml` so D2 to D5 inherit
   a default run that is fast and offline. Same rule file as above.
8. **Tests must not read the real environment.** Use `monkeypatch` for env
   vars so a developer's live `VAULT_ADDR` cannot change a result.
9. **Gates run through `just` or pre-commit, never the bare tool.** The
   pre-commit config is the source of truth for what runs. Restated from
   `.claude/rules/prek-code-quality.md`.
10. **New Python hooks follow the existing local-hook style**
    (`.pre-commit-config.yaml:14-33`): `repo: local`, `language: system`,
    and scoped with `files: '^cli/'` so an HCL-only or terraform-only
    commit does not pay for them.
11. **One place pins the tool versions**: `cli/pyproject.toml` dev
    dependencies plus `cli/uv.lock`. Do not additionally pin ruff or mypy
    through an upstream pre-commit `rev`, which would create two pins that
    drift apart.
12. **`just pre_commit` from the repo root stays green and exercises the
    new hooks.** It is the loop's only gate (`.loop/config.json:2-4`).
13. **`--version` reads the installed distribution metadata**
    (`importlib.metadata.version`), not a hardcoded string, so it cannot
    drift from `cli/pyproject.toml`.
14. Every code change ships with a test
    (`.claude/rules/python-testing.md`).
15. Plain language in every doc, comment and commit message
    (`.claude/rules/plain-language.md`).
16. Adversarial review by a sub-agent before this is reported done
    (`.claude/rules/adversarial-reviews.md`).

## Code surface
- `cli/pyproject.toml` **(new)**: `[project]` with name, version,
  `requires-python`, dependencies; `[project.scripts] localstack =
  "localstack_cli.main:main"`; `[tool.pytest.ini_options]` with the
  `cluster` marker and the `addopts` exclusion; `[tool.ruff]` and
  `[tool.mypy]` config. Generated and edited through `uv add` where
  possible.
- `cli/uv.lock` **(new, generated, committed)**.
- `cli/src/localstack_cli/__init__.py` **(new)**: empty or a one-line
  docstring.
- `cli/src/localstack_cli/main.py` **(new)**: `app = typer.Typer()`, a
  `--version` callback reading `importlib.metadata.version`, and a `main()`
  the console script points at. No sub-commands.
- `cli/src/localstack_cli/config.py` **(new)**: one frozen dataclass
  holding the three cluster addresses, loaded from `VAULT_ADDR`,
  `NOMAD_ADDR` and `CONSUL_HTTP_ADDR`, raising an error that names the
  missing variable. About 20 lines. No HTTP client, no token handling.
- `cli/tests/test_main.py` **(new)**.
- `cli/tests/test_config.py` **(new)**.
- `cli/justfile` **(new)**: `test`, `lint`, `typecheck`, and whatever the
  install recipe ends up being. Style reference:
  `deployments/infrastructure/justfile:1-5` (`set shell`, then aliases).
- `.pre-commit-config.yaml`: append three hooks to the existing `local`
  repo block, after `:33`. Do not touch `:1-33`.
- `justfile`: one recipe so a developer installs the CLI from the repo root
  the way they already run `just setup` (`:14-15`). Place it near the other
  setup recipes; keep the file's comment-per-recipe style.
- `AGENTS.md`: a `### CLI (cli/)` command block after the migrations block
  (`:102-106`), in the same shape as the blocks at `:88-106`. Everything
  from `:71` down is outside the aim marker region (markers end at `:70`),
  so it is safe to edit.
- `README.md:21-25`: the layout table lists three deploy layers. Add a row
  for `cli/`, worded as a tool rather than a fourth deploy layer.
- `.devcontainer/devcontainer.json:31`: repoint `python.pythonPath` at
  `/home/vscode/workspace/cli/.venv/bin/python`. See Q4.

Anything not on this list is out of scope. Needing a file that is not here
is the `out-of-scope-fix-needed` blocker, not a judgment call.

## Tests & validation gates

### The repo gate
`just pre_commit` from the repo root, all hooks Passed. This is the loop's
gate (`.loop/config.json:2-4`). Run it and read the output: a new hook that
reports no files is a hook that did not run, and that is a failure of this
ticket, not a pass.

### The three hooks to add
All three as `repo: local`, `language: system`, `files: '^cli/'`, appended
after `.pre-commit-config.yaml:33`.

1. **ruff** (lint and format) through `uv run` with `cli/` as the project
   root.
2. **mypy** over `cli/src` and `cli/tests`, `pass_filenames: false`.
3. **pytest** over `cli/tests`, `pass_filenames: false`.

Pre-commit runs hooks with the repo root as the working directory, so every
entry needs uv pointed at the `cli/` project (`uv run --directory cli ...`
or `--project`). **Confirm the exact flag against `uv run --help` before
writing it into the config rather than trusting this line.** uv 0.11.16 is
what the container pins (`.devcontainer/Dockerfile:7`).

### Tests to add
- `cli/tests/test_main.py`
  - `--version` exits 0 and prints exactly the version
    `importlib.metadata.version` reports for the installed distribution.
    Use `typer.testing.CliRunner`. Assert against the metadata, not a
    literal, so the test fails if the two ever disagree.
  - `--help` exits 0 and names the `localstack` program.
- `cli/tests/test_config.py`
  - All three env vars set: the loader returns them. `monkeypatch.setenv`.
  - One env var missing: the error names the missing variable.
    `monkeypatch.delenv`. Parametrize over the three.

No test may reach the real cluster, and none needs the `cluster` marker
yet.

### Manual check
Install the CLI the way a developer will, then from a directory that is not
the repo run `localstack --version` and `localstack --help`. A package that
only works from inside `cli/` has not proven the entrypoint.

### Fresh-worktree check
`cli/.venv` does not exist in a new loop worktree, and `just worktree_setup`
(`justfile:30-32`) seeds only the SSH key and tfvars. Run `just pre_commit`
in a fresh worktree and confirm it passes, which means `uv run` builds the
environment from `cli/uv.lock` on first use. If it does not, report that
rather than working around it: it decides whether `worktree_setup` needs a
Python step, which is a follow-up ticket, not this one.

### Evals
`require_eval` is `true` (`.loop/config.json:6`), so the authoritative
scenario set is `.loop/evals/D1-cli-package-skeleton.md`. This ticket does
not author it; that step needs operator sign-off.

## Risk assessment
- **Blast radius: additive and small.** One new top-level directory, three
  appended hooks, two doc edits, one editor setting. Nothing existing
  changes behavior.
- **The gate is the real risk.** Three new hooks now run on commits in a
  repo whose pre-commit is fast today. Scoping every Python hook with
  `files: '^cli/'` keeps terraform and HCL commits at their current cost.
  Getting that scope wrong makes every commit in the repo slower.
- **First-run cost and the network.** `uv run` resolves and builds the
  environment on first invocation. On a fresh worktree, or on a machine
  with a cold uv cache, the first `just pre_commit` after this lands is slow
  and needs network. That is why the fresh-worktree check is a gate and not
  a nice-to-have.
- **Name collision.** `localstack` is also the console script of the AWS
  emulator on PyPI. A developer who installs both gets whichever shim wins
  on PATH. The name is the operator's decision; record the clash in the
  AGENTS.md block instead of quietly renaming.
- **A wrong layout is the expensive failure.** D2 to D5 all build on this,
  so moving the package later costs four tickets of churn. That is why the
  layout, install path and config-source questions are settled here rather
  than discovered in D2.
- **Reversibility: high.** Delete `cli/`, revert the three hooks and the doc
  lines. No cluster state, no secrets, no terraform.

## Subtickets (ordered)
1. `cli/pyproject.toml`, src layout, `main.py`, `--version` and `--help`,
   `cli/tests/test_main.py`. Verify by running the entrypoint by hand.
2. Commit `cli/uv.lock`. Add `cli/justfile` and the root install recipe.
3. Wire the three local hooks into `.pre-commit-config.yaml`. Verify `just
   pre_commit` is green from the repo root and that each new hook actually
   ran.
4. `config.py` plus `cli/tests/test_config.py`. Register the `cluster`
   marker and the `addopts` exclusion.
5. Docs: the AGENTS.md block, the README layout row, the devcontainer
   interpreter path.
6. Fresh-worktree check, then adversarial review by a sub-agent.

If these ever become separate plan files, chain them with `depends_on` in
each file's front-matter rather than relying on this list.

## Open questions

**Q1. Package layout: `cli/pyproject.toml` alone, a uv workspace, or a root
manifest?**
*Recommendation: `cli/pyproject.toml` alone.* A root manifest would sit next
to the unmanaged `requirements.txt` and imply the repo is a Python project,
which it is not: it is terraform, Ansible and HCL with one Python tool in
it. A uv workspace buys nothing with a single member. Gates run from the
root by pointing uv at `cli/`.

**Q2. How does a developer install it: `uv tool install --editable ./cli`
or `uv run` every time?**
*Recommendation: `uv tool install --editable ./cli`.* It puts `localstack`
on PATH, and editable means a `git pull` updates it with no reinstall. It
also matches how the dev container installs its own tools
(`.devcontainer/Dockerfile:21-24`). Document the `uv run` form too, since
that is what the gates and a fresh worktree use.

**Q3. Should pytest be a pre-commit hook, or only a `just test` recipe?**
*Recommendation: a pre-commit hook, scoped to `^cli/`.* The loop's only
gate is `just pre_commit` (`.loop/config.json:2-4`), so a suite outside it
never runs in the loop. The alternative is adding `just test` to the config's
gate list, which is operator config and out of scope here. Keep the
`cli/justfile` recipe as well for the fast local loop.

**Q4. Repoint `python.pythonPath` in `.devcontainer/devcontainer.json:31`?**
*Recommendation: yes.* It currently names `/home/vscode/workspace/.venv`,
which does not exist, so the editor resolves nothing today and would not
resolve typer either. Repointing it at `cli/.venv/bin/python` is one line.
Skip it if the operator would rather keep devcontainer changes out of this
ticket, and accept that Pylance cannot see the new package.

**Q5. Where do cluster addresses come from: env vars or a config file?**
*Recommendation: env vars.* `VAULT_ADDR`, `NOMAD_ADDR` and
`CONSUL_HTTP_ADDR` are already set in every dev shell from
`.devcontainer/.env` (`devcontainer.json:37-40`, `.env.example:2-11`), and
the `vault`, `nomad` and `consul` CLIs read those exact names, so the new
tool agrees with the tools beside it instead of inventing a second source
of truth (one place that defines a value, so nothing can disagree with it).
A config file would need seeding, documenting and keeping in sync. This
answer binds D2 to D5, so settle it here. Where D2 caches a brokered token
is a separate question and stays open for D2.

**Q6. Does D1 ship `config.py`, or does D2?**
*Recommendation: ship it in D1.* It is about 20 lines, D2 to D5 all need
it, and it gives the new pytest gate something to check beyond `--version`.
Defer it only if the operator wants D1 to be packaging and gates with no
application code at all, in which case D2 inherits Q5's answer as a written
requirement.

**Q7. Distribution name `localstack-cli`, given PyPI already has a package
by that name?**
*Recommendation: `localstack-cli`.* The package is never published, so the
name only has to be unique on the developer's machine. The clash bites only
someone who also installs AWS LocalStack, and the entrypoint name is the
operator's decision either way. Note it in the docs.

**Q8. Ruff rule selection: defaults or an explicit select?**
*Recommendation: defaults (`E`, `F`) plus `I` for import order.* A fresh
package with no legacy code can tighten later at low cost, and a noisy
first gate is a gate people learn to skip.

**Q9. Run mypy in strict mode?**
*Recommendation: yes, `strict = true`.* It is free on a package with two
modules and expensive to retrofit once D2 to D5 have added HTTP clients and
a TUI. If typer or textual stubs make strict mode painful in a later
ticket, narrow it there with evidence rather than starting loose.
