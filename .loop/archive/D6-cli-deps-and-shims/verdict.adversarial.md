---
verdict: pass
tree: b0285c012d89f5148d9030c10501b8cd52da307b
---

# Adversarial review: D6-cli-deps-and-shims (cycle 3, re-bind)

This is a re-bind of the cycle-2 `pass` onto a new fingerprint, not a
re-litigation. I confirmed the delta is exactly what I was told it was,
re-ran all three gates, and re-proved by execution the two properties I
proved at cycle 2.

## Deterministic floor

`loopctl verify-eval-substance D6-cli-deps-and-shims` returns `valid`
(exit 0). No grep-greens-on-a-comment defect, no stale `depends_on`, no
dropped amendment check. Proceeded to the semantic pass.

## The delta is exactly the seven files claimed

`git diff 3dd161a3 b0285c01` returns 7 files, 17 insertions, 12 deletions:
`.devcontainer/Dockerfile`, `README.md`, `ROADMAP.md`,
`cli/src/localstack_cli/commands/_common.py`, `cli/tests/conftest.py`,
`docs/cli-deps.md`, `docs/cli-login.md`. Nothing else moved. No source
module, no test file body, no `pyproject.toml`, no `uv.lock`.

I also confirmed the fingerprint binds the tree I actually read. Rebuilding
a tree from the full worktree (tracked plus untracked) and diffing it
against `b0285c01` yields additions under `.loop/` only, so every path
outside `.loop/` matches the given fingerprint byte for byte.

## Gates, re-run independently

| Gate | Result |
|------|--------|
| `just pre_commit` | exit 0. All 14 hooks Passed, including Ruff lint, Ruff format, Mypy (strict, cli/) and Pytest (cli/) |
| `loopctl verify` | `ok`, exit 0 |
| `cd cli && uv run pytest` | 291 passed, 7 deselected — same count as cycle 2, so nothing was dropped or skipped |

## The two properties I proved by execution at cycle 2, re-proved

**Zero non-loopback socket attempts across the full run.** I re-instrumented
`socket.getaddrinfo`, `socket.create_connection` and `socket.socket.connect`
from a plugin loaded ahead of the repo conftest (`-p netprobe`). The full
default suite produced **672 socket events, all loopback, zero non-loopback**.

The instrument is not silently broken: a deliberate leak recorded all three
event kinds, including the resolved address behind the DNS name.

```
create_connection ('vault.lab.orangecluster.nl', 443)
getaddrinfo       ('vault.lab.orangecluster.nl', 443)
connect           ('192.168.2.30', 443)
```

The `cli/tests/conftest.py` edit is inside the `no_outbound_network`
docstring only (`:69-70`). The guard body at `:78-83` is untouched, and the
measurement above confirms it still holds.

**The shim rows are still non-vacuous.** I re-derived this by mutation
rather than trusting cycle 2, running the real tests against a shadowed
copy of `localstack_cli.shims` on `PYTHONPATH`:

- Mutation A, drop both fall-throughs (`|| exec "$REAL" "$@"` becomes
  `|| exit 7`), which is the row-7 failure mode: **9 failed**, three tests
  times all three tools —
  `test_the_shim_falls_through_when_the_broker_fails`,
  `test_the_shim_falls_through_on_an_empty_token`,
  `test_an_ambient_token_survives_a_broker_that_gives_nothing`.
- Mutation B, exec `/usr/bin/{tool}` instead of the pinned absolute literal,
  which is the row-8 failure mode: **14 failed**, including
  `test_the_shim_does_not_reach_a_system_binary` and
  `test_the_shim_injects_the_token_and_calls_the_pinned_binary_once`.

Rows 7, 8 and 9 all go red against code that gets them wrong. Non-vacuous.

## The `_common.py` edit breaks nothing

`cli/src/localstack_cli/commands/_common.py:74` now reads
"Or use the `vault` shim on PATH (`localstack deps --with-shims`)."

No test asserts on that line. The three tests that exercise
`warn_if_environment_shadows` assert only on
`"VAULT_TOKEN is set in this shell"`
(`cli/tests/commands/test_auth_commands.py:159,176,181`), which the diff did
not touch. The suite confirms it: 291 passed, unchanged.

The command it names is correct. `commands/deps.py:121` calls
`write_shims(sorted(TOKEN_VARS), ...)` and `shims.py:33-37` puts `vault` in
`TOKEN_VARS`, so `--with-shims` does write the `vault` shim. If the binaries
are absent, `shims.py:79` names `localstack deps --install` as the fix,
which is cycle-1 fix 4 closing the chain.

