---
verdict: pass-with-required-fixes
plan: cc1edcb231d26fef944d0876e2695a423dddc080cec4a292936dc33214e9b3d8
---

# Plan review: D1-cli-package-skeleton (pass `plan-validator`, re-review)

Fingerprint confirmed on disk: `sha256(.loop/plans/D1-cli-package-skeleton.md)`
= `cc1edcb231d26fef944d0876e2695a423dddc080cec4a292936dc33214e9b3d8`, matching
the briefing.

## Premise verdict

**PARTIALLY SOUND.** All four required fixes from the previous pass are applied
and each survives execution, not just reading. The packaging premise, the D2 to
D6 compatibility premise and the eval's falsifiability all hold under probe.
Two defects remain, both inside the hook wiring the last pass told this plan to
settle. One makes the repo gate red on the tree the plan itself mandates. The
other silently discards the `strict = true` decision that Q9 argues is the whole
point of settling typing in D1 rather than D5.

All probes ran in throwaway trees under the scratchpad. The only command I ran
against this repo was `pre-commit run <hook>` for the seven non-mutating hooks,
plus read-only greps. I wrote nothing here but this verdict.

## The four claimed fixes: verified by execution

### F1. `[build-system]` in `cli/pyproject.toml`. VERIFIED

I built the plan's stated manifest verbatim in a scratch tree: hatchling
backend, `name = "localstack-cli"`, `src/localstack_cli/`,
`[project.scripts] localstack = "localstack_cli.main:main"`, the pytest
`cluster` marker with `addopts`, `[tool.ruff.lint]`, `[tool.mypy]`.

```
$ uv run --project cli localstack --version
0.1.0
$ uv run --project cli localstack --help
 Usage: localstack [OPTIONS] COMMAND [ARGS]...
 --version   Show the version and exit.
```

Hatchling auto-detects `src/localstack_cli` from the dashed distribution name,
so plan `:168-175` needs no extra `[tool.hatch]` stanza. Counterfactual, same
tree with only the `[build-system]` table deleted:

```
$ uv run --project cli localstack --version
error: Failed to spawn: `localstack`
  Caused by: No such file or directory (os error 2)
$ uv run --project cli python -c "from importlib.metadata import version; print(version('localstack-cli'))"
importlib.metadata.PackageNotFoundError: No package metadata was found for localstack-cli
```

Requirement 2 (`:117-121`) and Requirement 13 (`:157-159`) are now achievable,
and the plan's claim at `:176-181` that both failures were reproduced is true.
Eval row 1 (`.loop/evals/D1-cli-package-skeleton.md:25`) also passes in its own
form, `cd cli && uv run localstack --version`, and Q2's
`uv tool install --editable ./cli` puts `localstack` on PATH and runs from `/`.

One inaccuracy, minor. Plan `:173-175` says to start from `uv init --package
cli`, "which emits both the `[build-system]` table and the src layout". It emits
a table, but on uv 0.11.16 that table is `uv_build`, not the hatchling the plan
names three lines earlier:

```
[build-system]
requires = ["uv_build>=0.11.16,<0.12.0"]
build-backend = "uv_build"
```

I confirmed `uv_build` also works with this exact layout and name, so the choice
is harmless and eval row 7 (`:31`, "a `[build-system]` table naming a backend")
accepts either. See RF3.

### F2. The `--help` test drops the program name. VERIFIED, and non-vacuous

`typer.testing.CliRunner` reports `Usage: root [OPTIONS] COMMAND [ARGS]...`,
exactly as plan `:252-257` claims. The replacement assertion is not vacuous:
with `--version` present, `assert "--version" in result.output` passes; with the
option removed from the callback and everything else identical, it fails.

```
>       assert "--version" in r.output
E       AssertionError: assert '--version' in '... Usage: root [OPTIONS] ...'
1 failed
```

So the assertion is bound to something the app owns, and the entrypoint's real
name stays proved where it belongs, in the installed run at `:266-269` and eval
row 1.

### F3. `--project` over `--directory`. VERIFIED for ruff, over-generalized for mypy

Both forms run, and they differ exactly as `:226-235` says:

```
$ uv run --project cli   ruff check cli/src/localstack_cli/main.py    ->  All checks passed! (exit 0)
$ uv run --directory cli ruff check cli/src/localstack_cli/main.py    ->  E902 No such file or directory (exit 1)
$ uv run --project cli   python -c "...getcwd()"   ->  <root>
$ uv run --directory cli python -c "...getcwd()"   ->  <root>/cli
```

