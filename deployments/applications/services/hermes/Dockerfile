FROM nousresearch/hermes-agent:latest

# Install curl + jq for skill-based HTTP/JSON manipulation
USER root
RUN apt-get update && apt-get install -y --no-install-recommends curl jq && rm -rf /var/lib/apt/lists/*
USER hermes

# Install Memex common, Hermes plugin, and CLI into the venv
RUN uv pip install --no-deps --link-mode=copy --python /opt/hermes/.venv/bin/python \
  "https://github.com/JasperHG90/memex/releases/download/v0.2.0/memex_common-0.2.0-py3-none-any.whl" \
  "https://github.com/JasperHG90/memex/releases/download/v0.2.0/memex_hermes_plugin-0.2.0-py3-none-any.whl" \
  "https://github.com/JasperHG90/memex/releases/download/v0.2.0/memex_cli-0.2.0-py3-none-any.whl"

# Stage plugin files for prestart to copy into user plugins dir ($HERMES_HOME/plugins/memex/)
RUN mkdir -p /opt/hermes/memex-plugin && \
    cp -r /opt/hermes/.venv/lib/python3.13/site-packages/memex_hermes_plugin/memex/* /opt/hermes/memex-plugin/
