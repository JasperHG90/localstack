# Base: nousresearch/hermes-agent (s6-overlay, v2026.5.16+). /init runs
# cont-init.d as root (UID remap, data-volume chown, config seeding, skills
# sync), then main-wrapper.sh drops the main program to the hermes user via
# s6-setuidgid. That drop needs CAP_SETGID, which the radxa node's Nomad
# podman driver provides — it runs ROOTFUL (driver.podman.rootless=false), so
# the earlier "rootless can't grant CAP_SETGID" concern no longer applies.
# The image therefore stays root (no trailing USER hermes); do NOT pin the
# Nomad task to a non-root UID — the wrapper rejects arbitrary UIDs.
FROM nousresearch/hermes-agent:v0.22.2

# jq and chromium only: the base already ships curl, but not these two.
# chromium is what lets the agent-browser fallback chain find a system Chrome
# for browser_vision / screenshot workflows (see issue #8). Checked against
# v0.22.2 -- if a later base starts shipping both, this whole custom image
# stops earning its keep and the job can point at the base directly.
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
      jq chromium \
    && rm -rf /var/lib/apt/lists/*

# OpenViking's memory provider left the base image in v0.22.0. Hermes would
# fetch it from GitHub at first start; instead the image carries Volcengine's
# catalog plugin (2.1.1) pinned by commit, in the bundled provider directory
# `memory.provider: openviking` resolves, so no start depends on the network
# (spike:hermes-update/3). A pip install of it does not build, hence the copy.
ARG OPENVIKING_PLUGIN_SHA=9f150ece247ad683494ab172d738023bd6dc6170
RUN mkdir -p /opt/hermes/plugins/memory/openviking \
    && curl -fsSL "https://codeload.github.com/volcengine/OpenViking/tar.gz/${OPENVIKING_PLUGIN_SHA}" \
      | tar xz -C /opt/hermes/plugins/memory/openviking --strip-components=3 \
        "OpenViking-${OPENVIKING_PLUGIN_SHA}/examples/hermes-plugin" \
    && rm -rf /opt/hermes/plugins/memory/openviking/tests \
    && grep -q 'version: 2.1.1' /opt/hermes/plugins/memory/openviking/plugin.yaml

# No trailing `USER hermes`: s6-overlay's /init must run as root so cont-init.d
# can remap/chown, then main-wrapper.sh drops to the hermes user itself.
