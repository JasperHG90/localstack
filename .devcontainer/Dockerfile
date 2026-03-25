FROM  jhginn/devcontainer:ubuntu2404-pyuv312-latest-terraform

ENV RUFF_CACHE_DIR=$HOME/workspace/.cache/ruff
ENV PRE_COMMIT_HOME=$HOME/workspace/.cache/pre-commit
ENV ANSIBLE_GALAXY_CACHE_DIR=$HOME/workspace/.cache/ansible-galaxy

RUN pipx install --force uv==0.10.12

USER vscode
WORKDIR /home/vscode

RUN sudo apt-get update && \
  sudo apt-get install -y wget gpg coreutils && \
  wget -O- -q https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor --yes --batch -o /usr/share/keyrings/hashicorp-archive-keyring.gpg && \
  echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list && \
  sudo apt-get update && \
  sudo apt-get -y install nomad vault consul && \
  rm -rf /var/lib/apt/lists/*

RUN uv tool install pre-commit
RUN uv tool install ansible-core
RUN uv tool install ansible-lint
RUN uv tool install ansible
RUN sudo chown -R vscode:vscode /home/vscode/.local/share/uv/tools/
RUN curl https://install.duckdb.org | sh

RUN mkdir -p $HOME/.duckdb
RUN sudo chown -R vscode:vscode /home/vscode/.duckdb

RUN wget https://dl.min.io/client/mc/release/linux-amd64/mc && \
  chmod +x mc && \
  sudo mv mc /usr/local/bin/

RUN curl -L https://github.com/golang-migrate/migrate/releases/download/v4.19.0/migrate.linux-arm64.tar.gz | tar xvz && \
  sudo mv migrate /usr/local/bin/

RUN curl -fsSL https://claude.ai/install.sh | bash

# Install rtk
RUN curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh
ENV PATH="$HOME/.local/bin:$PATH"
