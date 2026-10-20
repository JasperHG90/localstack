set shell := ["bash", "-uc"]

alias s := setup
alias f := format
alias p := pre_commit
alias u := unseal_vault
alias w := worktree_setup
apm := "uvx --from apm-cli==0.33.0 apm"
kmctl_ref := "v0.12.1"
kmctl_src := "git+https://github.com/JasperHG90/kmctl@" + kmctl_ref
# kmctl at the pinned release, without touching the kmctl on your PATH.
kmctl := "uvx --from " + kmctl_src + " kmctl"

# List the recipes.
default:
    @just --list

# Format Nomad job files
format:
    nomad fmt -recursive

# Set up the git hooks. --overwrite drops a hook pre-commit left behind;
# without it prek keeps that hook as .legacy and still runs it.
# loopctl's commit gate owns pre-commit and runs pre-commit.local after itself.
# On a rerun, loopctl init refuses to move prek's fresh hook onto an existing
# pre-commit.local, so move it there first. A hook type prek installs besides
# pre-commit needs the same move, or it replaces loopctl's hook of that type.
setup:
    prek install --overwrite
    mv -f "$(git rev-parse --git-path hooks)/pre-commit" "$(git rev-parse --git-path hooks)/pre-commit.local"
    loopctl init --yes

# Run pre-commit checks on all files
pre_commit:
    bash scripts/seed_worktree.sh
    prek run --all-files

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
# nothing plans it and nothing reminds you to leave. docs/reference/cluster-roles.md
# is the long form.
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

# --- Vault login MFA ---------------------------------------------------------
#
# Terraform owns the TOTP method and the login enforcement
# (deployments/infrastructure/identity.tf). These recipes own only the
# per-person secret, which Terraform must never hold: that secret is the second
# factor, so keeping it in state would file both factors in one place.
#
# Every trap worth knowing is in scripts/vault_mfa.sh; docs/how-to/roll-out-vault-login-mfa.md
# is the rollout order.

# Show whether Vault login MFA is configured, and on which auth mounts
mfa_status:
    #!/usr/bin/env bash
    set -euo pipefail
    eval "$(localstack env)"
    bash scripts/vault_mfa.sh status

# Enroll a person's authenticator, writing their QR code to tmp/
mfa_enroll username:
    #!/usr/bin/env bash
    set -euo pipefail
    eval "$(localstack env)"
    bash scripts/vault_mfa.sh enroll "{{ username }}"

# Replace a person's authenticator after a lost phone; kills the old one
mfa_reset username:
    #!/usr/bin/env bash
    set -euo pipefail
    eval "$(localstack env)"
    bash scripts/vault_mfa.sh reset "{{ username }}"

# Test the MFA recipes against a fake Vault; touches no real cluster
mfa_test:
    bash scripts/vault_mfa_test.sh

# Set up a fresh clone: the kmctl CLI, the APM dependencies, the knowledge folders.
bootstrap: kmctl kmctl-install kmctl-init

# Install the kmctl CLI on your PATH unless one as new as the pin is there, then fetch the pin.
# The kmctl on PATH runs each project's pinned release, so one install serves every project.
kmctl:
    #!/usr/bin/env bash
    set -euo pipefail
    have=$(KMCTL_PINNED=1 kmctl --version 2>/dev/null | awk '{print $2}') || have=""
    if [ -z "$have" ] || uv run --no-project --quiet --with packaging python -c 'import sys; from packaging.version import Version; sys.exit(0 if Version(sys.argv[1]) < Version(sys.argv[2]) else 1)' "$have" "{{kmctl_ref}}"; then
        uv tool install --force "{{kmctl_src}}"
    fi
    kmctl --version

# Install the APM dependencies in apm.yml for its targets, then what APM cannot install yet.
kmctl-install:
    {{apm}} install
    {{kmctl}} plugin patch

# Install exactly what apm.lock.yaml records (for a clean clone or CI).
kmctl-install-frozen:
    {{apm}} install --frozen
    {{kmctl}} plugin patch

# Fail when a frozen install changes a committed file, such as a hand edit to an installed skill.
# Run it on a clean checkout, as in CI: the install overwrites an uncommitted edit without a word.
check-install: kmctl-install-frozen
    #!/usr/bin/env bash
    set -euo pipefail
    changed=$(git status --porcelain)
    if [ -n "$changed" ]; then
        printf '%s\n' "$changed"
        echo "the committed files above differ from what apm.lock.yaml installs; make the change in the package they come from, and commit what just install-frozen writes" >&2
        exit 1
    fi

# Resolve the dependencies again and rewrite apm.lock.yaml without installing.
apm-lock:
    {{apm}} lock

# Show locked dependencies that have newer versions.
apm-outdated:
    {{apm}} outdated

# Create docs/ and the .okf/ knowledge bundle, and kmctl's block in AGENTS.md (safe to run again).
kmctl-init:
    {{kmctl}} init

# Check the knowledge bundle and that kmctl is installed correctly.
kmctl-check:
    {{kmctl}} check
    {{kmctl}} doctor

# Run `just` again rather than depending on recipes, so the second step reads the rewritten justfile.
# Move to another kmctl release, such as v0.5.0: rewrite the pinned files, then reinstall at it.
kmctl-upgrade ref:
    uvx copier update --defaults --data kmctl_ref={{ref}}
    just kmctl-install install
