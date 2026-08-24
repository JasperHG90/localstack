# Build context is this directory alone (single directory, matching
# hermes/Dockerfile's shape) -- unlike L3, the backend carries no path
# dependency on cli/ (Requirement 2), so nothing outside this tree is
# needed to build it.
FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv==0.11.16

WORKDIR /build
COPY . /build

# No --no-editable here: that flag existed only to work around cli's
# editable path-dependency .pth pointing at a build-stage-only path (found
# in adversarial review, AR1, under L3). With cli dropped entirely, every
# remaining dependency is an ordinary PyPI package uv never installs in
# editable mode, so the flag would be a no-op citing a cause that no
# longer applies.
RUN uv sync --frozen --no-dev

FROM python:3.12-slim

WORKDIR /app
COPY --from=builder /build/.venv /app/.venv
COPY --from=builder /build/src /app/src

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

EXPOSE 8001
CMD ["python", "-m", "dash_app.main"]
