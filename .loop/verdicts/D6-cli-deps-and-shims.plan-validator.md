---
verdict: fail
---

# Plan review: D6-cli-deps-and-shims (pass `plan-validator`)

Plan reviewed: `.loop/plans/D6-cli-deps-and-shims.md`
Content sha256 (computed here, not supplied by the briefing):
`6aa999800f8fdae9c745099b2e44054640c1933e50dfe007086d544dd0a7634d`.
This verdict is a `fail`, so it carries no `plan:` line and cannot authorize
the flip to `ready`. See "Briefing gap" at the end.

## Premise verdict: PARTIALLY SOUND

Every external fact this plan rests on holds, and several hold under direct
measurement rather than inference. The plan fails on an internal
contradiction it never surfaces: the pinned binaries and the `nomad` shim
are both specified to live at the same path, and the shim as written targets
the drifted system binary the ticket exists to stop using.

## Per assumption

### P1 — `nomad` has no credential-file mechanism, so a PATH shim is the
only way a bare `nomad` inherits a session. HOLDS (measured at the wire).

- `strings -a /usr/bin/nomad | grep -c NOMAD_TOKEN_FILE` returns `0`;
  `CONSUL_HTTP_TOKEN_FILE` returns `2`. Exactly the counts the plan
  (`.loop/plans/D6-cli-deps-and-shims.md:37`) and the eval marker
  (`.loop/evals/D6-cli-deps-and-shims.md:21-23`) claim.
- Stronger than a string count: I pointed `NOMAD_ADDR` at a local HTTP
  listener with `NOMAD_TOKEN` unset, `NOMAD_TOKEN_FILE` set to a real file,
  and `$HOME/.nomad-token` present. `nomad job status` sent
  `GET /v1/jobs` and `GET /v1/agent/self` with **no** `X-Nomad-Token`
  header. With `NOMAD_TOKEN` set, both requests carried
  `X-Nomad-Token: ENVTOKEN`. Nomad reads the env var and nothing else.
- `nomad login --help` (Login Options: `-method`, `-oidc-callback-addr`,
  `-login-token`, `-json`, `-t`) has no sink or output-file flag. General
  Options offer `-token` only.
- Caveat, not a break: the measurement is against the installed Nomad
  **2.0.3**, while `group_vars` pins **2.0.4-1**. The plan is honest about
  this ("Measured against the installed binaries"), and nothing suggests
  2.0.4 added a token file, but the binary `deps` will install is not the
  binary that was measured.

### P2 — `vault` reads `~/.vault-token` natively and `consul` reads
`CONSUL_HTTP_TOKEN_FILE`, so neither needs a shim. HOLDS (measured).

Against a local capture listener, with the env token vars cleared and `HOME`
redirected to a temp dir:

- `vault token lookup` sent `GET /v1/auth/token/lookup-self` with
  `X-Vault-Token: hvs.FILETOKEN`, read from `$HOME/.vault-token`.
- `consul acl token read -self` sent `GET /v1/acl/token/self` with
  `X-Consul-Token: CONSUL-FILE-TOKEN`, read from the file named by
  `CONSUL_HTTP_TOKEN_FILE`.

The table at `.loop/plans/D6-cli-deps-and-shims.md:71-76` is accurate.

### P3 — `bootstrap/inventory/group_vars/all.yml` is the single source of
version truth, read by both the apt pin and the install task. HOLDS.

- `bootstrap/inventory/group_vars/all.yml:9-13` declares `consul: 2.0.2-1`,
  `vault: 2.0.3-1`, `nomad: 2.0.4-1`, `nomad-driver-podman: 0.6.4-1`,
  quoted correctly in the plan at `:48-54`.
- The apt preferences template iterates it at
  `bootstrap/playbooks/install_dependencies.yml:22`
  (`{% for pkg, version in hashistack_versions.items() %}`), the package
  install pins from it at `:118-121`, and a third task loops it at `:138`.
  No other file references `hashistack_versions`.

### P4 — `releases.hashicorp.com` publishes per-platform archives and
checksums for these versions, and stripping `-1` yields a valid upstream
version. HOLDS (live).

- `https://releases.hashicorp.com/nomad/2.0.4/nomad_2.0.4_linux_arm64.zip`
  returns `200`, as do the `vault/2.0.3` darwin_arm64 and `consul/2.0.2`
  linux_amd64 archives.
- `nomad_2.0.4_SHA256SUMS`, `vault_2.0.3_SHA256SUMS` and
  `consul_2.0.2_SHA256SUMS` all return `200` and list darwin_amd64,
  darwin_arm64, linux_amd64, linux_arm64 lines. R3 is buildable.
