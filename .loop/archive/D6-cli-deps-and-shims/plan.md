---
epic = "cli"
depends_on = ["D1-cli-package-skeleton"]
priority = 44
summary = "`localstack deps` installs the HashiCorp CLIs at exactly the versions this cluster pins, reading them from the same group_vars file the Ansible pin reads, and optionally installs the PATH shims that let a bare `nomad`, `consul` or `vault` command inherit a `localstack login` session."
tags = ["cli", "tooling", "versions", "shims"]
---

# Ticket: D6-cli-deps-and-shims

## 1. Title

Install the `vault`, `nomad` and `consul` CLIs at the versions this cluster
runs, resolved from the repo's single declaration point, plus the optional
PATH shims that make a bare `nomad`, `consul` or `vault` command pick up the
session from `localstack login`.

## 2. Size / Effort

**M.** The download-and-install path is ordinary work: resolve architecture,
fetch, verify, unpack, place. The care is in three places. The versions must
come from the file that already governs the cluster rather than a second
list. The install must be idempotent, because it will be re-run. And the
shims shadow real binaries on a developer's PATH, which is a change to their
machine that has to be reversible and obvious.

## 3. Triggered by

Two findings from the 2026-07-31 design session.

**Version skew is real and silent.** The cluster runs Consul 2.0.2, Vault
2.0.3 and Nomad 2.0.4. The devcontainer currently carries Consul CLI 2.0.1 and
Nomad CLI 2.0.3. A CLI that drifts far from its server produces failures that
read like bugs in the cluster.

**`nomad` cannot inherit a session any other way.** Measured against the
installed binaries: `NOMAD_TOKEN_FILE` does not exist, `nomad login` has no
sink flag, and a child process cannot set its parent shell's environment. The
measurement went to the wire, not just to `strings`: with `NOMAD_TOKEN_FILE`
set and the file present, `nomad` sent no `X-Nomad-Token` header at all. The
PATH shim is the only mechanism that makes a bare `nomad job status` work
after `localstack login`, and D2 §12 locked it as the design. `consul` and
`vault` each looked like they had an alternative and each failed on
measurement, so all three end up shimmed. See "What the shims must do". One
caveat to carry: the measurement ran against the installed Nomad **2.0.3**,
while the pin `deps` installs is **2.0.4**. Nothing suggests 2.0.4 added one,
but the binary measured is not the binary `deps` will put on PATH. Re-check
`strings -a <pinned nomad> | grep -c NOMAD_TOKEN_FILE` during subticket 4; if
it is no longer zero, the shim is optional and this ticket shrinks.

## 4. Context (today's state)

### The versions already have a single source of truth

`bootstrap/inventory/group_vars/all.yml` declares all four:

```yaml
hashistack_versions:
  consul: 2.0.2-1
  vault: 2.0.3-1
  nomad: 2.0.4-1
  nomad-driver-podman: 0.6.4-1
```

Both the apt pin written to `/etc/apt/preferences.d/hashistack` and the
install task in `bootstrap/playbooks/install_dependencies.yml` read from
there, so moving a version is one edit. **`deps` must read the same file.** A
second list in the CLI is how the developer's toolchain and the cluster drift
apart while both look pinned.

The values carry a Debian package revision (`-1`). The upstream release
artifacts do not, so the suffix has to be stripped when building a download
URL. That is a small transform and exactly the kind of thing that gets written
twice and then diverges.

### What the shims must do

D2 §12 read this as one shim, `nomad`, with `consul` served by a static
`CONSUL_HTTP_TOKEN_FILE` export and `vault` served by `~/.vault-token`. D2
then measured both and reversed itself in R11 and R12
(`.loop/archive/D2-cli-login-broker-tokens/plan.md:445-501`), and its eval
marker is signed off carrying the reversals as scored rows. All three get a
shim:

| CLI | Reads a credential file? | Needs a shim? |
| --- | --- | --- |
| `vault` | yes, `~/.vault-token`, but `VAULT_TOKEN` outranks it | **yes** |
| `consul` | yes, via `CONSUL_HTTP_TOKEN_FILE`, which is the problem | **yes** |
| `nomad` | no | **yes** |

