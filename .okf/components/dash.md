---
type: component
title: dash, the landing page
description: "How dash is built: a static frontend and a status backend in one job on radxa, split by oauth2-proxy's exact-match upstreams, with a read-only Nomad token Vault mints per alloc. Covers what spans the two Terraform roots, the tiles.json guards, and the fact that no gate runs the backend suite since the pre-commit hooks were removed."
tags: [dash, landing, oauth2-proxy, nomad, vault, python]
status: stable
generated:
  by: claude-opus/5.5
  at: 2026-09-27
sources:
  - id: dash-jobspec
    resource: git:3ec5d1e:deployments/applications/services/dash.hcl
  - id: dash-backend
    resource: git:3ec5d1e:deployments/applications/services/dash/backend/src/dash_app/health.py
  - id: dash-tiles-test
    resource: git:3ec5d1e:deployments/applications/services/dash/backend/tests/test_tiles.py
  - id: app-services
    resource: git:3ec5d1e:deployments/applications/services.tf
  - id: infra-machine-roles
    resource: git:3ec5d1e:deployments/infrastructure/machine_roles.tf
  - id: infra-services
    resource: git:3ec5d1e:deployments/infrastructure/services.tf
  - id: oauth2-proxy-jobspec
    resource: git:3ec5d1e:deployments/infrastructure/services/oauth2-proxy.hcl
  - id: infra-oidc
    resource: git:3ec5d1e:deployments/infrastructure/oidc.tf
  - id: hooks-removed
    resource: git:f197702
  - id: L3-landing-dash-app
    resource: git:3ec5d1e:.loop/reflections/L3-landing-dash-app.md
  - id: L4-landing-dash-fe-be-split
    resource: git:3ec5d1e:.loop/reflections/L4-landing-dash-fe-be-split.md
  - id: L6-landing-dash-service-groups
    resource: git:3ec5d1e:.loop/reflections/L6-landing-dash-service-groups.md
---

# dash, the landing page

dash serves `https://dash.lab.orangecluster.nl`: one tile per service with
live status. What it shows and how to edit tiles is `docs/reference/dash.md`.
This page is about how the parts connect across both Terraform roots.

## The request path

```
browser -> HAProxy (firebat, backend dash) -> 192.168.2.50:4180 oauth2-proxy
             catch-all          -> 127.0.0.1:8000  dash frontend (nginx)
             /api/status exact  -> 127.0.0.1:8001  dash backend (Starlette)
```

oauth2-proxy and both dash tasks run on radxa-dragon-q6a with host
networking, so the proxy reaches dash over loopback. How the path-scoped
upstream matches is `docs/explanation/dash-routing.md`. The consequence for a
maintainer: a new backend route needs its own upstream entry in the
infrastructure root, or it falls through to the frontend.

## The pieces

**Applications root** (`deployments/applications/`):

- `services/dash.hcl`: group pinned to radxa, static ports 8000 and 8001,
  tasks `frontend` and `backend`.
- `services/dash/frontend/`: `index.html`, and an `nginx.conf` that listens
  on 8000 because host networking makes the container port the host port.
- `services/dash/backend/`: its own uv project (`dash_app`: `main.py`,
  `tiles.py`, `status.py`, `live.py`, and the copied `health.py`,
  `nomad_client.py`, `consul_client.py`, `services.py`).
- `services/dash/tiles.json`: the groups and tiles.
- `services.tf`: `local.dash_tiles_json` and `nomad_job.dash`, with the two
  image tags pinned separately and the Nomad and Consul addresses as literals.
- `justfile`: `rebuild_dash_frontend` and `rebuild_dash_backend` read the tags
  from `services.tf`.

**Infrastructure root** (`deployments/infrastructure/`):

- `machine_roles.tf`, the `dash` section: `nomad_acl_policy.dash_read`
  (`read-job`, `list-jobs`, `node:read`, written through the `nomad.manage`
  provider), `vault_nomad_secret_role.dash_read`,
  `vault_policy.dash_nomad_creds_read`, and `vault_jwt_auth_backend_role.dash`.
- `services.tf`: `nomad_job.oauth2_proxy`, whose upstreams are the two
  loopback literals above.
- `services/oauth2-proxy.hcl`: the proxy's jobspec.
- `oidc.tf`: `vault_identity_oidc_client.oauth2_proxy`, assigned to
  `operators` (developer and admin), and the redirect URL local. That
  assignment is the only access filter, because the proxy admits every email
  domain and names no group. `docs/reference/dash.md` still says any
  successful login is authorized.

