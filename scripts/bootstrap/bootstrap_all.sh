#! /usr/bin/env bash
set -euo pipefail

### Prerequisites Installation ###
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install -y \
    ufw \
    git \
    curl \
    wget \
    gpg \
    podman \
    python3-pip \
    podman-compose \
    avahi-daemon \
    libnss-mdns