**D6 does not export `CONSUL_HTTP_TOKEN_FILE` and does not write the file it
names.** D2 measured both failure modes on 2026-07-31: the file outranks
`CONSUL_HTTP_TOKEN`, so a stale one silently beats every fresh token the CLI
emits, and a missing one makes `consul` fail outright with `Error loading
token file ...: no such file or directory` rather than fall back. D6 writes no
tokens at all, so a D6 that exported the variable would break `consul` for
every developer on the next container rebuild, before `localstack login` even
exists. `consul` takes a shim of the same shape as `nomad`'s instead, exporting
`CONSUL_HTTP_TOKEN` for the one invocation.

**`vault` needs a shim too, for the mirror-image reason.** D2 R11 has `login`
write `~/.vault-token`, but that file is inert while `VAULT_TOKEN` is set, and
this devcontainer sets it for everyone (`.devcontainer/.env.example:10`,
injected via `devcontainer.json`). The environment outranks the file, so after
`localstack login` a bare `vault` still runs as the injected root token. D2
R11 names the `vault` shim as one of the two ways out and puts it in D6's
hands. F8 would remove the injected token and make the shim redundant, but F8
is blocked, so the shim is what works today.

So `--with-shims` writes exactly three files: `nomad`, `consul` and `vault`.

### The shim and the pinned binary must not share a directory

D2 §12 wrote the shim to `~/.localstack/bin/nomad` and had it exec
`/usr/bin/nomad`. Both halves are wrong for this ticket, and the first is the
kind of wrong that cancels the ticket out:

- `~/.localstack/bin` is where `deps` installs the pinned binaries (R4). A
  shim at the same path either overwrites the pinned Nomad 2.0.4 or is
  overwritten by it. One of them always loses, and nothing reports which.
- `/usr/bin/nomad` is the apt binary this ticket exists to stop using. It is
  2.0.3 against a 2.0.4 pin, and on a macOS laptop it does not exist at all.
  A shim pointing there reintroduces the skew described above while every
  check still reads green.

So the two live in separate directories, and the shim execs the **pinned**
binary:

```
~/.localstack/bin      pinned real binaries, written by `deps`
~/.localstack/shims    shims, written by `deps --with-shims`
```

PATH order is `shims`, then `bin`, then the system. A bare `nomad`, `consul`
or `vault` finds its shim, which execs the pinned binary. `bin` sits ahead of
the system anyway, so the pinned binary wins for anything not shimmed, and for
every shim removed by `--remove-shims`. Anything neither directory holds falls
through to the system as before.

The contract, superseding D2 §12's listing:

```bash
# ~/.localstack/shims/nomad, mode 0755
#!/usr/bin/env bash
# REAL is written in as an absolute literal at install time. Never resolve
# `nomad` through PATH here: PATH starts at this file.
REAL="/home/vscode/.localstack/bin/nomad"
T="$(localstack token nomad 2>/dev/null)" || exec "$REAL" "$@"
[ -n "$T" ] || exec "$REAL" "$@"
exec env NOMAD_TOKEN="$T" "$REAL" "$@"
```

The `consul` and `vault` shims are the same script with two substitutions: the
tool name, which appears in the path and as the `localstack token` argument,
and the variable, `CONSUL_HTTP_TOKEN` or `VAULT_TOKEN` in place of
`NOMAD_TOKEN`. One template, one code path, three files. The `consul` shim
exports `CONSUL_HTTP_TOKEN` and never `CONSUL_HTTP_TOKEN_FILE`.

The three behaviors that contract carries, all of which R6 and R7 restate: it
falls through when `localstack token` exits non-zero, it falls through when
the token comes back empty rather than exporting an empty variable and
clearing an ambient token, and it can never call itself.

All three were run, for all three tools, against fixture binaries on
2026-07-31. With a token: each shim called its pinned binary once, with its
own variable set. With `localstack token` exiting non-zero: one call, variable
unset. With it exiting zero and printing nothing, and an ambient token in the
environment: one call, and the ambient token survived. No recursion in any
case.

