eval: D6-cli-deps-and-shims

**Forks resolved 2026-07-31.** Q1 shims are opt-in, with the devcontainer
passing `--with-shims` at build. Q2 binaries come from `releases.hashicorp.com`
with the `-1` packaging revision stripped. Q3 no `terraform` install. Q4 the
pinned binaries and the shims live in separate directories and the shim execs
the pinned binary. The rows below already score those answers.

**Definition of Done:** `localstack deps` installs the `vault`, `nomad` and
`consul` CLIs at the versions declared in
`bootstrap/inventory/group_vars/all.yml`, into `$LOCALSTACK_HOME/bin`
(default `~/.localstack/bin`), verifying each download before it lands.
`--with-shims` writes the `nomad`, `consul` and `vault` shims into
`$LOCALSTACK_HOME/shims`, where each execs its pinned binary and lets a bare
command inherit a `localstack login` session, and `--remove-shims` takes them
back off without touching the binaries. Re-running changes nothing.

**Two directories, and the difference is load-bearing.** `$LOCALSTACK_HOME/bin`
holds the pinned real binaries and `$LOCALSTACK_HOME/shims` holds the shims.
PATH runs shims, then bin, then the system. Put them in one directory and
`--with-shims` overwrites the pinned Nomad 2.0.4 with a script that runs the
unpinned system 2.0.3, which is the exact skew this ticket exists to remove,
and it does so while every other row still scores green. Rows 8, 9 and 12
score the split.

**The trap this marker guards.** Every row here is easy to pass by doing the
happy path. `deps` that downloads and installs will look finished while
carrying its own copy of the version numbers (row 1), skipping checksum
verification (row 4), shipping a shim that turns a CLI bug into a dead `nomad`
(row 7), or shimming the wrong binary (row 8). Rows 1, 2, 4, 7 and 8 are the
ones that can actually fail.

**Redirect the home and clear the environment in every row.** Point
`LOCALSTACK_HOME` at `tmp_path`, so no row reads or writes the developer's
real `~/.localstack`, and delete `NOMAD_TOKEN` and `VAULT_TOKEN` from the
environment along with `CONSUL_HTTP_TOKEN` and `CONSUL_TOKEN`. This
devcontainer exports `NOMAD_TOKEN`, `VAULT_TOKEN` and `CONSUL_TOKEN` live, so
a shim row that leaves one in place cannot tell a token the shim injected from
a token the shell already had.

**One measured fact drives the shim rows.** `NOMAD_TOKEN_FILE` does not exist:
zero occurrences in the Nomad 2.0.3 binary, against two for
`CONSUL_HTTP_TOKEN_FILE`, and `nomad login` has no sink flag. Measured at the
wire, not just with `strings`: with `NOMAD_TOKEN_FILE` set and the file
present, `nomad` sent no `X-Nomad-Token` header. So `nomad` reads
`NOMAD_TOKEN` or `-token` and nothing else, and no amount of file-writing
substitutes for the shim.

