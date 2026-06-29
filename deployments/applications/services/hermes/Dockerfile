# Pinned to v2026.5.7 — the last tini-based hermes-agent tag. Upstream switched
# to s6-overlay (cont-init.d + s6-applyuidgid) starting v2026.5.16, and
# s6-applyuidgid needs CAP_SETGID which rootless podman on the radxa node
# cannot grant (cap_add is a no-op for caps the host user doesn't itself hold).
# TODO: revisit when base image / Nomad podman config supports s6-overlay.
FROM nousresearch/hermes-agent:v2026.5.7

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
      "https://github.com/JasperHG90/memex/releases/download/v1.0.0rc7/memex_common-1.0.0rc7-py3-none-any.whl" \
      "https://github.com/JasperHG90/memex/releases/download/v1.0.0rc7/memex_hermes_plugin-1.0.0rc7-py3-none-any.whl" \
      "https://github.com/JasperHG90/memex/releases/download/v1.0.0rc7/memex_cli-1.0.0rc7-py3-none-any.whl"; \
    ls -1 "$sp" | sort > /tmp/sp-after; \
    comm -13 /tmp/sp-before /tmp/sp-after | while IFS= read -r d; do \
      chown -R hermes:hermes "$sp/$d"; \
    done; \
    rm /tmp/sp-before /tmp/sp-after

# Stage plugin files for prestart to copy into user plugins dir ($HERMES_HOME/plugins/memex/)
RUN mkdir -p /opt/hermes/memex-plugin && \
    cp -r /opt/hermes/.venv/lib/python3.13/site-packages/memex_hermes_plugin/memex/* /opt/hermes/memex-plugin/ && \
    chown -R hermes:hermes /opt/hermes/memex-plugin

USER hermes
