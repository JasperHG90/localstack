FROM  jhginn/devcontainer:ubuntu2204-pyuv312-latest-terraform

ENV RUFF_CACHE_DIR=$HOME/workspace/.cache/ruff
ENV PRE_COMMIT_HOME=$HOME/workspace/.cache/pre-commit

RUN pipx install --force uv==0.8.17

RUN sudo apt-get update && \
  sudo apt-get install -y wget gpg coreutils && \
  wget -O- -q https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor --yes --batch -o /usr/share/keyrings/hashicorp-archive-keyring.gpg && \
  echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list && \
  sudo apt-get update && \
  sudo apt-get -y install nomad vault consul && \
  rm -rf /var/lib/apt/lists/*

RUN uv tool install pre-commit

RUN wget https://dl.min.io/client/mc/release/linux-amd64/mc && \
  chmod +x mc && \
  sudo mv mc /usr/local/bin/
