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

# Break-glass: join the Vault `admin` group for an incident, and leave after.
#
# `admin` membership is deliberately outside Terraform
# (deployments/infrastructure/identity.tf, external_member_entity_ids = true),
# so
# nothing plans it and nothing reminds you to leave. docs/cluster-roles.md is
# the long form.
#
# Both recipes REPLACE the whole membership list, because that is the only
# thing the API offers: `identity/group-member-entity-ids` does not exist on
# this Vault and returns `unsupported path`, which reads like a permissions
# error. So each one reads the current members first and edits only your own
# id. Never hand-write the underlying `vault write`.
#
# The grant is live immediately; no re-login is needed, because Vault resolves
# group membership per request rather than at token issuance. `localstack
# whoami` still shows the policies cached at login, so it will look stale.

# Who is in the break-glass admin group, and are you one of them
admin_status:
    #!/usr/bin/env bash
    set -euo pipefail
    eval "$(localstack env)"
    vault read -format=json identity/group/name/admin \
      | python3 -c 'import json,sys; d=json.load(sys.stdin)["data"]; m=d.get("member_entity_ids") or []; me=__import__("subprocess").run(["vault","read","-field=entity_id","auth/token/lookup-self"],capture_output=True,text=True).stdout.strip(); print("members :", m or "(empty)"); print("you     :", me); print("in admin:", me in m)'

# Join the break-glass admin group, preserving everyone already in it
admin_join:
    #!/usr/bin/env bash
    set -euo pipefail
    eval "$(localstack env)"
    me=$(vault read -field=entity_id auth/token/lookup-self)
    [ -n "$me" ] || { echo "your token has no entity; log in as yourself first" >&2; exit 1; }
    current=$(vault read -format=json identity/group/name/admin \
      | python3 -c 'import json,sys; print(",".join(json.load(sys.stdin)["data"].get("member_entity_ids") or []))')
    case ",$current," in *",$me,"*) echo "already in admin; nothing to do"; exit 0;; esac
    vault write identity/group/name/admin \
      member_entity_ids="$(if [ -n "$current" ]; then echo "$current,$me"; else echo "$me"; fi)"
    echo ">> joined admin. LEAVE WHEN DONE: just admin_leave"

# Leave the break-glass admin group, preserving everyone else
admin_leave:
    #!/usr/bin/env bash
    set -euo pipefail
    eval "$(localstack env)"
    me=$(vault read -field=entity_id auth/token/lookup-self)
    [ -n "$me" ] || { echo "your token has no entity; log in as yourself first" >&2; exit 1; }
    remaining=$(vault read -format=json identity/group/name/admin \
      | python3 -c "import json,sys; m=json.load(sys.stdin)['data'].get('member_entity_ids') or []; print(','.join(x for x in m if x != '$me'))")
    vault write identity/group/name/admin member_entity_ids="$remaining"
    echo ">> left admin. Remaining members: ${remaining:-(none)}"

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
    cp deployments/applications/vars/prod.tfvars "{{ path }}/deployments/applications/vars/prod.tfvars"
    ln -sfn "$(pwd)/.claude" "{{ path }}/.claude"

# Retrieve all secrets in a namespace
list_secrets namespace:
    vault kv list -mount=secret "{{ namespace }}"

# Get the value for a specific secret
get_secret path:
    vault kv get -mount=secret "{{ path }}"
