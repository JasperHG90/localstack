FROM nousresearch/hermes-agent:latest

# Install Memex Hermes plugin + dependency into the venv
RUN uv pip install --no-deps --link-mode=copy --python /opt/hermes/.venv/bin/python \
  "https://github.com/JasperHG90/memex/releases/download/v0.1.12/memex_common-0.1.12-py3-none-any.whl" \
  "https://github.com/JasperHG90/memex/releases/download/v0.1.12/memex_hermes_plugin-0.1.12-py3-none-any.whl"