Apply the infrastructure root first. The backend task's `vault { role =
"dash" }` fails to log in until that JWT role exists. The two roots share no
state. The upstream ports in the infrastructure root and the ports in
`dash.hcl` agree only because both are typed by hand.

## Why the backend is shaped this way

**Its own credential, minted per alloc.** The backend reads
`nomad/creds/dash_read` through a template, and Vault's Nomad secrets engine mints a client token
carrying only `dash-read`. No existing grant fit. `nomad-workloads` carries
no Nomad capability. `nomad/creds/deploy` can submit jobs. `nomad/creds/manage`
is a management token brokered only to interactive humans. The dedicated JWT
role carries `nomad-workloads` too, because naming a role replaces the
default one rather than adding to it.

**No dependency on `cli/`.** L3 imported cli's health logic through a uv
path dependency, and the Docker multi-stage build shipped a broken editable
install that crashed only at runtime. L4 copied the four modules down
instead (`docs/reference/dash.md`). No test compares the copies with
`cli/src/localstack_cli/api/`.

## Traps

- **`.Data.secret_id`, not `.Data.data.secret_id`.** The double nesting is a
  KV2 artifact. The Nomad engine returns the token one level down. L3's
  adversarial review caught this. Only a live render shows it.
- **`tiles_json` goes into a heredoc.** It is JSON with embedded quotes, and
  a quoted HCL string would end at the first one. Neither `terraform
  validate` nor `nomad fmt` parses the rendered jobspec, so this fails only
  at apply.
- **`tiles.json` must hold no template opener.** A dollar-brace or
  percent-brace sequence opens a template once `dash.hcl` splices the file
  in. The percent form is worse: it parses and rewrites the deployed text
  without an error. L6's plan review found this by rendering through Nomad's
  parser. The comment in `dash.hcl` cannot spell either opener, because
  `templatefile()` reads comments too, and an earlier version that did broke
  `terraform validate`.
- **A comment inside a `template` heredoc becomes file content.** L4 nearly
  shipped `###` lines into oauth2-proxy's env file. No gate catches this.
- **A stale filename inside the jobspec.** `dash.hcl`'s comment on the
  `vault` block cites `nomad_dash_read_role.tf`, which is now the `dash`
  section of `machine_roles.tf`. Editing that comment re-registers the job,
  so it stays until the jobspec changes for another reason.
- **CSS `display` beats `[hidden]`.** L6 found the panel button never hid,
  because `.fe-button { display: flex }` outranks the user-agent rule. The
  frontend has no test and no linter, and nobody in the loop ever ran
  `index.html` in a browser.

## What enforces the invariants today

- JSON syntax of `tiles.json`: `jsondecode` in `services.tf`, at plan.
- Tile schema and the opener ban: `backend/tests/test_tiles.py`
  (`test_the_shipped_config_carries_no_nomad_template_opener`).
- The backend's ruff, mypy and pytest gates: NOTHING automatic. Commit
  `f197702` ("fix: openviking code", 2026-09-09) deleted the
  `dash-backend-*` hooks from `.pre-commit-config.yaml`, together with the
  registry-ui and driftwatch hooks, the `oauth2-proxy-guard` hooks and cli's
  pytest hook. The loop's only gate is `just pre_commit`, so none of these run
  unless someone runs `uv run pytest` in `services/dash/backend/` by hand.
  The suite passed (75 tests) on 2026-09-27.

## History

L1 put oauth2-proxy in front of a placeholder. L2 (gethomepage) was dropped,
superseded by L3. L3 built dash as one task, L4 split it into frontend and
backend and dropped the cli dependency, and L6 grouped tiles under headings.
L5's registry view became its own job, [registry-ui](/components/registry-ui.md).
Why TOTP enrollment has no page here is
[ADR 0012](/decisions/0012-no-mfa-enrollment-app-on-dash.md).

## Related

- [The HAProxy edge and the oauth2-proxy gates behind it](/components/edge-proxy.md)
- [Vault's OIDC provider and its clients](/components/vault-oidc-provider.md)

- `docs/reference/dash.md`
- `docs/explanation/dash-routing.md`
- `docs/how-to/change-a-dash-tile.md`
- `docs/how-to/rebuild-the-dash-images.md`
