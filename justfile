set shell := ["bash", "-uc"]

alias s := setup
alias f := format
alias p := pre_commit
alias u := unseal_vault
alias w := worktree_setup

# Format Nomad job files
format:
    nomad fmt -recursive

# Set up pre-commit hooks
setup:
    pre-commit install

# Run pre-commit checks on all files
pre_commit:
    pre-commit run --all-files

# Unseal Vault server
unseal_vault:
    bash scripts/unseal_vault.sh

# `git worktree add` checks out tracked files only, so terraform validate
# fails on the missing SSH key before it ever evaluates the change.
# The key is symlinked (one source of truth, so rotations follow); the
# tfvars are copied, so a stray write in a worktree cannot reach the real file.
# Seed a fresh git worktree with the gitignored inputs the gates need
worktree_setup path:
    ln -sfn "$(pwd)/.ssh" "{{ path }}/.ssh"
    cp deployments/infrastructure/vars/prod.tfvars "{{ path }}/deployments/infrastructure/vars/prod.tfvars"
