---
type: component
title: The localstack CLI
description: "cli/ is a typer app that logs a human in to Vault, brokers Nomad and Consul tokens from that session, and reads the cluster without writing to it. Its shape is set by three rules the tests enforce: stdout of `token` is the token alone, the api/ layer is read-only, and the HashiStack versions are read from group_vars, never copied."
tags: [cli, python, typer, textual, vault, auth, testing]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: pyproject
    resource: git:3ec5d1e:cli/pyproject.toml
  - id: main
    resource: git:3ec5d1e:cli/src/localstack_cli/main.py
  - id: broker
    resource: git:3ec5d1e:cli/src/localstack_cli/auth/broker.py
  - id: session
    resource: git:3ec5d1e:cli/src/localstack_cli/auth/session.py
  - id: shims
    resource: git:3ec5d1e:cli/src/localstack_cli/shims.py
  - id: versions
    resource: git:3ec5d1e:cli/src/localstack_cli/versions.py
  - id: token
    resource: git:3ec5d1e:cli/src/localstack_cli/commands/token.py
  - id: read-guardrails
    resource: git:3ec5d1e:cli/tests/test_read_guardrails.py
  - id: D1-cli-package-skeleton
    resource: loop:D1-cli-package-skeleton
  - id: D2-cli-login-broker-tokens
    resource: loop:D2-cli-login-broker-tokens
  - id: D3-cli-read-commands
    resource: loop:D3-cli-read-commands
  - id: D4-cli-cluster-tui
    resource: loop:D4-cli-cluster-tui
  - id: D6-cli-deps-and-shims
    resource: loop:D6-cli-deps-and-shims
  - id: D10-cli-broker-nomad-manage
    resource: loop:D10-cli-broker-nomad-manage
---

# The localstack CLI

`cli/` is the `localstack` command: one login that hands a human short-lived
Vault, Nomad and Consul tokens, plus read-only views of the cluster. What each
command does is in `docs/reference/cli-login.md`,
`docs/reference/cli-read-commands.md`, `docs/reference/cli-deps.md` and
`docs/reference/cli-breakglass.md`. This page is how the package is built.

## Package layout

`cli/src/localstack_cli/`:

- `main.py`: the root typer app. Every command is registered by name in
  `LAZY_SUBCOMMANDS` and imported only when dispatched.
- `_lazy.py`: `LazyTyperGroup`, copied verbatim from aim so it can be
  re-synced. It is formatted for aim's line length of 100, and the one mypy
  override in `pyproject.toml` exists because it types against the
  standalone `click` while typer uses a vendored fork.
- `auth/`: the credential side. `vault.py` talks to Vault's auth endpoints,
  `broker.py` reads the three creds paths, `session.py` is the cache file, and
  `vault_token_file.py` handles `~/.vault-token`, which the CLI reads but
  does not own.
- `api/`: the read side. One fetch layer per system (`vault.py`, `nomad.py`,
  `consul.py`, `haproxy.py`, `secrets.py`, `status.py`), `_http.py` and
  `errors.py` to classify failures, and pure
  functions (`health.py`, `services.py`, `grants.py`) that join the results.
- `commands/`: one typer module per command. `_common.py` loads and refreshes
  the session, `_session.py` turns a 403 into the right sentence.
- `tui/`: the Textual `monitor` panel.
- `versions.py`, `install.py`, `platforms.py`, `shims.py`: `localstack deps`.
- `status.py` and `branding.py`: the banner printed by a bare `localstack`.
- `commands/breakglass_runbook.md`: packaged into the wheel by a
  `force-include` in `pyproject.toml`.

## Why imports are lazy

The PATH shims call `localstack token <svc>` on every bare `nomad`, `consul`
or `vault`. That call must not import Textual, httpx or the read commands.
`LAZY_SUBCOMMANDS` defers each module until its command runs, and the TUI
module is imported inside the `monitor` function body. A group with one
command and no callback collapses into that command, so `main.py` asks every
group to carry an `@app.callback()` until it has two commands.

## How login brokers tokens

1. `login` authenticates with userpass, completing an MFA challenge when Vault
   returns one. It writes the session, then revokes the session it replaced.
2. `broker.py` reads `nomad/creds/deploy`, `nomad/creds/manage` and
   `consul/creds/deploy`. The field names differ per engine (`secret_id` for
   Nomad, `token` for Consul), and the table `_FIELDS` is the only place that
   mapping lives. D10 added the `manage` token because `status`, `service`
   and `monitor` need `list-jobs` and `node:read`, which `deploy` lacks.
