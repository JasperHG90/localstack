---
description: Where the Tailscale auth key and the GitHub registry credentials are stored in Vault after day-0, and which playbooks read them.
stale_after: 2027-01-19
sources:
  - resource: bootstrap/playbooks/seed_vault.yml
  - resource: bootstrap/playbooks/configure_tailscale.yml
  - resource: bootstrap/playbooks/configure_podman.yml
  - resource: bootstrap/roles/tailscale/tasks/main.yml
---

# Bootstrap secrets

After day-0 bootstrap, `TAILSCALE_AUTH_KEY`, `GITHUB_USER` and `GITHUB_PAT` are
seeded into Vault KV2 and consumed by Ansible playbooks on day-2+. This page
lists where each one is stored and what reads it.

## Credential flow

```
bootstrap/.env (day-0) → seed_vault.yml → Vault KV2
                                             ↓ (day-2+)
                          configure_tailscale.yml → tailscale up --authkey=...  (manager only)
                          configure_podman.yml    → auth.json on all nodes      (ghcr.io pull)
```

Both reading playbooks check the manager for `/opt/vault/init.json`. When it
exists, they read the secret from Vault with the root token in that file, and
a failed read fails the run. When it does not exist (day-0, before Vault is
initialized), they read the same variables from the environment instead.

## TAILSCALE_AUTH_KEY

| Property | Value |
|---|---|
| Vault path | `bootstrap/tailscale` (field: `auth_key`) |
| Written by | `bootstrap/playbooks/seed_vault.yml` |
| Consumed by | `bootstrap/playbooks/configure_tailscale.yml` → `tailscale` role → `tailscale up --authkey=...` |
| Scope | Manager node only (subnet router for `192.168.2.0/24`). The same playbook stops and disables tailscaled on workers. |
| Notes | Once authenticated, the key isn't needed unless re-authentication is required. The tailscale role skips auth when `BackendState == "Running"`. |

## GITHUB_USER and GITHUB_PAT

| Property | Value |
|---|---|
| Vault path | `bootstrap/github` (fields: `user`, `pat`) |
| Written by | `bootstrap/playbooks/seed_vault.yml` |
| Consumed by | `bootstrap/playbooks/configure_podman.yml` → writes base64-encoded `user:pat` to `auth.json` |
| Host paths | `/home/<user>/.config/containers/auth.json` (rootless), `/root/.config/containers/auth.json` (Nomad driver) |
| Scope | All nodes. Used at runtime by Podman to pull ghcr.io images. Both files are skipped when the user is empty. |
