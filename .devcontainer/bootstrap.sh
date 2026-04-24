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
