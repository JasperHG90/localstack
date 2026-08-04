---
verdict: pass
tree: b0285c012d89f5148d9030c10501b8cd52da307b
---

# Documentation-freshness review: D6-cli-deps-and-shims (cycle 3)

Both required fixes landed and check out against the code. All three advisories
were acted on. The rewritten `ROADMAP.md` passage makes four claims and all four
resolve in this tree. No new drift, in `ROADMAP.md` or anywhere else: every
command, flag, path and env var in the changed docs exists as written.

## Required fix 1: `ROADMAP.md:218-222` (verified)

The locked-decision bullet now reads:

> "**`localstack login` writes `~/.vault-token`** at 0600. That file is inert
> while `VAULT_TOKEN` is set, and this devcontainer sets it for everyone, so
> `vault` gets a shim too. All three CLIs are shimmed, by `localstack deps
> --with-shims`. Removing the injected token is F8's job; until then the shim
> is what works."

Four claims, four anchors:

1. **Inert while `VAULT_TOKEN` is set.** `cli/src/localstack_cli/shims.py:14-16`
   states the precedence from the measurement, and `docs/cli-deps.md:76` and
   `docs/cli-login.md:79-82` say the same. Consistent across all three.
2. **This devcontainer sets it for everyone.**
   `.devcontainer/devcontainer.json:37-40` passes `--env-file
   .devcontainer/.env` on every container, and `.devcontainer/.env.example:10`
   declares `VAULT_TOKEN` as one of the values the reader is told to fill in
   (`README.md:66`). "For everyone" is right: it is a run arg, not a per-shell
   opt-in.
3. **All three shimmed by `localstack deps --with-shims`.**
   `shims.py:33-37` lists `nomad`, `consul` and `vault`; `deps.py:119-121`
   writes `sorted(TOKEN_VARS)` when the flag is passed.
4. **F8 owns removing the injected token.** `ROADMAP.md:103` scopes F8 as
   "Points Terraform's providers at brokered tokens, drops the static ones",
   and `docs/cli-login.md:91` already carried the identical sentence before
   this diff. The ROADMAP now agrees with the doc rather than contradicting it.

The old "It is why the stock `vault` CLI needs no shim" no longer appears
anywhere: `grep` for "no shim" across `docs/`, `README.md`, `ROADMAP.md` and
`AGENTS.md` returns nothing outside `docs/notes/`.

## Required fix 2: `docs/cli-deps.md:34-37` (verified)

> "Any run exits non-zero when the versions still disagree once it is done,
> `--install` included, so a script can tell drift from agreement."

Matches `cli/src/localstack_cli/commands/deps.py:134-138`, where `raise
typer.Exit(1)` sits after both the install loop and `_report`, guarded only by
`if not agreed`. The `--install`-included clause is exactly what the comment at
`:135-137` argues for. The `--remove-shims` early return at `:86-94` never
reaches the report, which the doc does not claim it does. Contract now
described correctly.

## Advisories from cycle 2: all acted on

- **`README.md:76-78`.** Splice gone. "Re-run `localstack deps --install` after
  a version moves in `group_vars`. Creating the container is what triggers it,
  so a restart alone will not fetch new binaries." Two sentences, same meaning,
  still correct against `.devcontainer/devcontainer.json:35-36`.
- **`cli/src/localstack_cli/commands/_common.py:74`** now prints "Or use the
  `vault` shim on PATH (`localstack deps --with-shims`)." The ticket id is gone
  and the string names the command that does the thing.
- **`docs/cli-login.md:106-109`** now reads "That contract is what makes the
  PATH shims safe". No ticket id on a user page. The behavior it describes
  still matches `shims.py:48-51`.

The only surviving "D6" in the CLI is `shims.py:12`, inside a module docstring
recording why `consul` gets the variable and not its `_FILE` form. That is a
comment to a maintainer, not a string printed to a user, and it reads as
provenance rather than a forward reference. No fix wanted.

## Checked for new drift: clean

- **`README.md:68-78`** against the tree. `.devcontainer/bootstrap.sh:30` runs
  `just install_cli && localstack deps --install --with-shims`, wrapped in
  `if ! (...)`, so "on create" (`devcontainer.json:35`), the order, and "both
  steps are guarded" are all accurate. `~/.localstack/bin` and
  `~/.localstack/shims` match `.devcontainer/Dockerfile:46` and
  `install.py:31-32`. `README.md:26` lists `deps` and `main.py:49` registers it,
  so the command table is complete again.
- **`docs/cli-deps.md`** re-walked end to end. The four-place repo-root search
  (`versions.py:53-97`), `--repo-root` / `--install` / `--with-shims` /
  `--remove-shims` (`deps.py:61-80`), `LOCALSTACK_HOME` (`install.py:31-32`),
  the `SHA256SUMS` check before any write (`install.py:109-157`), the PATH
  order (`Dockerfile:46`), the three token variables (`shims.py:33-37`), the
  fall-through on failure and on empty output (`shims.py:48-51`), and
  `bootstrap/inventory/group_vars/all.yml` as the version source
  (`versions.py:20-27`). All resolve.
- **No other doc went stale.** `docs/vault-human-auth.md:138,152` mention
  `~/.vault-token` only as a file `logout` deletes, which this diff does not
  change. No page outside `docs/cli-deps.md`, `docs/cli-login.md` and
  `README.md` describes the CLIs' versions, the shims or the container's
  create-time steps.
- **`cli/pyproject.toml`** adds `pyyaml` and `types-pyyaml`. No doc in this repo
  enumerates the CLI's dependencies, so nothing to update.

## Slop scan on the rewritten passages

`ROADMAP.md:218-222`: zero em dashes, no ` -- `, no smart quotes, no tier-1
slop, no British spellings, no self-narration, wrapped inside 80 characters.
`docs/cli-deps.md:34-37` and `README.md:68-78`: same, all clean. The one
"not just" hit in `docs/cli-login.md:113` is a pre-existing heading this diff
does not touch.

## Advisory (no fix demanded, and none expected at cycle 3)

- **`ROADMAP.md:221` has a semicolon splice**: "Removing the injected token is
  F8's job; until then the shim is what works." Two independent clauses, the
  same pattern cycle 2 raised at `README.md:77` and the author fixed there. A
  period reads identically. Low confidence per the slop rule, which asks that
  splices be surfaced rather than auto-rewritten, and this is a planning
  register rather than a user page.
- **`ROADMAP.md:220`**, "All three CLIs are shimmed, by `localstack deps
  --with-shims`." The comma splits a short clause that does not need splitting.
  Pure style.
- **`ROADMAP.md:337-340`** says F8 "needs a replan of its own". A locked
  decision that hands work to a ticket the same document flags as needing a
  replan is a mild tension, but it is a tension about F8's readiness, not about
  who owns the injected token, and it predates this diff. Not D6's to resolve.
- **`AGENTS.md:110-113`** still presents `just install_cli` as a manual step
  that the container now runs for you. Carried unchanged from cycles 1 and 2.
  It reads as a how-to-run-the-CLI note rather than a claim about the
  container, so it misleads nobody today.
