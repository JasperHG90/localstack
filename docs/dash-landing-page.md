# dash: the cluster landing page

`dash` is a small Nomad job that serves `https://dash.lab.orangecluster.nl`:
a grid of tiles for every user-facing dashboard (Grafana, MinIO, Vault,
Nomad, Consul, Phoenix, Bifrost) and every backend service worth knowing how
to reach (Postgres, NATS, Redis, Hermes, Memex, Tempo, Registry). Dashboard
tiles link out. Backend tiles open a modal with connection details. Every
tile's status is computed live from Nomad job state and Consul health
checks.

The job holds two tasks: a `frontend` task (static files only, no Python)
and a `backend` task (status computation). The backend carries its own
copies of the narrow health/join/consul logic it needs
(`dash/backend/src/dash_app/health.py`, `nomad_client.py`,
`consul_client.py`, `services.py`), copied down from
`cli/src/localstack_cli/api/` rather than imported: the backend does not
depend on `cli` at all, by design (drift between the two copies is an
accepted tradeoff, not a bug).

## Signing in

`dash` sits entirely behind oauth2-proxy (L1), gated on a completed Vault
OIDC login against the `lab` provider. Any successful login is authorized.
See `docs/vault-human-auth.md`'s "Logging in" section for the login flow
itself. Nothing here repeats it.

**One quirk to expect.** The first SSO attempt from a browser with no
existing Vault UI session can fail with a generic error and leave you
unauthenticated. Retrying after logging into the Vault UI succeeds. This is
the same behavior `docs/vault-human-auth.md:329-336` documents for the
Nomad sign-in button. It has been observed but not root-caused, and fixing
it is out of scope here.

## Adding or removing a tile

Edit `deployments/applications/services/dash/tiles.json`. Each entry is one
tile:

- `key`, `name`, `desc`, `color`, `icon` (an inline SVG string): display.
- `category`: `"dashboard"` or `"backend"`.
- `job`: the Nomad job name (or Consul service name, for Vault/Nomad/Consul,
  which run as agents rather than Nomad jobs) this tile's status is computed
  from.
- `node`: the node the job is constrained to. A deployment-time fact, not
  computed live.
- `"dashboard"` tiles need `url`. `"backend"` tiles need a `connect` block:
  `protocol`, `address`, `auth`, `example`. Never a credential value: an
  auth method description and an example command with a placeholder, same
  convention as `localstack secret <job>` (existence, never value).

Apply through `deployments/applications`'s normal `just apply`. The file
round-trips through Terraform's `jsondecode`/`jsonencode`, so a JSON syntax
error fails `terraform plan` rather than reaching the job.

## Rebuilding and deploying the images

```
cd deployments/applications
just rebuild_dash_backend
just rebuild_dash_frontend
just apply
```

`rebuild_dash_backend` builds and pushes
`ghcr.io/jasperhg90/dash-backend:<dash_backend_version>`.
`rebuild_dash_frontend` builds and pushes
`ghcr.io/jasperhg90/dash-frontend:<dash_frontend_version>` (both tags are
read out of `services.tf`, so bump them there before rebuilding). `just
apply` deploys the new images. Each image builds from its own
single-directory context
(`deployments/applications/services/dash/backend/` and
`deployments/applications/services/dash/frontend/`), and neither depends
on `cli/`.

## How the browser reaches two tasks through one route

`index.html` makes one same-origin call, `fetch('/api/status')`. Since the
frontend is static-file-only, oauth2-proxy itself splits the traffic
(`deployments/infrastructure/services/oauth2-proxy.hcl`,
`OAUTH2_PROXY_UPSTREAMS`): a catch-all upstream to the frontend task's
loopback port (8000) and a second upstream scoped to `/api/status`,
pointed at the backend task's loopback port (8001). Verified against a
real oauth2-proxy v7.13.0 container: the path-scoped upstream matches
`/api/status` exactly, not as a prefix, which is exactly what the one
fetch call needs.

## What the status backend can and cannot read

`dash`'s backend Nomad token is minted from a dedicated, read-only role
(`deployments/infrastructure/nomad_dash_read_role.tf`): `read-job`,
`list-jobs`, and `node:read`, nothing else. No `submit-job`, no
`host-volume-*`, no management capability. It never reads HAProxy's own job
spec (that spec embeds a live credential in plaintext), so tile-to-job
matching comes entirely from `tiles.json`'s own `job` field, not from
HAProxy's routing table. The frontend task holds no credential, no Vault
role, and no Nomad token at all — it serves `index.html` and nothing else.