### The architectures in play

The devcontainer is `linux_arm64`, verified from the Terraform provider path
resolved under `.terraform/`. Cluster nodes span arm64 and amd64, and a
developer may be on macOS. `deps` runs on the developer's machine, so it must
resolve its own platform rather than assume the cluster's.

## 5. Non-goals / out of scope

- **No changes to the cluster.** This ticket installs binaries on a
  developer's machine. The apt pin in `install_dependencies.yml` governs the
  nodes and is not touched.
- **No `terraform` install.** Version-managed elsewhere and not part of the
  HashiStack pin.
- **No `nomad-driver-podman`.** It is pinned in the same file but is a server
  plugin with no client CLI.
- **No new source of version truth.** If `deps` needs a version the
  `group_vars` file does not carry, add it there rather than in the CLI.
- **No session or token logic.** `localstack token` is D2's. The shim calls
  it and must not reimplement any part of it.
- **No `CONSUL_HTTP_TOKEN_FILE`, anywhere.** Not exported, not written, not
  mentioned in the devcontainer. D2 R12 owns that call and measured why. This
  ticket writes no tokens, so exporting a variable that names a file nobody
  writes would break `consul` outright rather than do nothing.

## 6. Requirements & restrictions

- **R1. Versions come from `bootstrap/inventory/group_vars/all.yml`.** Parse
  it with `pyyaml`. Do not copy the values into Python, a config file, or a
  constant. A test must fail if the CLI's idea of a version stops matching
  that file.
- **R1a. The CLI states how it finds that file.** It is a repo file, and an
  installed console script runs from anywhere, so the path cannot be
  assumed. Resolve in this order, first hit wins:
  1. `--repo-root PATH`, an option on `deps`.
  2. `LOCALSTACK_REPO_ROOT` in the environment.
  3. Walk up from the working directory for
     `bootstrap/inventory/group_vars/all.yml`.
  4. Walk up from `Path(__file__)` for the same. This is what makes D1's
     recommended `uv tool install --editable ./cli` work from any directory,
     and it is the step that fails for a non-editable install or a copy of
     the CLI outside the checkout.

  When all four miss, `deps` exits non-zero with a message that names the
  file it wanted, the directories it walked, and both `--repo-root` and
  `LOCALSTACK_REPO_ROOT`. It must **not** fall back to a built-in version
  list: that is the second source of truth R1 exists to prevent, and a
  silent fallback is worse than a failed command.

  Step 4 needs the same kind of seam R4 gives the shims, for the same
  reason. Inside the checkout the module always sits under the repo root, so
  step 4 always succeeds and the failure branch is unreachable: a test cannot
  force it by unsetting the overrides, because unsetting them is what hands
  control to step 4. So the resolver takes its walk-up start as a parameter
  defaulting to `Path(__file__)`, and a test passes `tmp_path` to score the
  failure message.
- **R2. Idempotent.** Re-running with the right versions already installed
  changes nothing and says so. This command will be re-run every time someone
  suspects their toolchain.
- **R3. Verify what you download.** Check the published checksum before
  unpacking. A CLI that installs an unverified binary onto a developer's PATH
  is a supply-chain hole in a tool whose entire purpose is credential
  handling.
- **R4. Install under the user's home, never system-wide, and keep binaries
  and shims apart.** Pinned binaries go in `$LOCALSTACK_HOME/bin`, shims in
  `$LOCALSTACK_HOME/shims`, where `LOCALSTACK_HOME` defaults to
  `~/.localstack`. Nothing writes to both directories. No `sudo`, no writes
  to `/usr/bin`; the system binaries stay where they are. `LOCALSTACK_HOME`
  is one env var with two jobs: it keeps the paths out of the code as
  literals, and it is the seam a test uses to redirect the whole install into
  `tmp_path`. The download, idempotency, drift, shim and removal rows in the
  eval marker all need that seam. See Q4.
