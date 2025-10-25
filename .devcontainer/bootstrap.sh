#!/bin/bash

set -e

echo "Configuring development container..."

#mc alias set minio "${AWS_ENDPOINT_URL_S3}" "${AWS_ACCESS_KEY_ID}" "${AWS_SECRET_ACCESS_KEY}"

alias ansible='uv tool run --from=ansible-core ansible'

alias j='just'
