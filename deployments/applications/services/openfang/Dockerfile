FROM rust:1-slim-bookworm AS builder
RUN apt-get update && apt-get install -y pkg-config libssl-dev git && rm -rf /var/lib/apt/lists/*
ARG VERSION=0.5.1
RUN git clone --depth 1 --branch "v${VERSION}" https://github.com/RightNow-AI/openfang.git /src
WORKDIR /src
RUN cargo build --release --bin openfang

FROM debian:bookworm-slim AS base
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*

FROM base AS server
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git \
    && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"
RUN uv python install 3.12
COPY --from=builder /src/target/release/openfang /usr/local/bin/openfang
RUN printf '#!/bin/sh\necho "username=x-access-token"\necho "password=$GIT_AUTH_TOKEN"\n' > /usr/local/bin/git-credential-env && chmod +x /usr/local/bin/git-credential-env
RUN git config --system credential.helper env
VOLUME /data
ENV OPENFANG_HOME=/data
EXPOSE 50051
CMD ["openfang", "start"]

FROM node:22-slim AS whatsapp-gateway
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /src/packages/whatsapp-gateway /opt/whatsapp-gateway
WORKDIR /opt/whatsapp-gateway
RUN git config --global url."https://github.com/".insteadOf "ssh://git@github.com/" && npm install --omit=dev
RUN sed -i "s|^import makeWASocket, { useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } from '@whiskeysockets/baileys';|import { makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } from '@whiskeysockets/baileys';|" index.js
EXPOSE 3009
CMD ["node", "index.js"]
