# Base: nousresearch/hermes-agent (s6-overlay, v2026.5.16+). /init runs
# cont-init.d as root (UID remap, data-volume chown, config seeding, skills
# sync), then main-wrapper.sh drops the main program to the hermes user via
# s6-setuidgid. That drop needs CAP_SETGID, which the radxa node's Nomad
# podman driver provides — it runs ROOTFUL (driver.podman.rootless=false), so
# the earlier "rootless can't grant CAP_SETGID" concern no longer applies.
# The image therefore stays root (no trailing USER hermes); do NOT pin the
# Nomad task to a non-root UID — the wrapper rejects arbitrary UIDs.
FROM nousresearch/hermes-agent:v2026.7.30

# Install curl + jq for skill-based HTTP/JSON manipulation, plus chromium so the
# agent-browser fallback chain finds a system Chrome for browser_vision /
# screenshot workflows (see issue #8).
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl jq chromium \
    && rm -rf /var/lib/apt/lists/*

# No memory-provider packages are installed here. OpenViking's provider ships
# inside the base image at /opt/hermes/plugins/memory/openviking and is chosen
# by `memory.provider` in config.yaml, so it needs neither an install nor a
# staging copy into $HERMES_HOME/plugins.

# No trailing `USER hermes`: s6-overlay's /init must run as root so cont-init.d
# can remap/chown, then main-wrapper.sh drops to the hermes user itself.
