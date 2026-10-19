#!/bin/bash

set -e

echo "Configuring development container..."

workspace="${1:-/home/vscode/workspace}"

# Docker creates a named volume owned by root when the image has nothing at the
# mount point, which is the case for cli/.venv under the bind-mounted workspace.
sudo chown -R vscode:vscode \
  /home/vscode/.claude \
  /home/vscode/.cache/uv \
  /home/vscode/.cache/prek \
  "${workspace}/cli/.venv"

if ! mc alias set minio "${AWS_ENDPOINT_URL_S3}" "${AWS_ACCESS_KEY_ID}" "${AWS_SECRET_ACCESS_KEY}"; then
  echo "warning: could not set the minio alias. Check the AWS_* keys in .devcontainer/.env." >&2
fi

alias ansible='uv tool run --from=ansible-core ansible'

alias j='just'

cd "${workspace}"

# The git hook in .git/hooks may still be pre-commit's, which this image no
# longer has. `just setup` replaces it with loopctl's commit gate, which runs
# prek's hook after it.
just setup

# The HashiCorp CLIs at the versions this cluster runs, plus the PATH shims
# that let a bare `nomad`, `consul` or `vault` see a `localstack login`
# session. Shims are opt-in on a laptop and passed here, because this
# container is disposable and a developer's machine is not.
#
# Guarded, because neither step is worth failing container creation over: the
# CLI still works without the pinned binaries, and without the shims the
# CLIs behave exactly as they did before this ran.
if ! (just install_cli && localstack deps --install --with-shims); then
  echo "warning: could not install the pinned CLIs or their shims." >&2
  echo "  Run 'just install_cli && localstack deps --install --with-shims' by hand." >&2
fi