3. `session.py` is the one cache file, and `_common.refreshed_session` runs
   before any command hands out a token, re-reading whatever is near expiry.
   Where the file is and how refresh behaves is `docs/reference/cli-login.md`.
4. `env` prints `CONSUL_TOKEN` beside `CONSUL_HTTP_TOKEN`. Its docstring says
   the Terraform recipes bridge `CONSUL_HTTP_TOKEN=${CONSUL_TOKEN}` by hand,
   but no justfile does any more (commit `0c28e71` removed the bridges). The
   second name is now only a guard against a stale value left in a shell.

When a call is denied, `broker.py` and
`cli/src/localstack_cli/commands/_session.py` name the grant and the ticket that
holds it. A 403 with a live session means the policy is missing something, so
the message says so instead of telling the user to log in again.

## Versions and shims

What `deps` installs and how the shims behave is
`docs/reference/cli-deps.md`. The internals behind it:

- `versions.py` reads `hashistack_versions` from
  `bootstrap/inventory/group_vars/all.yml`, the file the apt pin reads
  ([Ansible bootstrap](/components/bootstrap.md)), and carries no fallback
  list. `strip_revision` is the one place `X.Y.Z-1` becomes `X.Y.Z`. Its
  `walk_from` parameter exists only so a test can reach the failure branch,
  which is unreachable from inside a checkout.
- `install.py` writes only under `~/.localstack/bin`, and `shims.py` only
  under `~/.localstack/shims`. Neither writes the other's directory.
- `shims.py` renders one template for all three tools, so they cannot drift.
  The template holds the real binary as an absolute path fixed at install
  time, because resolving through `PATH` would find the shim itself.
- A shim never fails hard. If `localstack token` fails or prints nothing, it
  runs the real binary unchanged.

That last rule is why `cli/src/localstack_cli/commands/token.py` has its own
module with no shared output helper: stdout is the token and one newline, and a
failure exits non-zero with empty stdout.

## Tests

`uv run pytest` in `cli/` runs the suite. No pre-commit hook runs pytest.
`just pre_commit` from the root runs ruff, ruff-format and strict mypy over
`cli/src`, `cli/tests` and `scripts/`, and `just check` in `cli/` runs all
four.

- Tests that hit the live cluster carry the `cluster` marker, and `addopts`
  excludes them. Run them with `uv run pytest -m cluster` (`just
  test_cluster` in `cli/`).
- HTTP is mocked with respx. The TUI tests inject callables, so the app never
  knows whether data came from a cluster or a fixture.
- `tests/__snapshots__/test_monitor_tui/` holds pytest-textual-snapshot
  baselines at a fixed terminal size, built from a full capture of the live
  cluster rather than hand-written fixtures. A failing run writes
  `cli/snapshot_report.html`, which is gitignored.
- `test_read_guardrails.py` and `test_monitor_guardrails.py` turn the
  boundaries into greps and AST checks: `api/` is read-only and imports no
  renderer, holds no address, never requests a KV2 data endpoint, and there
  is no second auth path. Each first asserts that the directory it searches
  exists, because a grep over a missing path passes.
- `test_breakglass_runbook_facts.py` pins each fact in the runbook to the
  repo file that states it, including files under `bootstrap/`, so an
  inventory or Vault role edit can turn it red.

Some tests in `cli/tests/` guard the repo rather than the CLI.
`test_docs_index.py`, `test_how_to_skeleton.py`, `test_backup_coverage.py`
and `test_devcontainer_path.py` read files outside `cli/`, so a change to
`docs/`, a jobspec or the devcontainer can turn this suite red.

## Traps recorded in the ticket reflections

- A fixture more generous than production hides the bug it should catch. D4
  judged a `system` job healthy with `0 >= 0` because the test helper
  supplied a node count production did not.
- Fetching sources in line froze the whole TUI for the slowest one. Each
  source now polls on its own.
- A shadow copy of `cli/` that carries its `.venv` still imports the
  editable install. Check `localstack_cli.__file__` before trusting a
  before-and-after comparison (D7).
- `just install_cli` binds the global `localstack` to the checkout it runs
  from. Run it from the primary checkout, never a loop worktree that will be
  deleted.

## Tickets

Done: D1 skeleton and gates, D2 login and brokering, D3 read commands, D4
`monitor`, D5 `breakglass`, D6 `deps` and shims, D7 and D8 `service`
resolution through the Consul catalog, D10 brokering `nomad/creds/manage`.
Open: D9 (`service` renders one row per job) is ready, D11
(`localstack vault admin status|join|leave`, replacing the `admin_*` recipes in
the root `justfile`) is in planning.
