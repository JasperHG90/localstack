---
type: component
title: The devcontainer
description: "The devcontainer is the operator's workstation: an arm64 Ubuntu image with Docker-in-Docker for image builds, every variable in .devcontainer/.env injected into every process, and a PATH that puts the CLI's shims and pinned HashiCorp binaries ahead of the unpinned apt ones. A test holds the PATH order."
tags: [devcontainer, docker, tooling, path, tokens]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
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

This page describes the working tree on 2026-09-27, which carries
uncommitted operator edits to `Dockerfile` and `devcontainer.json`. The
`sources` above pin the committed versions, so every uncommitted change is
marked in the text. Re-check those paragraphs once the edits are committed or
dropped.

## The image

`Dockerfile` starts from `jhginn/devcontainer:ubuntu2404-pyuv312-latest-gcloud`
and adds:

- `uv` pinned to 0.11.16 through pipx.
- `nomad`, `vault` and `consul` from HashiCorp's apt repository, with no
  version pin. These are not the binaries a shell runs (see PATH below).
- `pre-commit`, `ansible-core`, `ansible` and `ansible-lint` as uv tools.
- `migrate` as an arm64 binary, and `mc`, whose architecture the uncommitted
  edit below changes. `cli/src/localstack_cli/platforms.py` states the
  container is `linux_arm64`.
- A set of agent tools (Claude Code, openviking, aim, ovx and others) that
  nothing in the repo's gates depends on.

Uncommitted in the working tree:

- HashiCorp rotated its apt signing key, and the base image ships the old
  one, so the first `apt-get update` failed with `NO_PUBKEY`. The edit fetches
  the key with `ADD` before updating. The comment explains why `ADD`: BuildKit
  keys the layer on the fetched content, so the next rotation rebuilds it, and
  a failed fetch fails the build instead of writing an empty keyring.
- `mc` now comes from GitHub releases as `linux-arm64`, because `dl.min.io`
  answers 410. The committed version fetched `linux-amd64`.
- The loop harness install line is commented out.

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
provider in the infrastructure root uses for the GCS backup bucket. The
working tree also mounts `~/.ovx`, and has removed the committed bind mount
of `~/.claude` and the `homelab-claude-plugins` volume. `bootstrap.sh` still
carries the `HOST_HOME` symlink written for that `~/.claude` mount.
