FROM nousresearch/hermes-agent:latest

# Install curl + jq for skill-based HTTP/JSON manipulation
USER root
RUN apt-get update && apt-get install -y --no-install-recommends curl jq && rm -rf /var/lib/apt/lists/*
USER hermes

# Install Memex Hermes plugin + dependency into the venv
RUN uv pip install --no-deps --link-mode=copy --python /opt/hermes/.venv/bin/python \
  "https://github.com/JasperHG90/memex/releases/download/v0.1.13/memex_common-0.1.13-py3-none-any.whl" \
  "https://github.com/JasperHG90/memex/releases/download/v0.1.13/memex_hermes_plugin-0.1.13-py3-none-any.whl"

# Patch v0.1.13 bug: get_tool_schemas() returns [] before initialize(),
# so Hermes (which queries schemas at registration time, BEFORE init)
# registers the plugin with 0 tools. Force it to always return ALL_SCHEMAS
# unless memory_mode is explicitly 'context'.
RUN sed -i "s/if self._config is None or self._config.memory_mode == 'context':/if self._config is not None and self._config.memory_mode == 'context':/" \
    /opt/hermes/.venv/lib/python3.13/site-packages/memex_hermes_plugin/memex/provider.py

# Stage plugin files for prestart to copy into user plugins dir ($HERMES_HOME/plugins/memex/)
RUN mkdir -p /opt/hermes/memex-plugin && \
    cp -r /opt/hermes/.venv/lib/python3.13/site-packages/memex_hermes_plugin/memex/* /opt/hermes/memex-plugin/
