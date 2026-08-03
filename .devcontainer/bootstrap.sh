#!/bin/bash

set -e

echo "Configuring development container..."

# Symlink the host home path so Claude Code plugins resolve correctly.
# ~/.claude is bind-mounted from the host, so installed_plugins.json
# contains host paths (e.g. /Users/<you>/...) that don't exist in the container.
# Set HOST_HOME in .devcontainer/.env to your host home dir to enable the symlink.
if [ -n "${HOST_HOME:-}" ] && [ ! -d "${HOST_HOME}" ]; then
  sudo mkdir -p "${HOST_HOME}"
  sudo ln -sf /home/vscode/.claude "${HOST_HOME}/.claude"
fi

mc alias set minio "${AWS_ENDPOINT_URL_S3}" "${AWS_ACCESS_KEY_ID}" "${AWS_SECRET_ACCESS_KEY}"

alias ansible='uv tool run --from=ansible-core ansible'

alias j='just'

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
