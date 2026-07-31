eval: D6-cli-deps-and-shims

**Forks resolved 2026-07-31.** Q1 shims are opt-in, with the devcontainer
passing `--with-shims` at build. Q2 binaries come from `releases.hashicorp.com`
with the `-1` packaging revision stripped. Q3 no `terraform` install. The rows
below already score those answers.

**Definition of Done:** `localstack deps` installs the `vault`, `nomad` and
`consul` CLIs at the versions declared in
`bootstrap/inventory/group_vars/all.yml`, into `~/.localstack/bin`, verifying
each download before it lands. `--with-shims` installs the PATH shims that let
a bare `nomad` inherit a `localstack login` session, and `--remove-shims`
takes them back off. Re-running changes nothing.

**The trap this marker guards.** Every row here is easy to pass by doing the
happy path. `deps` that downloads and installs will look finished while
carrying its own copy of the version numbers (row 1), skipping checksum
verification (row 3), or shipping a shim that turns a CLI bug into a dead
`nomad` (row 6). Rows 1, 3, 6 and 7 are the ones that can actually fail.

**One measured fact drives the shim rows.** `NOMAD_TOKEN_FILE` does not exist:
zero occurrences in the Nomad 2.0.3 binary, against two for
`CONSUL_HTTP_TOKEN_FILE`, and `nomad login` has no sink flag. So `nomad` reads
`NOMAD_TOKEN` or `-token` and nothing else, and no amount of file-writing
substitutes for the shim.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| **Versions are READ from `group_vars`, never carried** | Edit `hashistack_versions.nomad` in a fixture copy of `bootstrap/inventory/group_vars/all.yml`, then ask the resolver what it wants | The resolved version follows the file. Then `grep -rnE '2\.0\.[0-9]' cli/ --include='*.py'` finds **no HashiStack version literal** in the source. A CLI carrying its own copy looks pinned while drifting from the cluster, which is the exact failure this ticket exists to remove | deterministic check (resolver follows the file; no version literals in source) | 100% |
| The packaging revision is stripped once | Resolve each of the three tools | `2.0.4-1` in the file yields `2.0.4` in the download URL. The transform lives in one place; `grep` finds no second implementation. Written twice is how it diverges | deterministic check (suffix stripped; single implementation) | 100% |
| **An unverified download never lands on PATH** | Serve a mocked release whose checksum does not match the published one | `deps` exits NON-ZERO, nothing is written into `~/.localstack/bin`, and the message names the mismatch. Verify no partial file survives either. This CLI exists to handle credentials; installing an unchecked binary onto the developer's PATH would make it the attack it is meant to prevent | deterministic check (non-zero exit; nothing installed; no partial file) | 100% |
| **Idempotent** | Run `deps` twice against mocks; capture what the second run does | The second run downloads nothing, writes nothing, and reports that the versions already match. This command gets re-run every time someone suspects their toolchain, so a re-run that silently refetches wastes time and hides whether anything was wrong | deterministic check (second run performs no download or write) | 100% |
| **Drift is reported, not silently corrected or ignored** | Place a wrong-version binary in `~/.localstack/bin`, then run `deps` in its reporting mode | Both versions are named, installed and pinned, and the exit status distinguishes drift from agreement. Saying nothing recreates the skew the ticket exists to remove; silently overwriting hides that the developer's machine was wrong | deterministic check (both versions reported; exit status distinguishes) | 100% |
| **The shim falls through when `localstack token` fails** | Install shims, then make `localstack token` exit non-zero (no session), then run `nomad version` through the shim | `nomad version` still works, running the real binary with no token injected. **A shim that fails hard turns any CLI bug into a dead `nomad`**, which is a worse machine than the one the developer started with. This is the row that decides whether shims are safe to ship | deterministic check (bare command succeeds via the real binary when token fails) | 100% |
| **The shim cannot call itself** | Install shims with `~/.localstack/bin` ahead of `/usr/bin`, then run `nomad version` and observe the process tree or a call counter | The real binary at its absolute path is executed exactly once. Resolving through `PATH` at run time makes the shim re-find itself and loop until the process dies, and it does so only on a correctly configured machine, so it passes every test that forgets to put the shim first | deterministic check (real absolute path executed once; no recursion) | 100% |
| **`--remove-shims` fully reverses `--with-shims`** | `deps --with-shims`, snapshot `~/.localstack/bin`, then `deps --remove-shims` | Every shim written is removed and named in the output; the installed CLI binaries are **not** removed with them. Shadowing a binary on someone's PATH must be reversible by the tool that did it, and a removal that also deletes the real tooling is not a reversal | deterministic check (shims gone and listed; CLI binaries intact) | 100% |
| Shims are not installed without asking | `localstack deps` with no flags | No shim is written, and the run reports that shims are absent so the developer learns the flag exists. Q1 resolved: shadowing `nomad` is a change to the developer's machine and is opt-in, with the devcontainer passing `--with-shims` at build time. The accepted cost is that someone running `deps` on a laptop hits "why does `nomad` not see my login" once, so the drift report is what keeps it to once | deterministic check (no shim written; absence reported) | 100% |
| The platform is resolved, not assumed | Run the platform resolver under mocked `linux/arm64`, `linux/amd64` and `darwin/arm64` | The correct artifact name for each. The devcontainer is `linux_arm64` and the cluster spans both architectures, but `deps` runs on the **developer's** machine, which may be a Mac | deterministic check (correct artifact per platform) | 100% |
| **Guardrail: nothing outside the developer's home is touched** | Review the diff and the runtime behavior | No `sudo`, no write under `/usr/bin` or any system path, no change to `bootstrap/**`, and `group_vars/all.yml` is read but never written. The apt pin governs the cluster nodes; this ticket governs one laptop | deterministic check (no privileged or system writes; no `bootstrap/**` changes) | 100% |
| The default test suite is offline | `cd cli && uv run pytest` with no network | Green, and no outbound request. Downloads are mocked; any test reaching a real release server carries a marker excluded via `addopts` | deterministic check (suite green and offline) | 100% |
| The repo gate passes | `just worktree_setup <path>`, then `just pre_commit` | All Passed, including the ruff, mypy and pytest hooks D1 added | deterministic check (`just pre_commit` all Passed) | 100% |

signed-off-by: JasperHG90 2026-07-31
