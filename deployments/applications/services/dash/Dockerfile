# Build context is the REPO ROOT, not this directory: the app depends on
# cli/ via a uv path dependency, so both trees must be present in the
# build. deployments/applications/justfile's rebuild_dash recipe `cd`s to
# the repo root before invoking this build for exactly that reason -- `just`
# otherwise pins a recipe's cwd to its own justfile's directory.
FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv==0.11.16

WORKDIR /build
COPY cli /build/cli
COPY deployments/applications/services/dash/app /build/deployments/applications/services/dash/app

# The path dependency in pyproject.toml is relative to this directory
# (../../../../../cli), so the copy above preserves the same relative
# depth from the repo root as the source tree.
#
# --no-editable is required. pyproject.toml declares the cli dependency
# editable (the right mode for local development against a live checkout),
# but an editable install lands as a .pth file pointing at this stage's
# absolute /build/cli path -- copying only .venv and src into the final
# stage below leaves that .pth pointing at a path that does not exist
# there, and `import localstack_cli` fails at container runtime (found in
# adversarial review, AR1: reproduced by building and running this exact
# image). --no-editable installs cli as a real copy inside .venv instead,
# so the final stage is self-contained.
WORKDIR /build/deployments/applications/services/dash/app
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim

WORKDIR /app
COPY --from=builder /build/deployments/applications/services/dash/app/.venv /app/.venv
COPY --from=builder /build/deployments/applications/services/dash/app/src /app/src

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

EXPOSE 8000
CMD ["python", "-m", "dash_app.main"]
