#!/bin/bash

# Configuration for the Insecure Local Registry
REGISTRY_HOST="localstack.local:5000"
CONFIG_FILE="/etc/containers/registries.conf.d/00-localstack-registry.conf"
CONFIG_DIR="/etc/containers/registries.conf.d"

echo "Configuring Podman for Insecure Registry: ${REGISTRY_HOST}"

# --- Step 1: Check for root privileges ---
if [[ $EUID -ne 0 ]]; then
   echo "Error: This script must be run with sudo."
   exit 1
fi

# --- Step 2: Create the configuration directory ---
echo "Creating configuration directory: ${CONFIG_DIR}"
mkdir -p "$CONFIG_DIR"

# --- Step 3: Create the configuration file ---
echo "Writing configuration to ${CONFIG_FILE}"

cat << EOF > "$CONFIG_FILE"
# Podman/containers-image configuration for the localstack development registry.
# This config is necessary because the registry is running over HTTP (insecure)
# and Podman defaults to HTTPS.

# The use of 'insecure = true' tells the client to use plain HTTP.
[[registry]]
location = "${REGISTRY_HOST}"
insecure = true
EOF

echo "Successfully configured ${REGISTRY_HOST} as an insecure registry."
echo "You can now log in using:"
echo "podman login --username=<your-username> ${REGISTRY_HOST}"
echo "Restart the Podman service using 'systemctl --user daemon-reload'"

exit 0