The plan's supporting claim at `:239-241` also holds: ruff walks up from each
file and resolves `cli/pyproject.toml`. `ruff check --show-settings` prints
`Settings path: <root>/cli/pyproject.toml`, and an `I001` import-order violation
fires, which is a rule the plan's Q8 turns on and ruff's defaults do not carry.
Config discovery from the repo root is real, not assumed.

Where the fix over-reaches is `:226` ("Every entry runs as `uv run --project
cli ...`"). The reason given is filename passing, which applies only to ruff.
mypy is `pass_filenames: false`, and mypy does not walk up. See RF2.

### F4. D6 non-goal and the eval guardrail. VERIFIED

Plan `:100-102` now reads "No `deps` command, no PATH shims, no reading tool
versions from `group_vars`. That is D6", citing
`.loop/plans/D6-cli-deps-and-shims.md:3`, which I confirmed is
`depends_on = ["D1-cli-package-skeleton"]`. The eval's guardrail grep at
`.loop/evals/D1-cli-package-skeleton.md:35` is now
`grep -rniE "login|logout|whoami|breakglass|textual|vault|nomad|consul|deps|shims" cli/src/`.
Both halves of RF4 are in.

## Per assumption

### P1. The layout serves D2 to D6, and D6's reading of D1 agrees. HOLDS

D6 `:275-283` says D1 "bans typer sub-groups and forbids scaffolding a
`commands/` package for D3
(`.loop/plans/D1-cli-package-skeleton.md:95-97`), so **D6 creates no
`commands/` package and no sub-group.** `deps` is a leaf command registered
straight onto D1's existing `app` with `@app.command()`." That cross-plan anchor
still resolves after this edit: D1 `:95-97` is the "no read-only commands and no
typer sub-groups ... do not scaffold empty groups" paragraph. D6 `:282-283`
reads the ban correctly as a ban on empty groups guessing at D3's shape.

More important, the shape works. Typer collapses a single-command app into a
bare command when there is no callback, which would have broken `localstack
deps`. D1's `--version` callback prevents that. Probed against D1's app object:

```
['--version']            exit 0 | 0.1.0
['deps']                 exit 0 | deps ok shims=False
['deps', '--with-shims'] exit 0 | deps ok shims=True
['service', 'show']      exit 0 | service show      # add_typer sub-group, D3's form
```

So D6's leaf registration and D3's three groups both land on the app D1 ships.
The plan's `:404-410` surface block matches `ROADMAP.md:124-130` and adds no
deliverable.

### P2. Every cited anchor resolves. HOLDS

Re-checked all of them against this tree, not a sample:
`.pre-commit-config.yaml:1` (`exclude: '^\.(claude|loop)/'`), `:7` check-ast,
`:11` debug-statements, `:13` end-of-file-fixer, `:14-33` the local block ending
exactly at `pass_filenames: false` on `:33`, `:16-21` nomad-fmt, `:28-33`
terraform-validate. `justfile:1,10-11,14-15,18-19,30-32`.
`.loop/config.json:2-4` gates, `:6` `require_eval`.
`.devcontainer/Dockerfile:3,7,21-24`. `.devcontainer/devcontainer.json:31,37-40`.
`AGENTS.md:70` (the `END aim: guidelines` marker), `:102-106`, `:129`, `:134`.
`README.md:21-25`. `deployments/infrastructure/justfile:1-5`. `.gitignore:3,19`.
`.python-version` = 3.12. `requirements.txt` holds the five listed packages and
its only tracked mention outside `.cache/` is
`docs/nats-postgres-cdc-bridge.md:199`. `.github/workflows/` holds exactly the
two Claude bots. `git check-ignore -v` on `cli/.venv cli/pyproject.toml
cli/uv.lock cli/justfile cli/src/localstack_cli/main.py` matches one path only,
`.gitignore:3` against `cli/.venv`.

### P3. The ruff hook as specified keeps `just pre_commit` green. BREAKS

This is the new blocking finding. Plan `:223` lists all three hooks as
"`repo: local`, `language: system`, `files: '^cli/'`", and `:237-238` tells the
implementer to "leave `pass_filenames` at its default so ruff checks only the
changed files". No `types:` filter appears anywhere, even though the plan's own
Context at `:49-51` records that the repo's local-hook pattern carries one.

pre-commit's default is `types: [file]`, so the hook receives every file under
`cli/`, and ruff lints an explicitly-passed path whatever its extension. Built
the plan's hook verbatim in a scratch repo with real pre-commit:

```
ruff (plan as written, no types filter)..................................Failed
- hook id: ruff-plan-as-written
- exit code: 1
invalid-syntax: Expected an expression
 --> cli/justfile:1:6
```

Per-file counts from the same tree: `cli/uv.lock` 891 errors, `cli/justfile` 4
errors, `cli/pyproject.toml` clean. Both offenders are files this plan mandates:
Requirement 5 (`:131-132`) says commit `cli/uv.lock`, and the code surface
`:194-196` adds `cli/justfile`. Adding `types: [python]` to the same hook turns
it green:

```
ruff (types python)......................................................Passed
```

So the plan as written makes Requirement 12 (`:155-156`) and eval row 6
(`.loop/evals/D1-cli-package-skeleton.md:30`, "All hooks Passed") unreachable.
Subticket 3 (`:317-318`) would catch it, but the plan should not hand the
implementer a spec it knows the gate rejects. See RF1.

### P4. `[tool.mypy] strict = true` takes effect under the prescribed hook. BREAKS

ruff walks up from each file and pytest walks up from its arguments, so both
find `cli/pyproject.toml` from the repo root. mypy does neither: it looks for a
config in the current directory only. Under `uv run --project cli` the working
directory is the repo root, and this repo has no root `pyproject.toml` by
design (plan Q1, `:330-336`).

```
$ uv run --project cli mypy cli/src -v | grep "Config File"
LOG:  Config File:            Default
```

Consequence, on a file only strict mode rejects:

```
$ uv run --project cli mypy cli/src cli/tests
Success: no issues found in 4 source files

$ uv run --project cli mypy --config-file cli/pyproject.toml cli/src cli/tests
cli/tests/test_untyped.py:5: error: Function is missing a return type annotation  [no-untyped-def]
cli/tests/test_untyped.py:6: error: Call to untyped function "helper" in typed context  [no-untyped-call]
Found 3 errors in 1 file (checked 4 source files)
```

Q9 (`:390-394`) argues strict is "free on a package with two modules and
expensive to retrofit once D2 to D5 have added HTTP clients and a TUI". Under
the plan's own hook form that decision is inert, and nothing reports it: the
hook still passes, and mypy still catches a plain `int`-where-`str` error, so
eval row 3 (`:27`) goes red on cue and certifies a gate that dropped half its
configuration. This is the exact silent-pass shape the eval's own preamble
(`:11-18`) warns about, one layer below where the eval looks. On the ticket that
binds five others, this is the finding that matters most. See RF2.

### P5. mypy and pytest run correctly over `cli/` from the repo root. HOLDS otherwise

`uv run --project cli mypy cli/src cli/tests` resolves the src layout
(`base_dir=<root>/cli/src`) and reads typer's types from `cli/.venv`. pytest
does find its config and honours the marker exclusion:

```
$ uv run --project cli pytest cli/tests
rootdir: <root>/cli
configfile: pyproject.toml
collected 2 items / 1 deselected / 1 selected
1 passed, 1 deselected
```

So Requirement 7 (`:138-141`) and eval row 8 (`:32`) are satisfiable exactly as
written. pytest is not affected by P4.

### P6. The eval's rows can fail. HOLDS, with one soft row

Row 1 (`:25`) fails without `[build-system]`, proved above. Rows 2 to 4
(`:26-28`) each introduce a real violation and require RED, and I confirmed the
mypy one fires. Row 5 (`:29`) is observable, since a `files: '^cli/'` hook
reports Skipped on a non-Python change. Row 6 (`:30`) is the whole gate. Row 7
(`:31`) reads the manifest. Row 10 (`:34`) is a `git diff --stat` scope
guardrail. This marker is not a rubber stamp.

The soft one is row 9 (`:33`), "run the suite with `VAULT_ADDR` set to a junk
value". A test that reads the real environment and asserts the loader echoes it
passes under junk too, so the junk-value probe alone does not catch the defect
the row names. The row's "Read `cli/tests/`" half does, and the missing-variable
tests that Requirement 8 and `:259-261` specify genuinely need
`monkeypatch.delenv`, since `VAULT_ADDR` is live in every dev shell. No fix:
the eval is operator-signed at `:38` and plan `:279-283` correctly refuses to
edit it. Recording it so the implementation reviewer does not lean on that row.

### P7. `just pre_commit` is green on today's tree. HOLDS (confirming the briefing)

The briefing's report is right. I could not run the mutating hooks, so I ran the
seven non-mutating ones directly and non-mutating equivalents for the other two:

```
check json...............................................................Passed
check python ast.....................................(no files to check)Skipped
check for merge conflicts................................................Passed
check yaml...............................................................Passed
debug statements (python)............................(no files to check)Skipped
detect private key.......................................................Passed
Terraform Format (fmt -check -recursive).................................Passed
```

`nomad fmt -check -recursive` exits 0. For `end-of-file-fixer`, every tracked
text file outside `.claude/` and `.loop/` ends in a newline; the four hits are
PNGs under `assets/logos/` and `docs/architecture/`, which the hook's
`types: [text]` excludes. `git status --porcelain` shows one modified path,
`.loop/ledger.json`, which `.pre-commit-config.yaml:1` excludes. I did not run
`terraform-validate`, since it writes `.terraform/`; the operator's own run
covers it. So Requirement 12's "stays green" rests on a real green baseline, and
the previous pass's P16 UNCERTAIN is now settled. The last pass's note about
uncommitted `aim.toml` and `aim.lock.toml` is also stale: both are clean now.

Worth noting for the implementer: `check-ast` and `debug-statements` report "no
files to check" today. After D1 lands they start running on `cli/**/*.py` for
the first time. That is not a hook change, so it stays inside the "no changes to
the existing pre-commit hooks" non-goal (`:108-109`), but it is one more reason
subticket 3's "each new hook actually ran" check should read the whole output.

### P8. Contract hygiene. HOLDS

Every section the create-ticket contract names
(`.claude/plugins/aim-ef9f6a17bd3105b7/loop-harness/skills/create-ticket/SKILL.md`)
is present and non-empty. Gates are discovered rather than assumed, traced to
`.loop/config.json:2-4` and `justfile:18-19`. Non-goals are explicit and now
cover D2 through D6. Both named tests have homes on the code surface
(`:192-193`). Nine open questions each carry a recommendation, and the two that
bind downstream tickets (Q1 layout, Q5 env vars) say so. Plan `:279-283` now
reads the eval as authoritative and signed, which is correct: the sign-off is at
`.loop/evals/D1-cli-package-skeleton.md:38`.

## Most dangerous assumption

**P4, the inert `strict = true`.** P3 is louder and self-correcting: the gate
goes red, the implementer sees it in subticket 3, and adds `types: [python]`.
P4 makes no noise at all. The mypy hook passes, the eval row that exercises
mypy still goes red on cue, and every reviewer downstream reads a green strict
gate that is not strict. D2 through D5 then write HTTP clients and a Textual TUI
under default mypy, which is precisely the retrofit cost Q9 exists to avoid.
This is the highest-leverage ticket on the roadmap and this is the way it fails
quietly.

## Required fixes

**RF1 (blocking). Give the ruff hook a `types: [python]` filter.** Amend plan
`:223` and `:237-241` so the ruff hook declares `types: [python]` alongside
`repo: local`, `language: system` and `files: '^cli/'`. Evidence: with
pre-commit's default `types: [file]`, the hook is handed `cli/uv.lock` (891
ruff errors) and `cli/justfile` (4 errors), both files this plan mandates at
`:131-132` and `:194-196`, and `just pre_commit` reports Failed. Adding
`types: [python]` turns the same hook Passed. This is also what the Context at
`:49-51` already says the repo's local-hook pattern carries.

**RF2 (blocking). Make the mypy hook name its config file.** Amend `:242` to
`uv run --project cli mypy --config-file cli/pyproject.toml cli/src cli/tests`,
and soften the absolute at `:226` so it is clear `--project` is chosen for
filename passing (which only ruff does) rather than for config discovery.
Evidence: `uv run --project cli mypy cli/src -v` logs
`Config File: Default`, and an untyped function passes clean; the same command
with `--config-file cli/pyproject.toml` reports three `no-untyped-def` and
`no-untyped-call` errors. Without this, Q9's `strict = true` (`:390-394`) never
runs, and no eval row detects it. If you prefer, `uv run --directory cli mypy
src tests` also works, since mypy passes no filenames, but pick one and write it
down.

**RF3 (non-blocking). Fix the backend wording at `:173-175`.** `uv init
--package cli` on uv 0.11.16 emits `requires = ["uv_build>=0.11.16,<0.12.0"]`
with `build-backend = "uv_build"`, not the hatchling named at `:169`. I verified
both backends build this layout and produce a working `localstack --version`, so
either is fine. Say which one ships, or say that the backend `uv init` emits is
kept as-is, so the implementer is not left reconciling two lines of the same
paragraph.

## Re-review note

Applying RF1 to RF3 changes the plan file, so this verdict's `plan:` hash goes
stale by design and the `PLANNING -> READY` gate will refuse it, which is
correct. Recompute `sha256(.loop/plans/D1-cli-package-skeleton.md)` and
re-dispatch every enabled planning pass bound to the new hash. Nothing outside
the three fixes above needs to change: the packaging premise, the layout's fit
with D2 to D6, and the eval marker are all sound.
