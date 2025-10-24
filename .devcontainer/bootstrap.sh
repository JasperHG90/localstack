#!/bin/bash

set -e

echo "Configuring development container..."

mc alias set minio "${MINIO_ENDPOINT}" "${MINIO_ACCESS_KEY}" "${MINIO_SECRET_KEY}"