- **R5. Shims are opt-in and reversible.** `localstack deps --with-shims`
  writes the `nomad`, `consul` and `vault` shims, mode 0755, into
  `$LOCALSTACK_HOME/shims`. `localstack deps --remove-shims` deletes every
  file in that directory and names each one. Removal never touches
  `$LOCALSTACK_HOME/bin`. Shadowing a tool on someone's PATH is a real change
  to their machine and must not be a side effect of "install my
  dependencies". See Q1. `--with-shims` refuses to write a shim for a tool
  that is not installed under `$LOCALSTACK_HOME/bin`, because a shim pointing
  at a path that does not exist is a dead command, which is the one outcome
  R6 exists to prevent.
- **R6. The shim falls through on anything short of a token.** If
  `localstack token` exits non-zero, exec the pinned binary unchanged. If it
  exits zero but prints nothing, exec the pinned binary unchanged as well:
  exporting an empty `NOMAD_TOKEN`, `CONSUL_HTTP_TOKEN` or `VAULT_TOKEN`
  would clear a token the developer already had in the environment, so an
  empty success must not be worse than a failure. A broken CLI degrades to
  today's behavior, never to a dead command.
- **R7. The shim names the pinned binary by absolute literal path.** The
  writer computes `$LOCALSTACK_HOME/bin/<tool>`, expands it, and writes the
  result into the shim body as a literal string. It does not resolve the tool
  through `PATH` at install time or at run time, and it does not leave
  `$HOME` or `$LOCALSTACK_HOME` unexpanded in the shim. `PATH` starts at the
  shims directory, so anything resolved through it finds the shim itself: at
  install time that records the shim's own future path, and at run time it
  recurses until the process dies. Writing the expanded path is also what
  lets a test point the shim at a counter script, which is how the eval row
  for shim recursion is scored at all.
- **R8. `deps` reports drift it cannot fix.** If the installed version does
  not match the pin and the user did not ask to install, say so plainly with
  both versions. Silence here recreates the skew the ticket exists to remove.

## 7. Code surface

Under `cli/`. D1 owns the package skeleton (`src` layout, `main.py`,
`config.py`) and D6 adds to it. D2 established the command registration
convention D6 follows: commands live as modules under
`cli/src/localstack_cli/commands/` (`login.py`, `logout.py`, `whoami.py`,
`env.py`, `token.py`, `config.py` — six already shipped), and `main.py`
registers them **lazily** via `LAZY_SUBCOMMANDS` (`cli/src/localstack_cli/main.py:11-14,42`), not eager `@app.command()`. D6 follows that
convention. D1 bans typer sub-groups and forbids scaffolding a `commands/`
package speculatively for D3 (`.loop/archive/D1-cli-package-skeleton/plan.md:95-97`); D2 already made that scaffold real, so D6 adds to the
existing `commands/` package rather than inventing one. `deps` is a leaf
command module under `commands/`, registered lazily like its siblings.

- `cli/src/localstack_cli/versions.py` **(new)**: locates
  `bootstrap/inventory/group_vars/all.yml` per R1a, parses it, strips the
  packaging revision in exactly one function, returns a version per tool.
- `cli/src/localstack_cli/platforms.py` **(new)**: OS and architecture to
  release-artifact name. Named in the plural so it cannot be mistaken for the
  stdlib `platform` module it imports.
- `cli/src/localstack_cli/install.py` **(new)**: download, checksum
  verification, atomic install into `$LOCALSTACK_HOME/bin`.
- `cli/src/localstack_cli/shims.py` **(new)**: the shim writer and remover,
  against `$LOCALSTACK_HOME/shims`. One template renders all three shims,
  parameterised by tool name and token variable, so they cannot drift apart.
- `cli/src/localstack_cli/commands/deps.py` **(new)**: the `deps` command
  function and its options (`--with-shims`, `--remove-shims`, `--repo-root`),
  as a typer app module matching D2's command-module shape.
- `cli/src/localstack_cli/main.py`: one `LAZY_SUBCOMMANDS["deps"]` entry
  pointing at `localstack_cli.commands.deps:app`, matching the six D2 entries.
  Nothing else changes.