- The `-1` strip is sound, not just plausible: `dpkg-query` reports
  `nomad 2.0.3-1` for the package whose binary prints `Nomad v2.0.3`.
  Package revision to upstream version maps by dropping `-1`.
- The devcontainer is `aarch64` (`uname -m`), so the plan's `linux_arm64`
  claim at `:91` holds, though the stated evidence (a Terraform provider
  path under `.terraform/`) is a weaker source than `uname`.

### P5 — the shim contract works as written. HOLDS mechanically, with one
live fork.

I built the exact contract from `:82-87` with the real path substituted and
ran it three ways:

- `localstack token` succeeds: the real binary ran once, with
  `NOMAD_TOKEN=s.TOKEN123`.
- `localstack token` exits non-zero: the real binary ran once, unchanged.
- `localstack` absent from PATH entirely: same fall-through, exit 0.

`T="$(cmd)" || exec ...` does propagate the substitution's exit status, so
R6 is satisfied by the contract as written. Two live details the plan does
not state:

- `/usr/bin/nomad` is real on this machine (`which -a nomad` gives
  `/usr/bin/nomad`, installed unpinned by `.devcontainer/Dockerfile:16`),
  but it does not exist on a macOS laptop, which the plan explicitly
  supports (`:91-94`). The hardcoded literal is devcontainer-only.
- If `localstack token` succeeds but prints an empty string, the shim
  exports `NOMAD_TOKEN=""` and thereby clears any ambient token. R6 covers
  the non-zero exit but not the empty success.

### P6 — the pinned binaries and the shims can both live in
`~/.localstack/bin`. **BREAKS.** This is the finding that fails the plan.

- R4 (`:122`) installs the three pinned CLIs into `~/.localstack/bin`.
- The shim contract (`:83`, quoted from `D2:697`) puts the `nomad` shim at
  `~/.localstack/bin/nomad`.

Those are the same path. Three consequences the plan never addresses:

1. `--with-shims` overwrites the pinned `nomad` 2.0.4 that `deps` just
   installed, or `deps` overwrites the shim. One of them always loses.
2. The surviving shim execs `/usr/bin/nomad`, which on this machine is the
   apt binary at **2.0.3** against a pin of **2.0.4**. Turning on shims
   silently reintroduces exactly the version skew the ticket opens with
   (`:31-34`). The version half and the shim half of this ticket cancel
   each other for `nomad`.
3. Eval row 8 (`.loop/evals/D6-cli-deps-and-shims.md:36`) requires that
   `--remove-shims` leave "the installed CLI binaries" intact. For `nomad`
   that is unsatisfiable as written: the shim and the binary are one path.
   The row cannot be scored against this plan.

R7 (`:131-132`) makes it worse rather than better. "Resolve the real binary
by absolute path, recorded at install time" is ambiguous once
`~/.localstack/bin` is both the install dir and the shim dir: an
implementer who records the path by resolving `nomad` through `PATH` at
install time records the shim's own future path, and the recursion R7
exists to prevent is what the layout invites.

### P7 — `cli/` layout, including `commands/deps.py`, is settled by D1.
BREAKS (partially).

`.loop/plans/D6-cli-deps-and-shims.md:139` says the layout is "owned by
`D1-cli-package-skeleton`", and `:148` names `commands/deps.py`. D1 says the
opposite: "No read-only commands and no typer sub-groups. That is D3. Do
not scaffold empty groups 'ready for D3'"
(`.loop/plans/D1-cli-package-skeleton.md:95-97`). D1's code surface
(`:160-194`) is `main.py`, `config.py`, two tests, a justfile and hooks. No
`commands/` package exists or is planned. D6 depends only on D1
(`loopctl ledger`: `D6 ... deps: D1-cli-package-skeleton`), so D6 is the
first ticket to add a sub-command and must own that decision itself rather
than cite it as inherited.

### P8 — an installed `localstack` can read `group_vars/all.yml` at run
time. UNCERTAIN.

R1 (`:112-116`) forbids copying the versions into Python, so the file must
be read at run time, from a CLI a developer installs and may run from any
directory. Nothing in D6 or D1 says how the CLI finds the repo root. D1's
`config.py` holds three cluster addresses and nothing else
(`.loop/plans/D1-cli-package-skeleton.md:173-176`), and D1's install
recommendation is `uv tool install --editable ./cli`
(`:305-308`), which happens to leave the source in the working tree and
makes a `__file__`-relative walk possible. That is an accident of the
install mode, not a stated mechanism, and it fails for a non-editable
install or a copy of the CLI outside the checkout. The plan needs to say
how the path resolves and what happens when it cannot.

### P9 — the eval rows are testable as written. Mixed.

