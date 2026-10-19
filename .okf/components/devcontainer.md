---
type: component
title: The devcontainer
description: "The devcontainer is the operator's workstation: an arm64 Ubuntu image with Docker-in-Docker for image builds, every variable in .devcontainer/.env injected into every process, and a PATH that puts the CLI's shims and pinned HashiCorp binaries ahead of the unpinned apt ones. A test holds the PATH order."
tags: [devcontainer, docker, tooling, path, tokens]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-10-19
sources:
  - id: dockerfile
    resource: git:3ec5d1e:.devcontainer/Dockerfile
  - id: devcontainer-json
    resource: git:3ec5d1e:.devcontainer/devcontainer.json
  - id: devcontainer-bootstrap
    resource: git:3ec5d1e:.devcontainer/bootstrap.sh
  - id: env-example
    resource: git:3ec5d1e:.devcontainer/.env.example
  - id: devcontainer-path-test
    resource: git:3ec5d1e:cli/tests/test_devcontainer_path.py
  - id: vault-token-file
    resource: git:3ec5d1e:cli/src/localstack_cli/auth/vault_token_file.py
  - id: apps-justfile
    resource: git:3ec5d1e:deployments/applications/justfile
  - id: D2-cli-login-broker-tokens
    resource: loop:D2-cli-login-broker-tokens
  - id: D6-cli-deps-and-shims
    resource: loop:D6-cli-deps-and-shims
---

# The devcontainer

`.devcontainer/` builds the machine every `just` recipe, Terraform run and
Ansible playbook is run from. It matters to a maintainer for three reasons:
it decides which `nomad`, `vault` and `consul` binary runs, it injects
credentials into every process, and it is the only place images are built.

## The image

`Dockerfile` starts from `jhginn/devcontainer:ubuntu2404-pyuv312-latest-gcloud`
and adds:

- `nomad`, `vault` and `consul` from HashiCorp's apt repository, with no
  version pin. These are not the binaries a shell runs (see PATH below).
- `prek`, `ansible-core`, `ansible` and `ansible-lint` as uv tools. prek runs
  the hooks in `.pre-commit-config.yaml`, and `just setup` installs its git
  hook with `--overwrite` so a hook left by pre-commit does not survive as
  `pre-commit.legacy` and fail every commit.
- `loopctl`, pinned to a commit of loop-engineering-harness. `just setup`
  moves prek's hook to `pre-commit.local` and runs `loopctl init`, so
  loopctl's commit gate owns `pre-commit` and runs prek's hook after it. The
  gate refuses every commit when loopctl is not on PATH, and `bootstrap.sh`
  runs `just setup` under `set -e`, so a broken loopctl install stops
  container creation.
- `migrate` and `mc` as arm64 binaries. `mc` comes from GitHub releases,
  because `dl.min.io` answers 410. `cli/src/localstack_cli/platforms.py`
  states the container is `linux_arm64`.
- A set of agent tools (Claude Code, openviking, ovx and others) that
  nothing in the repo's gates depends on.

HashiCorp rotated its apt signing key, and the base image ships the old one,
so the first `apt-get update` failed with `NO_PUBKEY`. The Dockerfile fetches
the key with `ADD` before updating. The comment explains why `ADD`: BuildKit
keys the layer on the fetched content, so the next rotation rebuilds it, and a
failed fetch fails the build instead of writing an empty keyring.

## PATH, and which binary runs

The last line of the Dockerfile sets:

```
PATH="$HOME/.localstack/shims:$HOME/.localstack/bin:$HOME/.local/bin:$PATH"
```

`bootstrap.sh`, the `postCreateCommand`, runs `just install_cli` and then
`localstack deps --install --with-shims`. That fills `~/.localstack/bin` with
the HashiCorp CLIs at the versions in `bootstrap/inventory/group_vars/all.yml`
and writes shims into `~/.localstack/shims`. A bare `nomad` therefore runs the
shim, which runs the pinned binary with the session's token. The apt binaries
are reached only if `deps` failed, and `bootstrap.sh` prints a warning rather
than failing container creation in that case.

