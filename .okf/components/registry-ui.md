---
type: component
title: registry-ui, the registry browser
description: "How registry-ui is wired: its own job on radxa beside a second oauth2-proxy on 4181, a SQLite store on its own host volume, and a copy of the registry's only credential, which can push. Covers how it split off from dash in L5, what the guard script protects, and that the guard and the backend suite no longer run as pre-commit hooks."
tags: [registry-ui, registry, oauth2-proxy, sqlite, python]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: registry-ui-jobspec
    resource: git:3ec5d1e:deployments/applications/services/registry-ui.hcl
  - id: registry-ui-main
    resource: git:3ec5d1e:deployments/applications/services/registry-ui/backend/src/registry_ui/main.py
  - id: app-services
    resource: git:3ec5d1e:deployments/applications/services.tf
  - id: app-secrets
    resource: git:3ec5d1e:deployments/applications/secrets.tf
  - id: infra-services
    resource: git:3ec5d1e:deployments/infrastructure/services.tf
  - id: infra-secrets
    resource: git:3ec5d1e:deployments/infrastructure/secrets.tf
  - id: infra-oidc
    resource: git:3ec5d1e:deployments/infrastructure/oidc.tf
  - id: oauth2-proxy-registry-ui
    resource: git:3ec5d1e:deployments/infrastructure/services/oauth2-proxy-registry-ui.hcl
  - id: oauth2-proxy-guard
    resource: git:3ec5d1e:scripts/check_oauth2_proxy_guard.py
  - id: registry-ui-commit
    resource: git:7e93194
  - id: hooks-removed
    resource: git:f197702
  - id: L5-landing-registry-tab
    resource: git:3ec5d1e:.loop/plans/L5-landing-registry-tab.md
---

# registry-ui, the registry browser

registry-ui serves `https://registry-ui.lab.orangecluster.nl`: KitOps
ModelKits with their model cards, and container images, read from the cluster
OCI registry. What it shows is `docs/reference/registry-ui.md`. Why the walk
stays cheap and where it stops scaling is `docs/explanation/registry-ui-cost.md`.
This page covers how the parts connect.

## The request path

```
browser -> HAProxy (backend registryui) -> 192.168.2.50:4181 oauth2-proxy-registry-ui
             catch-all            -> 127.0.0.1:8002  frontend (nginx)
             /api/registry exact  -> 127.0.0.1:8003  backend (Starlette)
backend -> https://registry.lab.orangecluster.nl -> HAProxy -> registry on ubuntu:5000
```

The backend reaches the registry through the edge, not port 5000, because
that port admits HAProxy's node alone and TLS ends at the edge. The
path-scoped upstream follows the exact-match rule [dash](/components/dash.md)
depends on, so a new backend route needs its own upstream entry.

## The pieces

**Applications root** (`deployments/applications/`):

- `services/registry-ui.hcl`: group on radxa-dragon-q6a, static ports 8002
  and 8003, tasks `frontend` and `backend`, and the `registry_ui_data`
  volume mounted at `/var/lib/registry-ui`.
- `services/registry-ui/frontend/`: `index.html` and an `nginx.conf` that
  listens on 8002.
- `services/registry-ui/backend/`: its own uv project (`registry_ui`:
  `main.py`, `config.py`, `registry_client.py`, `registry_store.py`,
  `registry.py`, `_http.py`) and its tests.
- `services.tf`: `nomad_job.registry_ui`, with both image tags pinned
  separately and `registry_addr` built from `local.embark_registry`.
- `secrets.tf`: `vault_kv_secret_v2.registry_ui_credentials` at
  `default/registry-ui/registry`.
- `justfile`: `rebuild_registry_ui_frontend` and `rebuild_registry_ui_backend`,
  which read the tags from `services.tf`.

**Infrastructure root** (`deployments/infrastructure/`):

- `services.tf`: `nomad_dynamic_host_volume.registry_ui_data` (radxa,
  1 GiB cap) and `nomad_job.oauth2_proxy_registry_ui`, whose upstreams are
  the loopback literals above.
- `services/oauth2-proxy-registry-ui.hcl`: a copy of dash's proxy jobspec on
  port 4181.
- `secrets.tf`: `oauth2_proxy_registry_ui_oidc_client` and
  `oauth2_proxy_registry_ui_cookie_secret`, copies of dash's proxy values
  under this job's own prefix.
