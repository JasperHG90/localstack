# Bootstrap secrets

After day-0 bootstrap, `TAILSCALE_AUTH_KEY` and `GITHUB_PAT` are seeded into
Vault KV2 and consumed by Ansible playbooks on day-2+. This page lists where
each one is stored and what reads it.

## Credential flow

```
bootstrap/.env (day-0) → seed_vault.yml → Vault KV2
                                             ↓ (day-2+)
                          configure_tailscale.yml → tailscale up --authkey=...  (manager only)
                          configure_podman.yml    → auth.json on all nodes      (ghcr.io pull)
```

## TAILSCALE_AUTH_KEY

| Property | Value |
|---|---|
| Vault path | `bootstrap/tailscale` (field: `auth_key`) |
| Consumed by | `configure_tailscale.yml` → `tailscale` role → `tailscale up --authkey=...` |
| Scope | Manager node only (subnet router). Workers have tailscaled disabled. |
| Notes | Once authenticated, the key isn't needed unless re-authentication is required. The tailscale role skips auth when `BackendState == "Running"`. |

## GITHUB_PAT

| Property | Value |
|---|---|
| Vault path | `bootstrap/github` (fields: `user`, `pat`) |
| Consumed by | `configure_podman.yml` → writes base64-encoded auth to `auth.json` |
| Host paths | `/home/<user>/.config/containers/auth.json` (rootless), `/root/.config/containers/auth.json` (Nomad driver) |
| Scope | All nodes. Used at runtime by Podman to pull ghcr.io images. |