`cli/tests/test_devcontainer_path.py` asserts the order: shims before
binaries, both before the system `PATH`, and that `bootstrap.sh` asks for
the shims. It also asserts that no file in
`.devcontainer/` names `CONSUL_HTTP_TOKEN_FILE`, because that variable
outranks the token the shim exports and nothing writes the file.
[The localstack CLI](/components/localstack-cli.md) has the shim rules.

## Credentials in the environment

`devcontainer.json` passes `--env-file .devcontainer/.env` in `runArgs`, so
every variable in that gitignored file is in every process in the container.
`.devcontainer/.env.example` is the tracked list of keys:

- Cluster addresses (`VAULT_ADDR`, `NOMAD_ADDR`, `CONSUL_HTTP_ADDR`). The CLI
  reads these and nothing else for addresses
  (`cli/src/localstack_cli/config.py`).
- Tokens (`VAULT_TOKEN`, `NOMAD_TOKEN`, `CONSUL_HTTP_TOKEN`) and the three
  Vault unseal keys.
- Day-0 bootstrap secrets (`TAILSCALE_AUTH_KEY`, `GITHUB_USER`,
  `GITHUB_PAT`), which the Ansible playbooks read with `lookup('env', ...)`
  ([Ansible bootstrap](/components/bootstrap.md)).
- MinIO, Postgres and registry credentials for the operator's own tools.

The tokens are the trap. When `VAULT_TOKEN` is set, the stock `vault` ignores
`~/.vault-token`. The shim covers a bare `vault`, but anything that bypasses
it (a failed `deps`, a script that calls the binary by path, a library reading
the variable) acts with the injected token, which the example file intends to
be root. `vault_token_file.py` and the `warn_if_environment_shadows` check in
`cli/src/localstack_cli/commands/_common.py` exist to say so. The operator's
local `.env` no longer sets the tokens, so on this machine the session is what
runs. The tracked example, the CLI's warnings and the `shims.py` docstring
still describe the injected-root case as the normal one.

`deployments/applications/justfile` also loads the same file with
`set dotenv-filename := "../../.devcontainer/.env"`. Its `rebuild_*` recipes
need `GITHUB_WRITE_PAT` and `GITHUB_USER` from it, a write-scoped token that
`.env.example` does not list.

## Docker-in-Docker

The `docker-in-docker` feature is there for the `rebuild_*` recipes in
`deployments/applications/justfile`. Each reads its image tag out of
`services.tf` with `grep`, runs `docker build --pull --platform linux/arm64`,
and pushes to `ghcr.io/jasperhg90/`. The tag in `services.tf` is the only
version record, so bump it there before rebuilding.

## Mounts

`devcontainer.json` bind-mounts `~/.config/gcloud`, which the `google`
provider in the infrastructure root uses for the GCS backup bucket, and
`~/.ovx`.

Four named volumes hold state that outlives a rebuild:

- `loop-harness-uv-cache` at `/home/vscode/.cache/uv` and
  `loop-harness-prek-cache` at `/home/vscode/.cache/prek`. The names are the
  loop-engineering-harness devcontainer's, so both containers share one cache
  ([ADR 0013](/decisions/0013-devcontainer-shares-caches-with-loop-harness.md)).
  `UV_CACHE_DIR` and `PREK_HOME` in the Dockerfile point at them, and
  `cli/tests/test_devcontainer_volumes.py` pins both names.
- `localstack-claude` at `/home/vscode/.claude`, with `CLAUDE_CONFIG_DIR`
  pointing there, so Claude Code's login, settings and plugins live in one
  volume of this repository's own.
- `localstack-cli-venv` at `cli/.venv`, which keeps the Linux venv apart from
  the macOS one the bind-mounted workspace would otherwise share.

A new named volume is owned by root when the image has nothing at its mount
point, which is the case for `cli/.venv`. `bootstrap.sh` chowns all four to
`vscode` before anything else runs.