- `oidc.tf`: no client of its own. `local.registry_ui_redirect_url` is a
  second redirect URI on `vault_identity_oidc_client.oauth2_proxy`, so dash
  and registry-ui share one client, one `operators` assignment and one cookie
  secret. They gate different hostnames, so the cookies never collide. The
  `operators` assignment is the only access filter here too, and
  `docs/reference/registry-ui.md` still says any successful login is
  authorized.
- `services/haproxy.hcl`: `backend registryui` to 192.168.2.50:4181.

Apply the infrastructure root first: the host volume must exist before the
job can place, and the proxy's templates block until its KV copies exist.

## Why the copies

Every job with a bare `vault {}` gets the `nomad-workloads` grant, which reads
only `secret/data/default/<job_id>/*`. The first deploy of the second proxy
read `default/oauth2-proxy/*`, got a 403, never rendered its templates and
never registered. Hence the copies under `default/oauth2-proxy-registry-ui/`,
and the same reason for `default/registry-ui/registry`. embark's registry
credential and Bifrost's virtual keys follow the same copy-under-the-consumer
pattern.

## The credential can push

The registry reads an htpasswd file and has one user, `push`
(`vault_kv_secret_v2.registry_auth` in `secrets.tf`). registry-ui's copy
carries that user and its plaintext password. The jobspec, `secrets.tf` and
the reference page all say "read-only use", and that describes the code, not
the credential: the backend never pushes, but its token can. The registry
cannot issue a pull-only user without a second htpasswd entry, and rotating
the password means tainting `random_password.registry_push` and restarting
every job that holds a copy.

## The store and the credential file

The SQLite store and why it keeps the walk cheap are in
`docs/explanation/registry-ui-cost.md`. One wiring fact is not: `create_app`
builds the sweep once, at startup, from the credential file. Nomad does not
start a task until its templates render, and `change_mode = "restart"`
restarts it when the credential changes, so the process never has to notice
a new password by itself.

## The auth-exemption guard

`scripts/check_oauth2_proxy_guard.py` refuses `OAUTH2_PROXY_SKIP_AUTH_ROUTES`,
`_SKIP_AUTH_REGEX` and `_SKIP_AUTH_PREFLIGHT` in both oauth2-proxy jobspecs.
Before L5 it checked only dash's jobspec, so an exemption on this proxy
passed every hook. The fix is in `7e93194`. The registry's notification
webhook, one of the scaling fixes the cost page describes, would need such an
exemption, and that page says how narrow it must be.

Today the guard runs only when someone runs it. Commit `f197702` (2026-09-09)
removed its pre-commit hooks, along with the four `registry-ui-backend-*`
hooks (ruff, format, mypy, pytest). Nothing runs either automatically.
`docs/reference/registry-ui.md` still says both run as hooks. On 2026-09-27
the guard passed by hand, and the backend suite passed 55 tests.

## History

L5 planned a registry tab inside dash, on a `dash_data` volume. Mid-ticket it
became its own job, so either service can fail without the other. It landed
as `7e93194` under `loopctl halt`: the ticket hit its review-cycle cap, and
the final adversarial pass read a tree that edits had moved. The ledger still
shows L5 as `blocked` with no commit. Three defects no gate caught were fixed
before landing. The copied `nginx.conf` listened on 8000 while the job
allocated 8002. The split dropped every test of `main.py` and `config.py`.
The guard covered dash alone. The plan and signed eval still describe the
dash-integrated design and a `1 + R + T + B` request count. The shipped walk
is `1 + R + T + D + B`, because a manifest `HEAD` returns only a digest.

## Port 4181 is taken

Ticket `B2-bifrost-oauth2-proxy` (stage `ready`) plans an oauth2-proxy for
Bifrost on "port 4181, same node", and its premise says 4181 "appears
nowhere in `deployments/`" (grep of 2026-09-03). registry-ui's proxy took
4181 on radxa on 2026-09-05. B2 needs another port before it runs.

## Related

- [Container registry](/components/container-registry.md)
- [The HAProxy edge and the oauth2-proxy gates behind it](/components/edge-proxy.md)

- `docs/reference/registry-ui.md`
- `docs/explanation/registry-ui-cost.md`
- `docs/how-to/rebuild-the-registry-ui-images.md`
