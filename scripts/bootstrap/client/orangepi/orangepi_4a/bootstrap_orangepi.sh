#! /usr/bin/env bash
set -euo pipefail

sudo usermod -aG systemd-journal localstack
newgrp systemd-journal

sudo apt-get update
sudo apt-get install -y \
    uidmap \
    fuse-overlayfs \
    slirp4netns
