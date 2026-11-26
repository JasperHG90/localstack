---
type: decision
title: "ADR 0013: The devcontainer shares its uv and prek caches with loop-harness by volume name"
description: "The localstack devcontainer mounts the loop-harness-uv-cache and loop-harness-prek-cache volumes, so both containers fill one cache. Hooks run through prek instead of pre-commit. Renaming a volume on either side silently ends the sharing."
generated:
  by: claude-opus/5.5
  at: 2026-10-19
tags: [adr, decision, devcontainer, uv, prek]
status: stable
sources:
  - id: devcontainer
    resource: .devcontainer/devcontainer.json
  - id: dockerfile
    resource: .devcontainer/Dockerfile
  - id: volume-test
    resource: cli/tests/test_devcontainer_volumes.py
---

# ADR 0013: The devcontainer shares its uv and prek caches with loop-harness by volume name

- Status: Accepted
- Date: 2026-10-19

## Context

The operator runs this repository and the loop-engineering-harness repository
in two devcontainers on one Docker host. The harness container already kept
Claude state, the uv cache, the prek cache and its venv in named volumes. The
localstack container kept its pre-commit cache under the workspace bind mount,
had no uv cache volume, and shared `cli/.venv` with the macOS host through the
bind mount. Each rebuild re-downloaded every package and hook environment.

Docker attaches the same named volume to every container that names it, so
sharing a cache costs only agreeing on a name.

## Decision

Mount `loop-harness-uv-cache` at `/home/vscode/.cache/uv` and
`loop-harness-prek-cache` at `/home/vscode/.cache/prek`, the names the harness
already uses. Keep Claude state (`localstack-claude`) and `cli/.venv`
(`localstack-cli-venv`) in volumes of this repository's own. Run the hooks
through prek instead of pre-commit, so the prek cache has something to share.

Rejected: neutral names such as `devcontainer-uv-cache` in both repositories.
They read better here, but they need a matching change in the harness
repository, and the operator chose to leave that repository as it is.

Rejected: keeping pre-commit. Its cache layout is not prek's, so there would
be no hook cache to share.

## Consequences

- The names are a contract with another repository that nothing checks
  across the two. `cli/tests/test_devcontainer_volumes.py` pins this side
  only. A rename in the harness gives this container a new empty cache with
  no error.
- `just setup` runs `prek install --overwrite`. Without the flag, prek keeps
  the hook pre-commit wrote as `pre-commit.legacy` and still runs it, and that
  hook fails once pre-commit is gone from the image.
- Both images use the uv their base image ships, so this Dockerfile no longer
  pins uv. uv keeps each cache format in a versioned bucket (`wheels-v6` for
  uv 0.11.16, `wheels-v7` for 0.13.0), so a pinned uv on one side would write
  beside the other's cache instead of into it. The sharing holds only while
  both images are rebuilt from base images with the same uv.

## Correction, 2026-11-24

[ADR 0015](/decisions/0015-loopctl-owns-the-pre-commit-hook-and-chains-prek-behind-it.md)
changed the `just setup` consequence. Setup still runs
`prek install --overwrite`, but it then moves prek's hook to
`pre-commit.local` and runs `loopctl init --yes`, so loopctl's commit gate
owns `.git/hooks/pre-commit` and runs prek's hook after it (`justfile`,
recipe `setup`).
