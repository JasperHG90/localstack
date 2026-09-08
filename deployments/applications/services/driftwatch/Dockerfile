# Build context is this directory alone, the same shape dash's backend uses.
# Nothing outside this tree is needed to build it.
FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv==0.11.16

WORKDIR /build
COPY . /build

RUN uv sync --frozen --no-dev

FROM python:3.12-slim

WORKDIR /app
COPY --from=builder /build/.venv /app/.venv
COPY --from=builder /build/src /app/src

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

# The goldset is NOT baked in. It is rendered into the job from
# services/driftwatch/goldset.jsonl (services.tf), so changing the canary set
# is a terraform apply rather than a rebuild and a push. Same reason dash
# takes tiles.json and embark takes models.json that way.
EXPOSE 8010
CMD ["python", "-m", "driftwatch.main"]
