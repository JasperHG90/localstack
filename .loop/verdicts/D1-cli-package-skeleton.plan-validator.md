---
verdict: pass-with-required-fixes
plan: b69284fe3eef1a1efb4a76895f17e4f3247a2715ab0b180420d097bfccc0b5dd
---

# Plan review: D1-cli-package-skeleton (pass `plan-validator`)

## Briefing gap, stated loudly

The briefing did NOT hand me a plan fingerprint. It named the repo root, the
plan path, the slug, the pass id and the verdict path, and then told me to
"carry the plan-content fingerprint your contract requires". I did not invent
one: I derived it from the harness's own definition at
`skills/create-ticket/SKILL.md:188-189` ("the sha256 of
`.loop/plans/<slug>.md`") and computed
`sha256(.loop/plans/D1-cli-package-skeleton.md)` =
`b69284fe3eef1a1efb4a76895f17e4f3247a2715ab0b180420d097bfccc0b5dd`.

This is safe here only because the verdict is NOT a pass. Per
`skills/create-ticket/SKILL.md:204-206`, a `pass-with-required-fixes` does not
authorize `PLANNING -> READY`; the plan must be edited, which changes the
sha256 and stales this verdict anyway. The dispatcher should pass the
fingerprint explicitly on the re-review batch.

## Premise verdict

**PARTIALLY SOUND.** The plan's picture of the repo is accurate to an unusual
degree: every `path:line` I opened resolved to what the plan claims, and the
riskiest structural claim (pre-commit hooks scoped to a subdirectory package)
holds under an empirical probe. Two claims about how the chosen tooling
behaves do not survive execution, and both sit on the ticket's two headline
deliverables: the `localstack` console script and its `--version`.

## Per assumption

### P1. No Python packaging exists in the tracked tree today. HOLDS

`git ls-files | grep -Ei 'pyproject|setup\.py|uv\.lock|requirements'` returns
only `bootstrap/requirements.yml` and `requirements.txt`. `git ls-files
'*.py'` returns exactly one file,
`.loop/evals/B1-bifrost-native-auth-and-virtual-keys.scorer.py`. `.claude` is
gitignored (`.gitignore:19`) and `git ls-files .claude` returns 0 files, so
the plan's "the only `.py` files are under `.claude/` (untracked) and
`.loop/evals/`" is exactly right. `requirements.txt:1-5` lists the five
packages named at plan `:40-41`, and its only mention in tracked, non-`.loop`
content is the code sample at `docs/nats-postgres-cdc-bridge.md:199`, as
claimed. Nothing installs it.

### P2. Python pre-commit coverage is two hooks; no ruff, mypy or pytest. HOLDS

`.pre-commit-config.yaml:7` is `check-ast`, `:11` is `debug-statements`,
exactly as cited. No `ruff`, `mypy` or `pytest` string appears in
`.pre-commit-config.yaml`, `justfile` or `AGENTS.md`. The local-hook block is
`:14-33` with `terraform-validate` at `:28-33` shelling out to
`scripts/tf_validate.sh` (which exists and reads as described). `:1` is
`exclude: '^\.(claude|loop)/'`, so a new `cli/` tree is in scope for
`end-of-file-fixer` (`:13`) and the rest, as the plan says.

### P3. Every cited anchor resolves. HOLDS

Spot-checked all of them, not a sample:

- `justfile:1` `set shell`, `:3-7` aliases, `:10-11` format, `:14-15` setup,
  `:18-19` `pre-commit run --all-files`, `:22-23` unseal, `:30-32`
  `worktree_setup path`. All correct.
- `.loop/config.json:2-4` gates `["just pre_commit"]`, `:6` `require_eval`
  true. Correct.
- `.devcontainer/Dockerfile:3` `RUFF_CACHE_DIR`, `:7` `uv==0.11.16`, `:21`
  `uv tool install pre-commit`, `:21-24` the tool-install pattern. Correct.
- `.devcontainer/devcontainer.json:31` `python.pythonPath` =
  `/home/vscode/workspace/.venv/bin/python`; that path does not exist.
  `:37-40` `runArgs --env-file .devcontainer/.env`. Correct.
- `.devcontainer/.env.example:2-11` covers `NOMAD_TOKEN`, `NOMAD_ADDR`,
  `CONSUL_HTTP_TOKEN`, `CONSUL_HTTP_ADDR`, `VAULT_TOKEN`, `VAULT_ADDR`.
  Correct.
- `AGENTS.md:70` is the `END aim: guidelines` marker (so `:71` down is
  editable, as claimed), `:88-106` are the command blocks, `:102-106` is the
  migrations block, `:129` the per-directory-justfile convention, `:134`
  Python 3.12. All correct.
- `README.md:21-25` is the three-row layout table. Correct.
- `deployments/infrastructure/justfile:1-5` is `set shell` then three
  aliases. Correct.
- `.python-version` is `3.12`. `.github/workflows/` holds exactly
  `claude-ollama.yaml` and `hermes-interactive.yaml`. Correct.

`prek` is absent from PATH and `pre-commit` is present
(`/home/vscode/.local/bin/pre-commit`), and `uv --version` reports exactly
`0.11.16`. Both as claimed at plan `:67-71`.

### P4. `.gitignore:3` does not swallow `cli/pyproject.toml` or `cli/uv.lock`. HOLDS

`git check-ignore -v cli/.venv cli/pyproject.toml cli/uv.lock
cli/src/localstack_cli/main.py cli/tests/test_main.py cli/justfile` reports
one match only: `.gitignore:3:.venv    cli/.venv`. Every other path is
trackable. The plan's "no `.gitignore` change is needed" is right. Note in
passing that `.gitignore:1` (`tmp`) and `:4` (`.cache`) are also bare, so a
`cli/tmp` or `cli/.cache` would be ignored too; neither is on the plan's code
surface.

### P5. A `repo: local` hook scoped `files: '^cli/'` runs under the repo gate and skips elsewhere. HOLDS

Probed empirically in a throwaway git repo under the scratchpad (never in
this tree). Two local hooks, one `pass_filenames: false` and one with
filenames, both `files: '^cli/'`:

```
--- pre-commit run --all-files ---
scoped pass_filenames false..............................Passed
scoped with filenames....................................Passed
--- pre-commit run --files other/thing.hcl ---
scoped pass_filenames false..........(no files to check)Skipped
scoped with filenames................(no files to check)Skipped
```

So the plan's scoping design works, plan `:261-262`'s cost argument holds,
and eval row 5 (`.loop/evals/D1-cli-package-skeleton.md:28`, "the three new
hooks report Skipped rather than running") is a satisfiable row rather than a
wish. This was the briefing's sharpest question and the answer is yes:
`pre-commit` picks up subdirectory-scoped Python hooks, and the root
`justfile:18-19` recipe needs no change to reach them.

### P6. uv can be pointed at the `cli/` project from the repo root. HOLDS, with a trap the plan half-flags

`uv run --help` on 0.11.16 confirms both flags exist, and they are NOT
interchangeable:

- `--directory <DIR>`: "Change to the given directory prior to running the
  command".
- `--project <DIR>`: "Discover a project in the given directory".

Probed: `uv run --project cli python -c "print(os.getcwd())"` prints the
repo root; `uv run --directory cli ...` prints `<root>/cli`. Pre-commit
passes filenames relative to the repo root, so a filename-passing hook built
on `--directory cli` would look for `cli/cli/src/...` and fail. The plan
tells the implementer to verify the flag (`:216-220`), which is the right
instinct, but it lists ruff (`:211-212`) without a `pass_filenames` setting
while giving mypy and pytest `pass_filenames: false`. See RF3.

### P7. `[project.scripts]` gives a working `localstack` and `importlib.metadata.version` resolves. BREAKS as the plan specifies it

This is the finding that matters. The plan's code surface for
`cli/pyproject.toml` (`:161-166`) enumerates `[project]`,
`[project.scripts]`, `[tool.pytest.ini_options]`, `[tool.ruff]` and
`[tool.mypy]`. There is no `[build-system]` and no `[tool.uv] package =
true`. Without one, uv treats the directory as a non-packaged project: it
does not install the project into the venv, so no console script is created
and no distribution metadata exists.

Probed with exactly the plan's table set, minus a build system:

```
$ uv run --project cli localstack
error: Failed to spawn: `localstack`
  Caused by: No such file or directory (os error 2)

$ uv run --project cli python -c \
    "from importlib.metadata import version; print(version('localstack-cli'))"
importlib.metadata.PackageNotFoundError: No package metadata was found for
localstack-cli
```

Adding `[build-system] requires = ["hatchling"]` to the same file makes both
work and the src layout resolve (`uv run --project cli localstack` prints the
version). So the plan's Requirement 2 (console script), Requirement 13
(`--version` reads distribution metadata), the `test_main.py` version test
(`:224-227`) and eval rows 1 and 7
(`.loop/evals/D1-cli-package-skeleton.md:24,30`) all rest on a table the plan
never names. It is a one-table fix, not a design flaw, and `uv init --package
cli` emits it, but the plan must say so: this is the repo's first Python
packaging and the layout decision binds D2 to D6.

### P8. A typer app with a `--version` callback and no subcommands is viable. HOLDS

Worth checking, because typer has a real failure mode here. Probed:

- `typer.Typer()` with `@app.callback()` carrying an eager `--version`
  option and zero commands: `--version` prints and exits 0, `--help` exits 0.
- `typer.Typer()` with neither a callback nor a command: `RuntimeError: Could
  not get a command for this Typer instance`.

The plan's shape (`:169-172`, `app = typer.Typer()` plus a `--version`
callback) lands on the working side of that line. The "no empty typer groups"
stance (`:95-97`) is therefore buildable, not just principled. Bare
`localstack` with no args prints "Missing command", which is a UX note, not a
defect.

### P9. The `--help` test can assert the program is named `localstack`. BREAKS

Plan `:228` specifies "`--help` exits 0 and names the `localstack` program",
and `:226` says to use `typer.testing.CliRunner`. Probed on typer 0.27:

```
CliRunner().invoke(app, ["--help"])          ->  "Usage: root [OPTIONS] ..."
CliRunner().invoke(app, ["--help"], prog_name="localstack")
                                             ->  "Usage: localstack [OPTIONS] ..."
```

CliRunner derives the program name from the invocation, not from
`[project.scripts]`. So the test as written either fails on `root`, or the
implementer passes `prog_name="localstack"` and the assertion checks a string
the test itself supplied. That second outcome is precisely the defect the
eval marker exists to catch
(`.loop/evals/D1-cli-package-skeleton.md:10-16`, "a weak marker passes
against an empty package"). The real proof of the entrypoint name is the
installed run, which the plan already has at `:237-240` and the eval has at
row 1. See RF2.

### P10. "No empty typer groups" does not conflict with D2 to D6. HOLDS

Every downstream plan defers to D1 and registers its own surface rather than
expecting a scaffold:

- `.loop/plans/D2-cli-login-broker-tokens.md:379` "D1's CLI entry module,
  register the four subcommands. One line each"; `:328-330` treats the
  package root as D1's to set.
- `.loop/plans/D3-cli-read-commands.md:275` "The CLI entrypoint D1 created:
  modified. Register the three groups".
- `.loop/plans/D4-cli-cluster-tui.md:225-226`, `:346` register `status`
  against D1's structure.
- `.loop/plans/D5-cli-breakglass.md:207` "register it with whatever
  command-registration mechanism D1 established; do not invent one".
- `.loop/plans/D6-cli-deps-and-shims.md:139` "layout owned by
  D1-cli-package-skeleton".

A module-level `app = typer.Typer()` is all any of them need, and the plan
provides it. What D2 to D5 DO need and the plan supplies is a settled package
root (`cli/src/localstack_cli/`, matching D2's assumption at `:330`) and a
marker name (`cluster`, which D3 `:500-501` explicitly asks D1 to pick). Both
are settled here. This assumption is not merely non-conflicting, it is the
plan doing D2 to D6 a favor.

### P11. `just pre_commit` is the loop's only gate. HOLDS

`.loop/config.json:2-4`. The plan's Q3 conclusion (pytest as a hook, because
a suite outside `just pre_commit` never runs in the loop) follows from it,
and the eval's row 4 (`:27`) says the same. Sound.

### P12. The appended command-surface section did not widen scope. HOLDS, with a small gap

The block at plan `:371-377` matches `ROADMAP.md:126-132` line for line
(modulo `vault grants <job>` vs `vault grants`, and D6's row order). It adds
no deliverable, and `:379` closes with "Build the entrypoint and the gates.
Add no groups." So the answer to the briefing's question is no, scope did not
silently widen.

The gap it exposes: the plan's non-goals (`:92-107`) and its front-matter
summary enumerate D2 to D5 and never mention D6's `deps
[--with-shims|--remove-shims]`. D6 depends on D1
(`.loop/plans/D6-cli-deps-and-shims.md:3`) and is roadmap item 6
(`ROADMAP.md:24`). The eval's scaffolding guardrail grep
(`.loop/evals/D1-cli-package-skeleton.md:34`) covers
`login|logout|whoami|breakglass|textual|vault|nomad|consul` but not `deps` or
`shims`. So `deps` is the one command in the settled surface that neither the
non-goals nor the guardrail row would catch. See RF4.

### P13. Cluster addresses are already in the process env. HOLDS

`VAULT_ADDR`, `NOMAD_ADDR`, `CONSUL_HTTP_ADDR`, `VAULT_TOKEN` and
`NOMAD_TOKEN` are all set in this shell, fed per
`.devcontainer/devcontainer.json:37-40` from `.devcontainer/.env` (gitignored
at `.gitignore:2`, shape at `.env.example:2-11`). Q5's recommendation stands,
and it survives `N4-netsec-edge-only-service-access` (roadmap item 4,
`ROADMAP.md:22`, which changes the addresses) precisely because the env var
is the indirection. Requirement 8's `monkeypatch` rule is not optional
housekeeping given these are live in every dev shell: a test reading the real
environment would pass here by accident.

### P14. The eval marker has rows that can fail. HOLDS

The briefing's worry is the right one for a skeleton ticket, and the marker
answers it. Rows at `.loop/evals/D1-cli-package-skeleton.md:25-27` each
introduce a real violation (unused import, type error, failing test), require
the hook to go RED, then revert. Row `:28` requires Skipped on a non-Python
change, which P5 proves is observable. Row `:24` runs the console script
rather than checking that files exist. Row `:33` is a `git diff --stat` scope
guardrail. The marker is signed at `:37` (`signed-off-by: JasperHG90
2026-07-31`), so plan `:250-253` ("This ticket does not author it; that step
needs operator sign-off") is now stale in a harmless direction: the sign-off
already happened. No fix required, but the implementer should read the marker
as authoritative rather than as pending.

Row `:29` cites `deployments/infrastructure/services.tf:290` for the
gitignored SSH key read; I confirmed that line is the
`private_key = file("${path.root}/../../.ssh/id_rsa")` in the `remote-exec`
provisioner. The `worktree_setup`-first ordering it demands is real.

### P15. `uv run` can build the environment on first use. HOLDS

Network resolution works from this container: `uv run --no-project --with
typer python -c "import typer"` installed 7 packages in 503ms and reported
typer 0.27.0. So the plan's fresh-worktree check (`:242-248`) is runnable
rather than hypothetical, and its first-run-cost risk (`:263-267`) is
correctly scoped as slowness, not impossibility.

### P16. `just pre_commit` is green on today's tree. UNCERTAIN

Requirement 12 says the gate "stays green", which presumes a green baseline I
did not establish. I deliberately did not run it: `end-of-file-fixer`
(`.pre-commit-config.yaml:13`) and `nomad-fmt` (`:16-21`) rewrite files, and
I am read-only to this tree. The working tree also carries uncommitted
changes to `aim.lock.toml` and `aim.toml`. If the baseline is red, the
implementer inherits it under `.claude/rules/pre-existing-issues.md` and
should say so rather than absorb it into this ticket. Not a plan defect,
but not a verified premise either.

## Most dangerous assumption

**P7, the missing `[build-system]`.** Every other finding is a wording fix.
This one silently produces a `cli/` tree that looks complete, passes ruff and
mypy, and has no `localstack` on PATH and no version metadata, failing the
ticket's two headline requirements (2 and 13) at the last step. It is also the
assumption most likely to be waved through, because `uv init --package`
happens to add the table and a hand-written `pyproject.toml` following the
plan's own section list does not.

## Required fixes

**RF1 (blocking). Name the build system in the code surface.** Amend plan
`:161-166` so `cli/pyproject.toml` includes a `[build-system]` table (state
the backend, for example hatchling, or state that the file is generated by
`uv init --package cli`). Evidence: without it, `uv run --project cli
localstack` fails with "Failed to spawn: `localstack`" and
`importlib.metadata.version("localstack-cli")` raises `PackageNotFoundError`
(probed on uv 0.11.16). This is what makes Requirement 2 (`:113-114`),
Requirement 13 (`:150-152`) and eval rows 1 and 7 achievable.

**RF2 (blocking). Rewrite the `--help` test at `:228`.** As specified it
either fails (`CliRunner` prints `Usage: root`) or is vacuous (the assertion
checks the `prog_name` the test passed in). Replace with something the app
actually owns, for example: `--help` exits 0 and lists the `--version`
option. Leave the proof that the program is named `localstack` where it
belongs, in the installed run at `:237-240` and eval row 1.

**RF3 (blocking). Settle the uv flag and `pass_filenames` for the ruff hook
at `:211-212`.** State `uv run --project cli` (keeps the repo root as cwd, so
pre-commit's root-relative filenames resolve) or set `pass_filenames: false`
on ruff as the plan already does for mypy and pytest. `--directory cli`
changes the working directory and breaks any filename-passing hook. The plan
already tells the implementer to verify (`:216-220`); make the answer part of
the plan so it is not re-derived under time pressure.

**RF4 (non-blocking, do it while you are in the file). Add D6 to the
non-goals** at `:92-107`: no `deps`, no PATH shims, no version reading from
`group_vars`. That is `D6-cli-deps-and-shims`, which depends on D1
(`.loop/plans/D6-cli-deps-and-shims.md:3`) and is named in the plan's own
appended surface at `:376`. Today it is the one command in the settled
surface that neither the non-goals nor the eval's scaffolding guardrail
(`.loop/evals/D1-cli-package-skeleton.md:34`) would catch.

## Contract hygiene

All 11 contract sections from `skills/create-ticket/SKILL.md:98-143` are
present and non-empty. Gates are discovered, not assumed: `just pre_commit`
traced to `.loop/config.json:2-4` and `justfile:18-19`, with the honest note
that no Python gate exists to discover yet, which is the ticket. Non-goals
are explicit (RF4 is one omission, not a missing section). Both named tests
(`cli/tests/test_main.py`, `cli/tests/test_config.py`) have homes in the code
surface at `:177-178`. Nine open questions each carry a recommendation, and
the load-bearing ones (Q1 layout, Q5 config source) are correctly flagged as
binding D2 to D5 rather than left for the implementer.

One observation, no fix required: the plan restates `.claude/rules/*` content
inline because loop worktrees cannot see `.claude` (`:86-90`). I confirmed
`.claude` is gitignored at `.gitignore:19` with 0 tracked files, so the
reasoning is right. The specific witness it cites
(`.loop/worktrees/F2-foundation-vault-oidc-provider/`) no longer exists,
since `.loop/worktrees/` is empty today. The conclusion stands on the
gitignore evidence alone.

## Re-review note

Applying RF1 to RF4 changes the plan file, so this verdict's `plan:` hash
goes stale by design. Recompute
`sha256(.loop/plans/D1-cli-package-skeleton.md)` and re-dispatch this pass
bound to the new hash, and pass the fingerprint in the briefing this time.
