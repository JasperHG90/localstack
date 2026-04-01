FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git jq \
    && rm -rf /var/lib/apt/lists/*
ARG VERSION=0.5.5
RUN curl -fsSL "https://github.com/RightNow-AI/openfang/releases/download/v${VERSION}/openfang-aarch64-unknown-linux-gnu.tar.gz" \
    | tar xz -C /usr/local/bin openfang
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"
RUN uv python install 3.12 && ln -s $(uv python find 3.12) /usr/local/bin/python3
RUN printf '#!/bin/sh\necho "username=x-access-token"\necho "password=$GIT_AUTH_TOKEN"\n' > /usr/local/bin/git-credential-env && chmod +x /usr/local/bin/git-credential-env
RUN git config --system credential.helper env
RUN --mount=type=secret,id=git_token \
    GIT_AUTH_TOKEN=$(cat /run/secrets/git_token) uv tool install \
    "memex-cli @ git+https://github.com/JasperHG90/memex.git@v0.0.62a#subdirectory=packages/cli"
VOLUME /data
ENV OPENFANG_HOME=/data
EXPOSE 50051
CMD ["openfang", "start"]
