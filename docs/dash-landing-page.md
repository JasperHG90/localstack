# dash: the cluster landing page

`dash` is a small Nomad job that serves `https://dash.lab.orangecluster.nl`:
one tile per service, grouped under headings the config names: Platform,
Storage, Telemetry, Events, Agentic, Artifacts. A tile is one SERVICE, not
one endpoint, so `openviking` is a single tile carrying both its dashboard
and its API, and `registry` is a single tile covering the OCI API and the
`registry-ui` browser view.

Clicking a tile opens a panel: the status of every job behind the service,
instructions for reaching it without a browser, and a button to its UI if it
has one. A service with both gets both, which is the point. A tile that
only linked out never showed you its API. Tiles that have a UI also keep a
corner link, so getting to Grafana is still one click.

Every tile's status is computed live from Nomad job state and Consul health
checks. A service spanning two jobs reports the worse of the two, so a dead
browser view cannot hide behind a healthy API.

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

## Adding, removing, or reordering a tile

Edit `deployments/applications/services/dash/tiles.json`. It is an array of
groups, and array order is display order, for the headings and for the
tiles inside each one. Moving a tile up the page is moving it up the file.

A group carries:

- `key`: unique, used for nothing but catching duplicates.
- `title`: the heading text.
- `hint`: the gray line beside the heading. Optional.
- `tiles`: the tiles under it, in display order. At least one.

A tile carries:

- `key`, `name`, `desc`, `color`, `icon` (an inline SVG string): display.
  `key` is unique across every group.
- `jobs`: one or more `{name, node}` pairs. `name` is the Nomad job (or the
  Consul service name, for Vault, Nomad and Consul, which run as agents
  rather than Nomad jobs). `node` is the node its jobspec constrains it to,
  a deployment-time fact rather than something read live. A tile's status is
  the worst of its jobs', and the card names the node of whichever job
  decided it.
- `fe`: `{url, label}` for a service with a browser UI. `label` is the panel
  button's text and defaults to `open`. Optional.
- `connect`: `protocol`, `address`, `auth`, `example`. How to work with the
  service without a browser. Never a credential value: an auth method
  description and an example command with a placeholder, same convention as
  `localstack secret <job>` (existence, never value). Optional.

A tile needs `fe`, `connect`, or both. One with neither fails to parse.
`connect` covers both directions: how to call a service, and how to be
picked up by one. The `prometheus` tile uses it to say how to get scraped,
since Prometheus collects nothing until a service tags its Consul
registration.

Two characters are forbidden anywhere in the file: `${` and `%{`. Terraform
splices this config into a Nomad heredoc (`services/dash.hcl`), where both
open a template. An expression-shaped `${...}` fails `terraform apply`;
`%{ ... }` is worse, parsing cleanly and rewriting the text on its way to
the job. A bare `$` is fine and already ships. The backend suite asserts
both openers are absent.

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
(`deployments/infrastructure/machine_roles.tf`, the `dash` section): `read-job`,
`list-jobs`, and `node:read`, nothing else. No `submit-job`, no
`host-volume-*`, no management capability. It never reads HAProxy's own job
spec (that spec embeds a live credential in plaintext), so tile-to-job
matching comes entirely from each tile's own `jobs` array, not from
HAProxy's routing table. The frontend task holds no credential, no Vault
role, and no Nomad token at all — it serves `index.html` and nothing else.