- `cli/tests/`: one test module per source module above, mirroring the tree
  as D1's rule 6 requires.
- `cli/pyproject.toml` and `cli/uv.lock`: `uv add pyyaml` (runtime) and `uv
  add --dev types-PyYAML` (so the mypy hook D1 wired can see the stubs). D1's
  runtime dependencies are `click`, `rich`, and `typer`
  (`cli/pyproject.toml:7-9`); `pyyaml` is D6's addition. Use `uv add`, never
  `uv pip` and never a hand-written dependency table.

Read, never edited: `bootstrap/inventory/group_vars/all.yml`.

Also touched: the devcontainer setup, so a rebuilt container puts
`~/.localstack/shims` then `~/.localstack/bin` ahead of the system PATH. PATH
only. It sets no `CONSUL_HTTP_TOKEN_FILE`, per D2 R12. Confirm where that
belongs before editing; it is outside the `cli/` tree.

## 8. Tests & validation gates

Repo gate: `just pre_commit`, including the ruff, mypy and pytest hooks D1
adds. The default suite must stay offline: downloads are mocked, and any test
that reaches a release server carries a marker excluded via `addopts`.

Two things every test here must do, because this devcontainer is not a clean
room. Point `LOCALSTACK_HOME` at `tmp_path` with `monkeypatch`, so no test
reads or writes the developer's real `~/.localstack`. And clear the ambient
credential variables, `NOMAD_TOKEN` and `VAULT_TOKEN` above all, since this
container exports both live, plus `CONSUL_HTTP_TOKEN` and `CONSUL_TOKEN`. A
shim test that leaves one in place cannot tell a token the shim injected from
a token the shell already had. D1 rule 8 says the same thing for
`VAULT_ADDR`.

The eval marker `.loop/evals/D6-cli-deps-and-shims.md` carries the scored
rows.

## 9. Risk assessment

- **Medium: shadowing a binary on PATH.** The shim makes `which nomad` return
  something the developer did not install. Mitigated by R5 (opt-in and
  reversible) and R6 (falls through). The failure to avoid is a shim that
  breaks `nomad` entirely when the CLI has a bug.
- **Medium: a shim that shadows the binary it is supposed to wrap.** If shims
  and binaries share a directory, `--with-shims` replaces the pinned Nomad
  with a script running the unpinned system one, and the ticket ships a
  `nomad` more drifted than before it ran. Mitigated by Q4's split
  directories and R7's absolute literal path. Worth naming as its own risk
  because it fails green: every other row still passes.
- **Medium: installing an unverified binary.** Mitigated by R3. This is the
  one place this CLI could become the attack it is meant to prevent.
- **Low: version parsing drift.** Mitigated by R1 plus a test that fails when
  the parsed values stop matching the file.
- **Low: breaking existing tooling.** Purely additive on the developer's
  machine. Nothing about the cluster changes.

## 10. Subtickets (ordered)

1. `uv add pyyaml`, then the version resolver against `group_vars/all.yml`,
   including the repo-root search from R1a and its failure message, with the
   test from R1.
2. Platform resolution and the download-plus-verify path.
3. `localstack deps` installing the three CLIs into `$LOCALSTACK_HOME/bin`,
   idempotent, with drift reporting.
4. Shim install and removal behind the flags from R5, into
   `$LOCALSTACK_HOME/shims`.
5. Devcontainer wiring: PATH as shims, bin, system. No
   `CONSUL_HTTP_TOKEN_FILE`.
6. Docs.

## 11. Open questions (operator must settle)

> **All questions in this section were resolved on 2026-07-31 in
> `## Forks resolved, 2026-07-31` at the end of this plan.** Each followed the
> recommendation recorded below, so these read as history rather than as
> pending decisions.