- **Row 7, "the shim cannot call itself" (`:35`): testable.** My probe
  counted exactly one invocation of the real binary using a counter script,
  with the shim dir first on PATH, which is precisely what the row asks
  for. It is only testable if the real-binary path recorded at install time
  can be pointed at a fixture during the test; no requirement in the plan
  creates that seam. Add one.
- **Row 6, "falls through when `localstack token` fails" (`:34`): testable
  but leaky.** This devcontainer already exports a real `NOMAD_TOKEN` (my
  fall-through runs showed the real binary receiving
  `8acca0d8-…` from the ambient environment). The row's "with no token
  injected" assertion will read as a pass or a fail depending on the
  developer's shell unless the test clears `NOMAD_TOKEN` first.
- **Row 1's grep (`:29`) is mis-scoped.** `grep -rnE '2\.0\.[0-9]' cli/
  --include='*.py'` covers `cli/tests/`, so a legitimate test asserting a
  resolved version literal trips the row. Scope it to `cli/src/`.
- Rows 8 and 5 depend on the P6 layout being settled; row 8 is currently
  unsatisfiable (see P6).

### P10 — anchors and gates. HOLD.

- `D2 §12` resolves: `.loop/plans/D2-cli-login-broker-tokens.md:662`
  (`## 12. Design locked, 2026-07-31`); the CLI table is at `:684-688` and
  the shim contract at `:694-701`. D6 quotes both accurately.
- The stated gates exist: `justfile:18` (`pre_commit`) and `justfile:30`
  (`worktree_setup`), matching the eval's gate rows.
- The drift claim in "Triggered by" checks out: `consul version` reports
  2.0.1 against a 2.0.2 pin, `nomad version` reports 2.0.3 against a 2.0.4
  pin, `vault` 2.0.3 matches.

## Most dangerous assumption

**P6.** Everything else in this plan is verified true. If the pinned
binaries and the `nomad` shim both land in `~/.localstack/bin`, then
enabling shims replaces the pinned Nomad CLI with a script that runs the
unpinned system one, and the ticket ships a `nomad` that is *more* drifted
than before `deps` ran, while every eval row still scores green.

## Required fixes before this plan is `ready`

1. **Settle the layout fork (P6).** Decide, in Open Questions with a
   recommendation, where the pinned binaries live versus where the shims
   live, and what the shim execs. The obvious answer is that the shim must
   exec the **pinned** binary `deps` installed, at a path that is not the
   shim's own (for example binaries in `~/.localstack/tools/`, shims in
   `~/.localstack/bin/`). Whatever is chosen, state it in R4, R7 and the
   shim contract, and note that D2 §12's `/usr/bin/nomad` literal is
   superseded for this repo.
2. **Re-score eval rows 7 and 8 against that layout.** Row 8's "installed
   CLI binaries are not removed" is unsatisfiable while shim and binary
   share a path. The marker is signed off, so this is an operator edit, not
   an implementer's judgment call.
3. **Say how many shims `--with-shims` writes.** The table says `nomad`
   only; R5 and eval row 8 say "them" and "every shim written". One
   sentence settles it.
4. **State how the CLI locates `group_vars/all.yml` at run time (P8)**, and
   what it does when it cannot: a repo-root walk from `__file__`, a
   `--repo-root` flag, or a documented "run from the checkout" constraint.
   Add the failure message to R1.
5. **Correct the D1 ownership claim (P7).** D1 bans typer sub-groups, so
   D6 introduces the first one. Either name `commands/` as D6's own
   addition in the code surface or drop the `commands/deps.py` path.
6. **Name the YAML dependency.** D1's runtime dependency is `typer` alone
   (`.loop/plans/D1-cli-package-skeleton.md:121-123`). Parsing the file
   needs `pyyaml` added with `uv add`, plus `types-PyYAML` for the mypy
   hook. Neither appears in D6's code surface.
7. **Fix eval row 1's grep scope** to `cli/src/` and **clear `NOMAD_TOKEN`
   in the row 6 test**, which otherwise inherits a real token from the
   devcontainer environment.
8. **Optional but cheap:** note that the shim should not export an empty
   `NOMAD_TOKEN` when `localstack token` succeeds with empty output, and
   that `deps` is pinned against Nomad 2.0.4 while the no-token-file fact
   was measured on 2.0.3.

## Briefing gap

The briefing named the pass id (`plan-validator`) and the verdict path, but
supplied no plan fingerprint. I computed the sha256 of the plan file at the
given path and recorded it above rather than binding a hash I was not given.
Because this verdict is a `fail`, no `plan:` line is written and no flip to
`ready` can be authorized by it. If a later pass returns a passing verdict,
the dispatcher must supply the fingerprint explicitly.
