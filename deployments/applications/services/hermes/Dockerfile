FROM nousresearch/hermes-agent:latest

# Install Memex Hermes plugin + dependency into the venv
RUN uv pip install --no-deps --link-mode=copy --python /opt/hermes/.venv/bin/python \
  "https://github.com/JasperHG90/memex/releases/download/v0.1.13/memex_common-0.1.13-py3-none-any.whl" \
  "https://github.com/JasperHG90/memex/releases/download/v0.1.13/memex_hermes_plugin-0.1.13-py3-none-any.whl"

# Stage plugin files for prestart to copy into user plugins dir ($HERMES_HOME/plugins/memex/)
RUN mkdir -p /opt/hermes/memex-plugin && \
    cp -r /opt/hermes/.venv/lib/python3.13/site-packages/memex_hermes_plugin/memex/* /opt/hermes/memex-plugin/
