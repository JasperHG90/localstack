eval: D1-cli-package-skeleton

**Definition of Done:** a `cli/` src-layout package with its own
`cli/pyproject.toml` and committed `cli/uv.lock`, exposing a `localstack`
console script that runs, plus the repo's first Python gates (ruff, mypy,
pytest) wired into `.pre-commit-config.yaml` as `repo: local` hooks scoped to
`^cli/`. `just pre_commit` stays green from the repo root and now actually
exercises the new hooks. No login, no commands, no TUI, no breakglass, no
`deps`.

**The trap this marker exists to catch.** D1's success looks like "nothing
visible happened", so a weak marker passes against an empty package with
gates that never fire. Rows 3, 4 and 5 therefore prove each gate goes RED on
bad input, not merely that it is configured. A gate that cannot fail is the
defect this repo has shipped repeatedly: an eval row once scored secrets with
`detect-private-key`, a hook that matches a fixed list of PEM headers and
cannot match a Vault token.

**Rows 3-5 mutate the tree deliberately.** Introduce the violation, observe
red, revert it. The revert is part of the row; leaving the violation behind
fails row 10.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| The console script exists and runs | `cd cli && uv run localstack --version` and `uv run localstack --help` | Both exit 0. `--version` prints a version; `--help` lists the `--version` option. This is the only place the entrypoint's name is proved: it runs the installed console script, so it fails unless `[project.scripts]` AND `[build-system]` are both present. Without a build system uv leaves the project uninstalled and this dies with "Failed to spawn: `localstack`". A `CliRunner` test cannot prove this, since it takes the program name from the invocation | deterministic check (both commands exit 0 with non-empty output) | 100% |
| **The ruff hook goes RED on a real violation** | Add an unused import to a file under `cli/src/`, run `just pre_commit`, then revert | The ruff hook FAILS while the violation is present and passes after the revert. A hook that stays green through a deliberate violation is not a gate | deterministic check (hook red with violation, green after revert) | 100% |
| **The mypy hook goes RED on a real type error** | Add a call passing `int` where `str` is annotated, run `just pre_commit`, then revert | The mypy hook FAILS while the error is present and passes after the revert | deterministic check (hook red with error, green after revert) | 100% |
| **The pytest hook goes RED on a failing test** | Add a test asserting something false, run `just pre_commit`, then revert | The pytest hook FAILS while the test is failing and passes after the revert. **This row also settles whether pytest runs in the loop at all**: `.loop/config.json` lists `just pre_commit` as the only gate, so a suite outside pre-commit never runs during a loop iteration | deterministic check (hook red with failing test, green after revert) | 100% |
| Gates are scoped and do not tax unrelated commits | Read `.pre-commit-config.yaml`; run `just pre_commit` on a tree whose only change is an `.hcl` or `.tf` file | Each new hook carries `files: '^cli/'`, and on a non-Python change the three new hooks report Skipped rather than running. Matches the existing local-hook style at `.pre-commit-config.yaml:14-33` (`repo: local`, `language: system`) | deterministic check (files scope present; hooks skip on non-Python change) | 100% |
| The whole gate is green on the finished tree | `just worktree_setup <path>` then `just pre_commit` | All hooks Passed. The worktree step comes first or `terraform-validate` dies on the gitignored `.ssh/id_rsa` read at `deployments/infrastructure/services.tf:290` | deterministic check (`just pre_commit` all Passed) | 100% |
| **Dependencies are declared, not just installed** | Read `cli/pyproject.toml`; confirm `cli/uv.lock` is committed | `typer` under runtime deps; `pytest`, `mypy`, `ruff` under dev deps; `requires-python = ">=3.12"`; a `[build-system]` table naming a backend. `cli/uv.lock` is tracked by git. Installing into an environment without recording the dependency is what `uv add` exists to prevent, and a missing `[build-system]` is what turns row 1 red | deterministic check (deps and build-system present in pyproject; uv.lock tracked) | 100% |
| **The live-cluster marker is registered now, before anything needs it** | Read `cli/pyproject.toml`; run `cd cli && uv run pytest` | A `cluster` marker is declared and excluded from the default run via `addopts`. The default `uv run pytest` completes without contacting Vault, Nomad or Consul. D1 adds no such test; it establishes the default so D2-D5 inherit a fast offline run rather than each inventing one | deterministic check (marker declared, excluded in addopts, default run offline) | 100% |
| Tests do not read the developer's real environment | Read `cli/tests/`; run the suite with `VAULT_ADDR` set to a junk value | Config tests use `monkeypatch` for env vars and pass regardless of the ambient `VAULT_ADDR`. A test that reads the real environment passes or fails by accident | deterministic check (suite green with junk VAULT_ADDR set) | 100% |
| **Guardrail: scope holds** | `git diff --stat` over the branch | Changes confined to `cli/**` and `.pre-commit-config.yaml` (plus the justfile if a recipe was added). NO root `pyproject.toml`, no uv workspace, no edit to `.loop/config.json`, no change to existing terraform/Nomad/Ansible hooks, no CI workflow. The plan makes each of these an explicit non-goal | deterministic check (diff confined to the allowed paths) | 100% |
| **Guardrail: no feature scaffolding from D2-D6** | `grep -rniE "login|logout|whoami|breakglass|textual|vault|nomad|consul|deps|shims" cli/src/` | No login flow, no token handling, no HTTP client, no Textual import, no `deps` command or PATH shim, and no empty typer sub-groups "ready for D3". An empty group is a guess about a later ticket's shape, and the plan forbids it. Bare mentions in a docstring or a config variable name are acceptable; an implementation is not | model + rubric (adversarial review agent) | 5/5 |
| One pin, not two | Read `cli/pyproject.toml`, `cli/uv.lock` and `.pre-commit-config.yaml` | Tool versions are pinned once, by the dev dependencies plus the lock. The new hooks do NOT additionally pin ruff or mypy through an upstream pre-commit `rev`, which would create two pins that drift apart | deterministic check (no upstream rev pin for ruff/mypy) | 100% |

signed-off-by: JasperHG90 2026-07-31
