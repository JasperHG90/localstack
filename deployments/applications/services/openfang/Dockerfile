FROM rust:1-slim-bookworm AS builder
RUN apt-get update && apt-get install -y pkg-config libssl-dev git && rm -rf /var/lib/apt/lists/*
ARG VERSION=0.5.1
RUN git clone --depth 1 --branch "v${VERSION}" https://github.com/RightNow-AI/openfang.git /src
WORKDIR /src
RUN cargo build --release --bin openfang

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git jq \
    && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"
RUN uv python install 3.12 && ln -s $(uv python find 3.12) /usr/local/bin/python3
COPY --from=builder /src/target/release/openfang /usr/local/bin/openfang
RUN printf '#!/bin/sh\necho "username=x-access-token"\necho "password=$GIT_AUTH_TOKEN"\n' > /usr/local/bin/git-credential-env && chmod +x /usr/local/bin/git-credential-env
RUN git config --system credential.helper env
ARG GIT_AUTH_TOKEN
RUN GIT_AUTH_TOKEN=$GIT_AUTH_TOKEN uv tool install \
    "memex-cli @ git+https://github.com/JasperHG90/memex.git@v0.0.43a#subdirectory=packages/cli"
VOLUME /data
ENV OPENFANG_HOME=/data
EXPOSE 50051
CMD ["openfang", "start"]
