# Base: nousresearch/hermes-agent (s6-overlay, v2026.5.16+). /init runs
# cont-init.d as root (UID remap, data-volume chown, config seeding, skills
# sync), then main-wrapper.sh drops the main program to the hermes user via
# s6-setuidgid. That drop needs CAP_SETGID, which the radxa node's Nomad
# podman driver provides — it runs ROOTFUL (driver.podman.rootless=false), so
# the earlier "rootless can't grant CAP_SETGID" concern no longer applies.
# The image therefore stays root (no trailing USER hermes); do NOT pin the
# Nomad task to a non-root UID — the wrapper rejects arbitrary UIDs.
FROM nousresearch/hermes-agent:v2026.7.1

# Install curl + jq for skill-based HTTP/JSON manipulation, plus chromium so the
# agent-browser fallback chain finds a system Chrome for browser_vision /
# screenshot workflows (see issue #8).
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl jq chromium \
    && rm -rf /var/lib/apt/lists/*

# Install Memex common, Hermes plugin, and CLI into the venv (with deps).
# Snapshot site-packages before/after so only NEW package dirs are chowned to
# hermes — a recursive chown of the whole .venv would duplicate ~1.6GB into a
# fresh layer.
RUN set -euo pipefail; \
    sp=/opt/hermes/.venv/lib/python3.13/site-packages; \
    ls -1 "$sp" | sort > /tmp/sp-before; \
    uv pip install --link-mode=copy --python /opt/hermes/.venv/bin/python \
      pip setuptools wheel \
      "https://github.com/JasperHG90/memex/releases/download/v1.0.1/memex_common-1.0.1-py3-none-any.whl" \
      "https://github.com/JasperHG90/memex/releases/download/v1.0.1/memex_hermes_plugin-1.0.1-py3-none-any.whl" \
      "https://github.com/JasperHG90/memex/releases/download/v1.0.1/memex_cli-1.0.1-py3-none-any.whl"; \
    ls -1 "$sp" | sort > /tmp/sp-after; \
    comm -13 /tmp/sp-before /tmp/sp-after | while IFS= read -r d; do \
      chown -R hermes:hermes "$sp/$d"; \
    done; \
    rm /tmp/sp-before /tmp/sp-after

# Stage plugin files for prestart to copy into user plugins dir ($HERMES_HOME/plugins/memex/)
RUN mkdir -p /opt/hermes/memex-plugin && \
    cp -r /opt/hermes/.venv/lib/python3.13/site-packages/memex_hermes_plugin/memex/* /opt/hermes/memex-plugin/ && \
    chown -R hermes:hermes /opt/hermes/memex-plugin

# No trailing `USER hermes`: s6-overlay's /init must run as root so cont-init.d
# can remap/chown, then main-wrapper.sh drops to the hermes user itself.
