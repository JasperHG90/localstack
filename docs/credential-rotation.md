# Credential Rotation: TAILSCALE_AUTH_KEY & GITHUB_PAT

## Overview

After day-0 bootstrap, `TAILSCALE_AUTH_KEY` and `GITHUB_PAT` are seeded into Vault KV2 and consumed by Ansible playbooks on day-2+. This document describes a plan to add a repeatable `just rotate_*` workflow that updates Vault and propagates new values to all consuming locations.

## Current Credential Flow

```
bootstrap/.env (day-0) → seed_vault.yml → Vault KV2
                                             ↓ (day-2+)
                          configure_tailscale.yml → tailscale up --authkey=...  (manager only)
                          configure_podman.yml    → auth.json on all nodes      (ghcr.io pull)
```

### TAILSCALE_AUTH_KEY

| Property | Value |
|---|---|
| Vault path | `bootstrap/tailscale` (field: `auth_key`) |
| Consumed by | `configure_tailscale.yml` → `tailscale` role → `tailscale up --authkey=...` |
| Scope | Manager node only (subnet router). Workers have tailscaled disabled. |
| Notes | Once authenticated, the key isn't needed unless re-authentication is required. The tailscale role skips auth when `BackendState == "Running"`. |

### GITHUB_PAT

| Property | Value |
|---|---|
| Vault path | `bootstrap/github` (fields: `user`, `pat`) |
| Consumed by | `configure_podman.yml` → writes base64-encoded auth to `auth.json` |
| Host paths | `/home/<user>/.config/containers/auth.json` (rootless), `/root/.config/containers/auth.json` (Nomad driver) |
| Scope | All nodes. Used at runtime by Podman to pull ghcr.io images. |

## Why Ansible (Not Nomad Periodic Jobs)

These are **host-level** secrets, not application-level:

- `TAILSCALE_AUTH_KEY` authenticates the `tailscale` systemd daemon on the manager via `tailscale up --authkey` — a container can't do this
- `GITHUB_PAT` is baked into Podman's `auth.json` on the host filesystem — the Nomad Podman driver reads these when pulling images
- Both require SSH access to host filesystems across multiple nodes, which is Ansible's domain

## Why a New Playbook

- `configure_tailscale.yml` has an idempotency guard (`BackendState != "Running"`) that **skips** re-auth — rotation needs `--force-reauth`
- `configure_podman.yml` includes unrelated tasks (lingering, crun config)
- `seed_vault.yml` reads from env vars — rotation should accept CLI args directly

## Proposed Changes

### 1. Create `bootstrap/playbooks/rotate_secrets.yml`

New playbook with three sections, controlled by Ansible tags:

**`always` — Vault pre-flight (runs for all rotations):**
- Check `/opt/vault/init.json` exists, fail if not
- Read root token
- Check Vault is unsealed via `vault status`, fail with "run `just unseal_vault`" if sealed

**`tailscale` tag — Rotate Tailscale auth key:**
- Validate `tailscale_auth_key_new` extra var is provided
- `vault kv put bootstrap/tailscale auth_key=<new>`
- `tailscale up --force-reauth --authkey=<new> --hostname=... --advertise-routes=192.168.2.0/24 --accept-routes`
- Verify `BackendState == "Running"` after re-auth

**`github` tag — Rotate GitHub PAT:**
- Validate `github_pat_new` extra var is provided
- If `github_user_new` not provided, read existing user from Vault
- `vault kv put bootstrap/github user=<user> pat=<new>`
- Propagate to all hosts: write updated `auth.json` to both user and root paths
  - Base64-encoded `user:pat` → `auth.json` (same pattern as `configure_podman.yml`)
  - Vault read delegated to manager, `auth.json` written on all hosts

Key details:
- All secret-handling tasks use `no_log: true`
- `vault_root_token` set in pre-flight play, accessed via `hostvars` in later plays
- GitHub propagation uses `delegate_to` + `run_once` for the Vault read, then runs copy on `hosts: all`

### 2. Modify `bootstrap/justfile`

Add two recipes after `shutdown`:

```just
# Rotate Tailscale auth key in Vault and force re-authentication on manager
rotate_tailscale key: ssh_add
    ansible-playbook playbooks/rotate_secrets.yml --tags tailscale -e "tailscale_auth_key_new={{key}}"

# Rotate GitHub PAT in Vault and propagate auth.json to all nodes
rotate_github pat user="": ssh_add
    #!/usr/bin/bash
    EXTRA_VARS="-e github_pat_new={{pat}}"
    if [ -n "{{user}}" ]; then
        EXTRA_VARS="${EXTRA_VARS} -e github_user_new={{user}}"
    fi
    ansible-playbook playbooks/rotate_secrets.yml --tags github ${EXTRA_VARS}
```

Usage:
```bash
just rotate_tailscale "tskey-auth-newkey123"
just rotate_github "ghp_newpat456"
just rotate_github "ghp_newpat456" "newuser"    # also change username
```

### 3. Modify `bootstrap/.env.example`

Add the missing bootstrap secret placeholders (currently absent):

```
# Bootstrap-only secrets (day-0 seeding; Vault is source of truth after first run)
# Rotate with: just rotate_tailscale <key> / just rotate_github <pat>
TAILSCALE_AUTH_KEY=tskey-auth-xxxxxxxxxxxxxxxxx
GITHUB_USER=xxxxxxxx
GITHUB_PAT=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 4. Modify `.devcontainer/.env.example`

Update comment near the existing bootstrap secrets section:

```
# Bootstrap-only secrets (day-0 seeding — stored in Vault after first bootstrap)
# Rotate with: cd bootstrap && just rotate_tailscale <key> / just rotate_github <pat>
```

## Files Summary

| File | Action |
|---|---|
| `bootstrap/playbooks/rotate_secrets.yml` | Create |
| `bootstrap/justfile` | Modify (add 2 recipes) |
| `bootstrap/.env.example` | Modify (add 3 env vars + comments) |
| `.devcontainer/.env.example` | Modify (add rotation comment) |

## Verification

1. **Dry run**: `ansible-playbook playbooks/rotate_secrets.yml --tags tailscale --check -e "tailscale_auth_key_new=test"` — should pass pre-flight, show planned changes
2. **Tailscale rotation**: `just rotate_tailscale "<new_key>"` — verify Vault updated (`vault kv get bootstrap/tailscale` on manager), verify `tailscale status` shows Running
3. **GitHub rotation**: `just rotate_github "<new_pat>"` — verify Vault updated (`vault kv get bootstrap/github`), verify `auth.json` updated on all nodes, verify `podman pull ghcr.io/jasperhg90/memex:<tag>` works

## Error Handling

| Failure Scenario | Behavior |
|---|---|
| Vault not initialized | Pre-flight fails with clear message |
| Vault is sealed | Pre-flight fails with "run `just unseal_vault` first" |
| Missing CLI argument | Playbook validates extra vars are defined and non-empty |
| Tailscale re-auth fails | Post-auth verification checks `BackendState == "Running"` |
| SSH agent not loaded | Just recipe depends on `ssh_add` |
| Vault write succeeds but propagation fails | Vault already has new secret; re-run same command to retry (idempotent) |
