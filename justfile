set shell := ["bash", "-uc"]

alias s := setup
alias f := format
alias p := pre_commit
alias u := unseal_vault

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