**Q1 — should `deps` install the shims by default?**
Locked provisionally as **opt-in** (`--with-shims`), which is the honest
default: shadowing `nomad` is a change to someone's machine and should be
asked for. The counter-argument is that inside the devcontainer it does not
matter, the container is disposable, and making it opt-in means every
developer hits the "why doesn't `nomad` see my login" question once.
*Recommendation:* keep opt-in for the command, and have the devcontainer pass
`--with-shims` at build. That way the container is seamless and a laptop is
not surprised. Flagged rather than assumed, because the operator raised it and
did not settle it.

**Q2 — where do the binaries come from?**
`releases.hashicorp.com` publishes versioned zips and checksums for every
platform, which suits R3 well. The alternative is the apt repository the
cluster uses, which matches the pinned package revision exactly but is
Debian-only and would not serve a developer on macOS.
*Recommendation:* `releases.hashicorp.com`, and strip the `-1` revision.
Confirm the URL shape and checksum file format during subticket 2 rather than
writing it into the plan from memory.

**Q3 — should `deps` also install `terraform`?**
It is the one tool a developer needs that is not in the HashiStack pin, and
it is the tool a version mismatch hurts most, since state files carry a
version constraint.
*Recommendation:* no, not in this ticket, and open a separate one if the pain
is real. Terraform's version is not declared anywhere this ticket can read,
so including it would mean inventing the second source of truth R1 exists to
prevent.

**Q4 — where do the shims live, and what do they exec?**
D2 §12 put the `nomad` shim at `~/.localstack/bin/nomad` and had it exec
`/usr/bin/nomad`. The pinned binaries this ticket installs were headed for
that same directory, so the two collide: one overwrites the other, and if the
shim wins, a bare `nomad` runs the unpinned system binary. The version half
and the shim half of this ticket then cancel out, silently, while every check
reads green.
*Recommendation:* split the directories. Pinned binaries in
`~/.localstack/bin`, shims in `~/.localstack/shims`, PATH ordered shims then
bin then system, and the shim execs the pinned binary at its absolute path
rather than `/usr/bin`. That removes the collision and makes the shim wrap
the right version instead of the wrong one. The cost is a second directory on
PATH and a supersession of D2 §12's listing, which is cheap next to shipping
a `nomad` more drifted than the one the developer started with.

## Forks resolved, 2026-07-31

- **Q1 → opt-in.** `localstack deps` installs no shim; `--with-shims` does,
  and the devcontainer passes it at build time. Shadowing `nomad` on a
  developer's PATH is a change to their machine and must be asked for, while a
  disposable container can be seamless. The cost is real and accepted: someone
  running `deps` on a laptop will hit "why does `nomad` not see my login" once.
  R8's drift report should name the missing shims so that once is enough.
- **Q2 → `releases.hashicorp.com`, stripping the `-1` revision.** It publishes
  per-platform archives with checksums, which is what R3 needs, and it serves
  macOS. The apt repository matches the pinned package revision exactly but is
  Debian-only, and `deps` runs on the developer's machine. Confirm the URL
  shape and checksum format during subticket 2 rather than writing them in
  from memory.
- **Q3 → no `terraform`.** Its version is declared nowhere this ticket can
  read, so including it would mean inventing the second source of truth R1
  exists to prevent. Open a separate ticket if the pain is real.
- **Q4 → separate directories, and the shim execs the pinned binary.**
  Binaries in `~/.localstack/bin`, shims in `~/.localstack/shims`, PATH
  ordered shims then bin then system. D2 §12's listing is superseded for this
  repo on both counts: the shim path and the `/usr/bin/nomad` target. R4, R5
  and R7 carry the decision, and the contract in "The shim and the pinned
  binary must not share a directory" is the one to implement. Two things this
  buys beyond removing the collision: `--remove-shims` can clear a whole
  directory without ever endangering an installed binary, and the shim wraps
  the version this ticket pinned rather than whatever apt left behind.

## Premises / assumptions

- **P1.** `nomad` has no credential-file mechanism, so a PATH shim is the only
  way a bare `nomad` inherits a session.
  `probe: strings -a /usr/bin/nomad | grep -c NOMAD_TOKEN_FILE` returns `0`,
  and a wire-level check with `NOMAD_TOKEN_FILE` set sent no `X-Nomad-Token`
  header. Measured against Nomad 2.0.3; the pin `deps` installs is 2.0.4, so
  re-check during subticket 4.

