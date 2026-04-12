#!/bin/bash

set -e

echo "Configuring development container..."

# Symlink macOS home path so Claude Code plugins resolve correctly.
# ~/.claude is bind-mounted from the Mac host, so installed_plugins.json
# contains macOS paths (<REDACTED_HOST_HOME>/...) that don't exist in the container.
if [ ! -d "<REDACTED_HOST_HOME>" ]; then
  sudo mkdir -p <REDACTED_HOST_HOME>
  sudo ln -sf /home/vscode/.claude <REDACTED_HOST_HOME>/.claude
fi

mc alias set minio "${AWS_ENDPOINT_URL_S3}" "${AWS_ACCESS_KEY_ID}" "${AWS_SECRET_ACCESS_KEY}"

alias ansible='uv tool run --from=ansible-core ansible'

alias j='just'
