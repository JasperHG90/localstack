# dash: the cluster landing page

`dash` is a small Nomad job that serves `https://dash.lab.orangecluster.nl`:
a grid of tiles for every user-facing dashboard (Grafana, MinIO, Vault,
Nomad, Consul, Phoenix, Bifrost) and every backend service worth knowing how
to reach (Postgres, NATS, Redis, Hermes, Memex). Dashboard tiles link out.
Backend tiles open a modal with connection details. Every tile's status is
computed live from Nomad job state and Consul health checks, the same logic
`localstack service` already uses (`cli/src/localstack_cli/api/health.py`,
`cli/src/localstack_cli/api/services.py`).

## Signing in

`dash` sits entirely behind oauth2-proxy (L1), gated on a completed Vault
OIDC login against the `lab` provider. Any successful login is authorized.
See `docs/vault-human-auth.md`'s "Logging in" section for the login flow
itself. Nothing here repeats it.

**One quirk to expect.** The first SSO attempt from a browser with no
existing Vault UI session can fail with a generic error and leave you
unauthenticated. Retrying after logging into the Vault UI succeeds. This is
the same behavior `docs/vault-human-auth.md:328-335` documents for the
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

## Rebuilding and deploying the image

```
cd deployments/applications
just rebuild_dash
just apply
```

`rebuild_dash` builds and pushes `ghcr.io/jasperhg90/dash:<dash_version>`
(the tag is read out of `services.tf`, so bump `dash_version` there before
rebuilding). `just apply` deploys the new image.

## What the status backend can and cannot read

`dash`'s Nomad token is minted from a dedicated, read-only role
(`deployments/infrastructure/nomad_dash_read_role.tf`): `read-job`,
`list-jobs`, and `node:read`, nothing else. No `submit-job`, no
`host-volume-*`, no management capability. It never reads HAProxy's own job
spec (that spec embeds a live credential in plaintext), so tile-to-job
matching comes entirely from `tiles.json`'s own `job` field, not from
HAProxy's routing table.
