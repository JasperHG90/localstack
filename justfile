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

# Install the localstack CLI: a project venv for the IDE, and `localstack` on PATH.
#
# `uv tool install --editable` binds ONE global `localstack` to the checkout it
# was run from. Run this from the primary checkout, not a `.loop/worktrees/`
# one, or the binary points into a directory that gets deleted.
install_cli:
    uv sync --project cli
    uv tool install --editable ./cli
    @echo "installed. run it with: localstack --help"


# Unseal Vault server
unseal_vault:
    bash scripts/unseal_vault.sh

# `git worktree add` checks out tracked files only, so terraform validate
# fails on the missing SSH key before it ever evaluates the change.
# The key is symlinked (one source of truth, so rotations follow); the
# tfvars are copied, so a stray write in a worktree cannot reach the real file.
# `.claude` is symlinked for the same reason as the key: `.gitignore` drops it,
# so a worktree has no `.claude/rules/`, and `loopctl verify-plan` refuses any
# plan that cites one of those rule files.
# Seed a fresh git worktree with the gitignored inputs the gates need
worktree_setup path:
    ln -sfn "$(pwd)/.ssh" "{{ path }}/.ssh"
    cp deployments/infrastructure/vars/prod.tfvars "{{ path }}/deployments/infrastructure/vars/prod.tfvars"
    ln -sfn "$(pwd)/.claude" "{{ path }}/.claude"

# Retrieve all secrets in a namespace
list_secrets namespace:
    vault kv list -mount=secret "{{ namespace }}"

# Get the value for a specific secret
get_secret path:
    vault kv get -mount=secret "{{ path }}"