The remaining `D6` mentions outside `.loop/` are a source comment
(`shims.py:12`) and a test docstring
(`cli/tests/commands/test_token_command.py:1`), neither of which reaches a
user. `ROADMAP.md`'s ticket IDs belong there.

## The `ROADMAP.md` locked-decision rewrite is justified and accurate

Editing a section headed "Decisions locked, do not reopen without cause" is
the one change here that deserved scrutiny. It holds:

- **The decision itself did not move.** The bullet still says
  `localstack login` writes `~/.vault-token` at 0600. Only its rationale
  clause changed, and the old clause ("It is why the stock `vault` CLI needs
  no shim") was a claim D6's own measurement falsified. Correcting a false
  rationale is cause; the eval marker
  (`.loop/evals/D6-cli-deps-and-shims.md:56-58`) already carried the
  correction, so the ROADMAP was the stale copy.
- **Every factual claim in the replacement checks out.**
  "`~/.vault-token` is inert while `VAULT_TOKEN` is set" and "this
  devcontainer sets it for everyone" match `shims.py:14-16` verbatim in
  substance, and the mechanism is real: `devcontainer.json` `runArgs` passes
  `--env-file .devcontainer/.env`, and `.devcontainer/.env.example:10`
  carries `VAULT_TOKEN`. "All three CLIs are shimmed, by `localstack deps
  --with-shims`" matches `TOKEN_VARS` and `deps.py:121`.
- **The forward assignment to F8 is not invented.**
  `.loop/plans/F8-foundation-deployer-provider-cutover.md:280-281` and
  `:407` both list removing the root `VAULT_TOKEN` from
  `.devcontainer/.env.example` as F8 work, and `ROADMAP.md:110` already
  routes F8 as "retires the root token".

## The `docs/cli-deps.md` correction matches the code

`deps.py:117` computes `agreed` **after** the install loop, and `:134-138`
raises `typer.Exit(1)` unconditionally on disagreement. So "Any run exits
non-zero when the versions still disagree once it is done, `--install`
included" is right, and the old "A plain `deps` exits non-zero when anything
drifts" was wrong by omission. This is also what
`test_an_install_that_does_not_settle_still_exits_non_zero` scores.

## Slop spot-check on the delta

No em dash on any added line. `README.md`, `docs/cli-deps.md` and
`docs/cli-login.md` are now free of prose semicolon splices outside code.
The three splices I flagged at cycle 2 (`README.md:77`,
`.devcontainer/Dockerfile:40`, `cli/tests/conftest.py:69`) are all gone, and
each rewrite reads cleanly rather than just swapping punctuation.

---

## Findings

Both are LOW. Neither blocks the commit. My cycle-2 LOW findings 1, 2, 4 and
5 stand unchanged and are not repeated here.

### 1. LOW — the ROADMAP fix introduced one new semicolon splice

`ROADMAP.md:221` — "Removing the injected token is F8's job; until then the
shim is what works." Two independent clauses joined by a semicolon, the same
shape the pass fixed in three other files. The repo's own
`.claude/rules/slop-scan-for-docs.md` says surface rather than auto-rewrite,
so I am surfacing it. A period or "and" reads the same. Net across the delta
is still three splices removed for one added.

### 2. LOW — "Any run" in `docs/cli-deps.md:34` is very slightly over-broad

The sentence sits under a code block that lists four modes, and
`--remove-shims` is not one of the runs it describes: `deps.py:86-94`
returns before resolving versions at all, so that mode always exits zero.
The claim is exactly right for the two modes it is about (`deps` and
`--install`), which is the correction that was asked for. Nobody scripts
`--remove-shims` expecting a drift exit code, so this is a note, not a
required fix.

## Summary

Nothing regressed. The delta is the seven files claimed and nothing more.
All three gates pass at the same test count as cycle 2. The suite is still
provably offline at both the DNS and the connect layer, measured with an
instrument I proved records a real leak. The shim rows still go red under
mutation, so they remain non-vacuous. The `_common.py` string edit touches
no assertion, and the command it now names is the command that writes the
shim. The one edit to a locked decision is a correction of a rationale that
D6 measured false, every claim in the replacement is grounded in code or
config I read, and the F8 hand-off is a real F8 task. Re-bound to
`b0285c012d89f5148d9030c10501b8cd52da307b`. Ship it.
