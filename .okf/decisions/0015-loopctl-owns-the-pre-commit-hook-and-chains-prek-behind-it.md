---
type: decision
title: "ADR 0015: loopctl owns the pre-commit hook and chains prek behind it"
description: "The loop harness's commit gate owns .git/hooks/pre-commit and runs prek's hook as pre-commit.local, and the devcontainer installs a pinned loopctl so the gate survives a rebuild."
tags: [adr, decision, devcontainer, loopctl, prek, git-hooks]
generated:
  by: process:kmctl/0.10.0
  at: 2026-10-19T15:15:06Z
status: stable
sources:
  - resource: "justfile"
  - resource: ".devcontainer/Dockerfile"
  - resource: ".devcontainer/bootstrap.sh"
---

# ADR 0015: loopctl owns the pre-commit hook and chains prek behind it

## Context

The repository moved to loopctl 2.2 of the loop-engineering-harness on
2026-10-19. `loopctl init` installs five git hooks. Its `pre-commit` refuses a
commit whose tree has no green stamp, then runs `pre-commit.local`. All five
fail closed: they refuse every commit when `loopctl` is not on PATH.

`.devcontainer/bootstrap.sh` runs `just setup` on every container create, and
`just setup` ran `prek install --overwrite` (ADR 0013). That replaced
loopctl's `pre-commit` with prek's, so after a rebuild the commit gate was
gone. The image did not install loopctl either, so the four hooks prek leaves
alone would have refused every commit.

## Decision

loopctl's commit gate owns `.git/hooks/pre-commit`, and prek's hook runs
after it as `pre-commit.local`. `just setup` runs `prek install --overwrite`,
moves the hook prek wrote to `pre-commit.local`, then runs `loopctl init
--yes`. The move is needed because on a rerun `loopctl init` refuses to put a
foreign `pre-commit` onto an existing `pre-commit.local`. The Dockerfile
installs loopctl pinned to commit `d843196`, the build this setup was tested
against.

Rejected: prek owns `pre-commit` and loopctl is not installed in the image.
That keeps container creation free of loopctl, but commits skip the gate that
checks a tree was stamped green, which is the point of running the loop.

Rejected: an unpinned loopctl install. A fresh build would take whatever is
on the harness's `main` that day, and `.loop/config.toml` follows loopctl's
schema, so a breaking change would stop container creation or every commit.

## Consequences

- loopctl is a hard dependency. `bootstrap.sh` runs `just setup` under
  `set -e`, so a broken loopctl install stops container creation.
- Upgrading loopctl means changing the pin in `.devcontainer/Dockerfile` and
  checking `.loop/config.toml` with `loopctl doctor`.
- prek installs only `pre-commit` today, because `.pre-commit-config.yaml`
  sets no `default_install_hook_types`. Adding another hook type there, such
  as `commit-msg`, needs the same move in `just setup`, or prek replaces
  loopctl's hook of that type.
- This amends the `just setup` consequence of ADR 0013: setup still runs
  `prek install --overwrite`, but prek's hook no longer owns `pre-commit`.
