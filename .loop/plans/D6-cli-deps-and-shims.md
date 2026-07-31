---
epic = "cli"
depends_on = ["D1-cli-package-skeleton"]
priority = 44
summary = "`localstack deps` installs the HashiCorp CLIs at exactly the versions this cluster pins, reading them from the same group_vars file the Ansible pin reads, and optionally installs the PATH shims that let a bare `nomad` command inherit a `localstack login` session."
tags = ["cli", "tooling", "versions", "shims"]
---

# D6 — `localstack deps`: pinned CLIs and the PATH shims

## Title

Install the `vault`, `nomad` and `consul` CLIs at the versions this cluster
runs, resolved from the repo's single declaration point, plus the optional
PATH shims that make a bare `nomad` command pick up the session from
`localstack login`.

## Size / Effort

**M.** The download-and-install path is ordinary work: resolve architecture,
fetch, verify, unpack, place. The care is in three places. The versions must
come from the file that already governs the cluster rather than a second
list. The install must be idempotent, because it will be re-run. And the
shims shadow real binaries on a developer's PATH, which is a change to their
machine that has to be reversible and obvious.

## Triggered by

Two findings from the 2026-07-31 design session.

**Version skew is real and silent.** The cluster runs Consul 2.0.2, Vault
2.0.3 and Nomad 2.0.4. The devcontainer currently carries Consul CLI 2.0.1 and
Nomad CLI 2.0.3. A CLI that drifts far from its server produces failures that
read like bugs in the cluster.

**`nomad` cannot inherit a session any other way.** Measured against the
installed binaries: `NOMAD_TOKEN_FILE` does not exist, `nomad login` has no
sink flag, and a child process cannot set its parent shell's environment. The
PATH shim is the only mechanism that makes a bare `nomad job status` work
after `localstack login`, and D2 §12 locked it as the design.

## Context (today's state)

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

From D2 §12, verified against the installed binaries:

| CLI | Reads a credential file? | Needs a shim? |
| --- | --- | --- |
| `vault` | yes, `~/.vault-token` | no, once D2 writes it |
| `consul` | yes, via `CONSUL_HTTP_TOKEN_FILE` | no, if that var is set statically |
| `nomad` | no | **yes** |

`CONSUL_HTTP_TOKEN_FILE` names a path, never changes, and holds no secret, so
it is configuration the devcontainer can export once.

The contract, from D2 §12:

```bash
# ~/.localstack/bin/nomad
#!/usr/bin/env bash
T="$(localstack token nomad 2>/dev/null)" || exec /usr/bin/nomad "$@"
exec env NOMAD_TOKEN="$T" /usr/bin/nomad "$@"
```

### The architectures in play

The devcontainer is `linux_arm64`, verified from the Terraform provider path
resolved under `.terraform/`. Cluster nodes span arm64 and amd64, and a
developer may be on macOS. `deps` runs on the developer's machine, so it must
resolve its own platform rather than assume the cluster's.

## Non-goals / out of scope

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

## Requirements & restrictions

- **R1. Versions come from `bootstrap/inventory/group_vars/all.yml`.** Parse
  it. Do not copy the values into Python, a config file, or a constant. A test
  must fail if the CLI's idea of a version stops matching that file.
- **R2. Idempotent.** Re-running with the right versions already installed
  changes nothing and says so. This command will be re-run every time someone
  suspects their toolchain.
- **R3. Verify what you download.** Check the published checksum before
  unpacking. A CLI that installs an unverified binary onto a developer's PATH
  is a supply-chain hole in a tool whose entire purpose is credential
  handling.
- **R4. Install under the user's home, never system-wide.** `~/.localstack/bin`.
  No `sudo`, no writes to `/usr/bin`. The real binaries stay where they are.
- **R5. Shims are opt-in and reversible.** `localstack deps --with-shims`
  installs them; `localstack deps --remove-shims` removes them and says what
  it removed. Shadowing `nomad` on someone's PATH is a real change to their
  machine and must not be a side effect of "install my dependencies". See Q1.
- **R6. The shim falls through on failure.** If `localstack token` exits
  non-zero, exec the real binary unchanged. A broken CLI must degrade to
  today's behavior, never to a dead `nomad`.
- **R7. The shim resolves the real binary by absolute path**, recorded at
  install time. Re-resolving through `PATH` makes the shim call itself.
- **R8. `deps` reports drift it cannot fix.** If the installed version does
  not match the pin and the user did not ask to install, say so plainly with
  both versions. Silence here recreates the skew the ticket exists to remove.

## Code surface

Under `cli/` (layout owned by `D1-cli-package-skeleton`):

- A version resolver that reads and parses
  `bootstrap/inventory/group_vars/all.yml`, strips the packaging revision, and
  returns a version per tool.
- A platform resolver for OS and architecture.
- A downloader with checksum verification and atomic install into
  `~/.localstack/bin`.
- The shim writer and remover.
- `commands/deps.py` rendering it.

Read, never edited: `bootstrap/inventory/group_vars/all.yml`.

Also touched: the devcontainer setup, so a rebuilt container gets
`~/.localstack/bin` on PATH ahead of `/usr/bin` and exports
`CONSUL_HTTP_TOKEN_FILE`. Confirm where that belongs before editing; it is
outside the `cli/` tree.

## Tests & validation gates

Repo gate: `just pre_commit`, including the ruff, mypy and pytest hooks D1
adds. The default suite must stay offline: downloads are mocked, and any test
that reaches a release server carries a marker excluded via `addopts`.

The eval marker `.loop/evals/D6-cli-deps-and-shims.md` carries the scored
rows.

## Risk assessment

- **Medium: shadowing a binary on PATH.** The shim makes `which nomad` return
  something the developer did not install. Mitigated by R5 (opt-in and
  reversible) and R6 (falls through). The failure to avoid is a shim that
  breaks `nomad` entirely when the CLI has a bug.
- **Medium: installing an unverified binary.** Mitigated by R3. This is the
  one place this CLI could become the attack it is meant to prevent.
- **Low: version parsing drift.** Mitigated by R1 plus a test that fails when
  the parsed values stop matching the file.
- **Low: breaking existing tooling.** Purely additive on the developer's
  machine. Nothing about the cluster changes.

## Subtickets (ordered)

1. Version resolver against `group_vars/all.yml`, with the test from R1.
2. Platform resolution and the download-plus-verify path.
3. `localstack deps` installing the three CLIs, idempotent, with drift
   reporting.
4. Shim install and removal behind the flags from R5.
5. Devcontainer wiring: PATH and `CONSUL_HTTP_TOKEN_FILE`.
6. Docs.

## Open questions (operator must settle)

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