- **P2.** `vault` reads `~/.vault-token` natively and `consul` reads
  `CONSUL_HTTP_TOKEN_FILE`, but each fails in this devcontainer for the
  mirror-image reasons above.
  `probe: vault token lookup` against a capture listener sent `X-Vault-Token`
  from `$HOME/.vault-token`; `probe: consul acl token read -self` sent
  `X-Consul-Token` from the file named by `CONSUL_HTTP_TOKEN_FILE`.

- **P3.** `bootstrap/inventory/group_vars/all.yml` is the single source of
  version truth, read by both the apt pin and the install task.
  `Evidence: bootstrap/inventory/group_vars/all.yml:9-13` declares the four
  versions; `bootstrap/playbooks/install_dependencies.yml:22,118-121,138`
  iterates them. No other file references `hashistack_versions`.

- **P4.** `releases.hashicorp.com` publishes architecture-specific archives
  and checksums for these versions, and stripping `-1` yields a valid
  upstream version.
  `source: https://releases.hashicorp.com/nomad/2.0.4/` — the version
  directory serves archives plus a `SHA256SUMS` file for nomad, vault and
  consul. A HEAD request to the linux aarch64 archive returns `200`.

- **P5.** The shim contract works as written: it falls through on non-zero
  exit, falls through on empty success, and never recurses.
  `probe: env -i bash -c 'T="$(false)" || echo fallthrough'` prints
  `fallthrough`; run against a fixture binary with `localstack token`
  exiting non-zero, zero-empty, and zero-with-token, the counter recorded
  one call in every case.

- **P6.** The pinned binaries and the shims must not share a directory, and
  the shim must exec the pinned binary at its absolute path. A shared
  directory makes `--with-shims` overwrite the pinned Nomad 2.0.4 or vice
  versa, and a shim targeting `/usr/bin/nomad` reintroduces the skew this
  ticket exists to remove.
  `Evidence: this plan R4 and R7` carry the split-directory and
  absolute-literal-path decision; the eval marker rows 8, 9 and 12 score it.

- **P7.** The `cli/` layout is settled by D1 and D2. D1 bans typer sub-groups
  and forbids scaffolding a `commands/` package speculatively for D3
  (`Evidence: .loop/archive/D1-cli-package-skeleton/plan.md:95-97`); D2 made
  that package real, shipping six command modules under
  `cli/src/localstack_cli/commands/` registered lazily via `LAZY_SUBCOMMANDS`
  (`Evidence: cli/src/localstack_cli/commands/` contents;
  `cli/src/localstack_cli/main.py:11-14,42`). D6 follows that convention:
  `deps` is a leaf command module under `commands/`, registered lazily.

- **P8.** An installed `localstack` can read `group_vars/all.yml` at run time.
  `UNCERTAIN.` R1a resolves the repo root via `--repo-root`,
  `LOCALSTACK_REPO_ROOT`, or a walk from the working directory or
  `Path(__file__)`. The walk from `__file__` works for an editable install but
  fails for a non-editable one or a copy outside the checkout; the failure
  branch is what R1a's exit-non-zero message exists to cover, and subticket 1
  tests it via the walk-up-start seam.

- **P9.** The eval rows are testable as written. Most are deterministic against
  fixtures under `tmp_path` with `LOCALSTACK_HOME` redirected and the ambient
  token vars cleared. Row 7's recursion check needs the absolute-literal-path
  seam from R7 so a test can point the shim at a counter script; row 6 needs
  `NOMAD_TOKEN` cleared before the run because this devcontainer exports a
  real one; row 1's grep is scoped to `cli/src/` so a test fixture writing
  `2.0.4` does not trip it.
  `Evidence: .loop/evals/D6-cli-deps-and-shims.md` rows 1, 6, 7 carry these
  scoping rules; the rest are straightforward against mocks.