**All three CLIs get a shim, and `consul` gets no token file.** D2 R11 and R12
(`.loop/plans/D2-cli-login-broker-tokens.md:410-466`) reversed D2 §12 on both
`consul` and `vault`, and D2's marker is signed off carrying the reversals.
`CONSUL_HTTP_TOKEN_FILE` outranks `CONSUL_HTTP_TOKEN`, so a stale file beats
every fresh token and a missing file makes `consul` fail outright instead of
falling back. D6 writes no tokens, so exporting that variable would break
`consul` on the next container rebuild, and row 12 greps the diff for it.
`vault` is the mirror image: `~/.vault-token` is inert while `VAULT_TOKEN` is
set, and this devcontainer sets it for everyone, so a bare `vault` runs as the
injected root token until the shim overrides it for one invocation.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| **Versions are READ from `group_vars`, never carried** | Edit `hashistack_versions.nomad` in a fixture copy of `bootstrap/inventory/group_vars/all.yml`, then ask the resolver what it wants | The resolved version follows the file. Then `grep -rnE '2\.0\.[0-9]' cli/src --include='*.py'` finds **no HashiStack version literal** in the source. Scoped to `cli/src` on purpose: `cli/tests` is where a fixture legitimately writes `2.0.4` down, and a grep that covers it fails the row for doing the right thing. A CLI carrying its own copy looks pinned while drifting from the cluster, which is the exact failure this ticket exists to remove | deterministic check (resolver follows the file; no version literals under `cli/src`) | 100% |
| **The repo file is found from anywhere, or the run fails loudly** | Resolve with `--repo-root` at the checkout; again with `LOCALSTACK_REPO_ROOT` set; then with both unset, from a working directory under `tmp_path` and with the resolver's walk-up start passed as `tmp_path` | With a root supplied by either the flag or the env var, the versions resolve. With neither, and no `bootstrap/inventory/group_vars/all.yml` above the working directory or above the walk-up start, `deps` exits NON-ZERO and the message names the file, the directories it walked, and both ways to supply the root. Passing the walk-up start is what makes this row scorable at all: the module normally lives inside the checkout, so the default start always finds the repo root and the failure branch is unreachable. Unsetting the overrides cannot force it, because unsetting them is what hands control to the walk. It must **not** fall back to a built-in version list. An installed console script runs anywhere, so a resolver that only works from the checkout is a command that breaks the day someone installs it properly, and a silent fallback is the second source of truth R1 exists to prevent | deterministic check (both overrides work; missing root exits non-zero with a message naming file, search path and both overrides; no fallback versions) | 100% |
| The packaging revision is stripped once | Resolve each of the three tools | `2.0.4-1` in the file yields `2.0.4` in the download URL. The transform lives in one place; `grep` finds no second implementation. Written twice is how it diverges | deterministic check (suffix stripped; single implementation) | 100% |
| **An unverified download never lands on PATH** | Serve a mocked release whose checksum does not match the published one, with `LOCALSTACK_HOME` in `tmp_path` | `deps` exits NON-ZERO, nothing is written into `$LOCALSTACK_HOME/bin`, and the message names the mismatch. Verify no partial file survives either. This CLI exists to handle credentials; installing an unchecked binary onto the developer's PATH would make it the attack it is meant to prevent | deterministic check (non-zero exit; nothing installed; no partial file) | 100% |
| **Idempotent** | Run `deps` twice against mocks; capture what the second run does | The second run downloads nothing, writes nothing, and reports that the versions already match. This command gets re-run every time someone suspects their toolchain, so a re-run that silently refetches wastes time and hides whether anything was wrong | deterministic check (second run performs no download or write) | 100% |
| **Drift is reported, not silently corrected or ignored** | Place a wrong-version binary in `$LOCALSTACK_HOME/bin`, then run `deps` in its reporting mode | Both versions are named, installed and pinned, and the exit status distinguishes drift from agreement. Saying nothing recreates the skew the ticket exists to remove; silently overwriting hides that the developer's machine was wrong | deterministic check (both versions reported; exit status distinguishes) | 100% |
| **The shim falls through when `localstack token` gives it nothing** | With `NOMAD_TOKEN` deleted from the environment, install the shim over a fixture binary, then run `nomad version` through it twice: once with `localstack token` exiting non-zero (no session), once with it exiting zero and printing an empty string | Both runs work, and both reach the fixture with `NOMAD_TOKEN` unset rather than set to the empty string. **A shim that fails hard turns any CLI bug into a dead `nomad`**, which is a worse machine than the one the developer started with, and an empty `NOMAD_TOKEN` clears a token the developer already had, which is worse still because it looks like success. Delete `NOMAD_TOKEN` first: this devcontainer exports a real one, and a row that inherits it passes or fails on the developer's shell rather than on the code. Run the same two cases against the `consul` and `vault` shims with `CONSUL_HTTP_TOKEN` and `VAULT_TOKEN` cleared, since one template renders all three and a fall-through that works for one must work for the others | deterministic check (both runs succeed via the fixture for all three shims; the token variable absent, not empty; ambient tokens cleared before the run) | 100% |
| **The shim execs the pinned binary, exactly once, and can never call itself** | Put a counter script at `$LOCALSTACK_HOME/bin/nomad`, write the shim, put `$LOCALSTACK_HOME/shims` ahead of `$LOCALSTACK_HOME/bin` and both ahead of `/usr/bin`, then run `nomad version` | The counter records exactly one call: the shim ran the **pinned** binary at its absolute literal path. Nothing runs `/usr/bin/nomad`. `LOCALSTACK_HOME` in `tmp_path` is what makes this row scorable, since it is how the recorded path gets pointed at the counter. Two failures hide here. A shim that resolves `nomad` through `PATH` re-finds itself and loops until the process dies, and it only does so on a correctly configured machine, so it passes any test that forgets to put the shims directory first. A shim that execs `/usr/bin/nomad` wraps the unpinned 2.0.3 and quietly undoes the version half of this ticket | deterministic check (pinned absolute path called exactly once; no recursion; no call to a system path) | 100% |
| **`--remove-shims` fully reverses `--with-shims`** | `deps --with-shims`, snapshot both `$LOCALSTACK_HOME/shims` and `$LOCALSTACK_HOME/bin`, then `deps --remove-shims` | The snapshot shows `--with-shims` wrote exactly three files, `nomad`, `consul` and `vault`, each rendered from the one template. After removal the shims directory is empty and every removed shim is named in the output; `$LOCALSTACK_HOME/bin` is byte-for-byte what it was, all three pinned binaries still there and still executable. The separate directories are what make this row scorable: share one and the `nomad` shim and the `nomad` binary are the same file, so no removal can take one and keep the other. Shadowing a binary on someone's PATH must be reversible by the tool that did it, and a removal that also deletes the real tooling is not a reversal | deterministic check (shims directory empty and each removal listed; `bin` unchanged and executable) | 100% |
| Shims are not installed without asking | `localstack deps` with no flags | No file is written under `$LOCALSTACK_HOME/shims`, and the run reports that shims are absent so the developer learns the flag exists. Q1 resolved: shadowing `nomad` is a change to the developer's machine and is opt-in, with the devcontainer passing `--with-shims` at build time. The accepted cost is that someone running `deps` on a laptop hits "why does `nomad` not see my login" once, so the drift report is what keeps it to once | deterministic check (no shim written; absence reported) | 100% |
| The platform is resolved, not assumed | Run the platform resolver under mocked `linux/arm64`, `linux/amd64` and `darwin/arm64` | The correct artifact name for each. The devcontainer is `linux_arm64` and the cluster spans both architectures, but `deps` runs on the **developer's** machine, which may be a Mac | deterministic check (correct artifact per platform) | 100% |
| **Guardrail: nothing outside the developer's home is touched** | Review the diff and the runtime behavior | No `sudo`, no write under `/usr/bin` or any system path, no change to `bootstrap/**`, and `group_vars/all.yml` is read but never written. Every write lands under `$LOCALSTACK_HOME`, and no code path writes both `bin` and `shims`: the installer only writes `bin`, the shim writer only writes `shims`. `grep -r CONSUL_HTTP_TOKEN_FILE` over the branch diff finds nothing, in the devcontainer or anywhere else: D2 R12 owns that call, D6 writes no tokens, and exporting the variable would break `consul` outright rather than do nothing. The apt pin governs the cluster nodes; this ticket governs one laptop | deterministic check (no privileged or system writes; no `bootstrap/**` changes; each writer owns one directory; no `CONSUL_HTTP_TOKEN_FILE` in the diff) | 100% |
| The default test suite is offline | `cd cli && uv run pytest` with no network | Green, and no outbound request. Downloads are mocked; any test reaching a real release server carries a marker excluded via `addopts` | deterministic check (suite green and offline) | 100% |
| The repo gate passes | `just worktree_setup <path>`, then `just pre_commit` | All Passed, including the ruff, mypy and pytest hooks D1 added. `pyyaml` and `types-PyYAML` go in through `uv add` and land in `cli/pyproject.toml` and `cli/uv.lock`, never through `uv pip` and never as a hand-written table entry. Without the stubs the mypy hook fails on the YAML import | deterministic check (`just pre_commit` all Passed) | 100% |

signed-off-by: JasperHG90 2026-07-31

**Signature history, 2026-07-31.** First signed against a single-directory
layout where the pinned binaries and the `nomad` shim shared
`~/.localstack/bin`. Cleared when the plan-validator showed that layout
cancels the ticket out, since `--with-shims` overwrites the pinned Nomad with
a script running the unpinned system one, which also made the removal row
unsatisfiable. Re-signed against the split directories, with row 2 added for
the repo-root search, row 1's grep scoped to `cli/src`, rows 7 and 8 given the
`LOCALSTACK_HOME` seam and the cleared ambient token, and rows 7, 9 and 12
re-scored for three shims and no `CONSUL_HTTP_TOKEN_FILE`, per D2 R11 and R12.
