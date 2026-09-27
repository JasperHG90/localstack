FROM  jhginn/devcontainer:ubuntu2404-pyuv312-latest-gcloud

ENV RUFF_CACHE_DIR=$HOME/workspace/.cache/ruff
ENV PRE_COMMIT_HOME=$HOME/workspace/.cache/pre-commit
ENV ANSIBLE_GALAXY_CACHE_DIR=$HOME/workspace/.cache/ansible-galaxy

RUN pipx install --force uv==0.11.16

WORKDIR /home/vscode

# The base image already ships /etc/apt/sources.list.d/hashicorp.list and a
# keyring holding AA16FCBCA621E701. HashiCorp rotated to FC9CA96ACA026560, so
# the very first `apt-get update` fails with `NO_PUBKEY` before anything can
# refresh the key. Replace the key first, then update.
#
# ADD, not `wget | gpg --dearmor` inside the RUN, for two reasons: BuildKit
# re-reads the URL every build and keys the layer on its content, so the next
# rotation busts the cache instead of baking a stale key in; and a failed fetch
# fails the build, where the old pipeline wrote an empty keyring and exited 0.
# apt reads the armored key directly, so no dearmor step and no `.gpg` file.
ADD --chmod=644 https://apt.releases.hashicorp.com/gpg /usr/share/keyrings/hashicorp-archive-keyring.asc

RUN sudo rm -f /usr/share/keyrings/hashicorp-archive-keyring.gpg && \
  echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.asc] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list && \
  sudo apt-get update && \
  sudo apt-get install -y wget gpg coreutils nomad vault consul && \
  rm -rf /var/lib/apt/lists/*

USER vscode

RUN uv tool install pre-commit
RUN uv tool install ansible-core
RUN uv tool install ansible-lint
RUN uv tool install ansible
RUN sudo chown -R vscode:vscode /home/vscode/.local/share/uv/tools/

# From GitHub releases, not dl.min.io: MinIO retired that host and every
# path under it now answers 410 Gone.
RUN wget -O mc https://github.com/minio/mc/releases/download/RELEASE.2025-08-13T08-35-41Z/mc.linux-arm64.RELEASE.2025-08-13T08-35-41Z && \
  chmod +x mc && \
  sudo mv mc /usr/local/bin/

RUN curl -L https://github.com/golang-migrate/migrate/releases/download/v4.19.0/migrate.linux-arm64.tar.gz | tar xvz && \
  sudo mv migrate /usr/local/bin/

RUN curl -fsSL --retry 5 --retry-delay 10 --retry-all-errors https://claude.ai/install.sh | bash

# Install rtk
RUN curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh

# Install codegraph
RUN curl -fsSL https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh | sh

# Install clx
RUN curl -fsSL https://raw.githubusercontent.com/JasperHG90/clx/main/install.sh | bash

# Install openviking
RUN uv tool install openviking

# Install aim
RUN uv tool install git+https://github.com/JasperHG90/agent-integrations-manager.git

# Install loop engineering harness control CLI
#RUN uv tool install git+https://github.com/JasperHG90/loop-engineering-harness.git

# Install ovx
RUN uv tool install ovx --from "git+https://github.com/JasperHG90/openviking_extensions@ovx-v0.4.0#subdirectory=packages/ovx"

# Shims first, then the pinned binaries, then the system. `localstack deps`
# writes both directories and never writes to one what belongs in the other.
# A bare `nomad`, `consul` or `vault` finds its shim, which execs the pinned
# binary. Anything unshimmed still gets the pinned version, because `bin`
# sits ahead of the system too. PATH only: no token variable belongs here,
# and Consul's token-file variable least of all, since it outranks the token
# the shim exports and nothing writes the file it names.
ENV PATH="$HOME/.localstack/shims:$HOME/.localstack/bin:$HOME/.local/bin:$PATH"
