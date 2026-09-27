# dash: the cluster landing page

`dash` is a small Nomad job that serves `https://dash.lab.orangecluster.nl`:
one tile per service, grouped under headings the config names: Platform,
Storage, Telemetry, Events, Agentic, Artifacts. A tile is one SERVICE, not
one endpoint, so `openviking` is a single tile carrying both its dashboard
and its API, and `registry` is a single tile covering the OCI API and the
`registry-ui` browser view.

One service may still get a second tile when a facet of it is worth finding on
its own. `alerting` is the first: it names Grafana's Telegram channel and
tracks Grafana's job, because Grafana is the alert engine. A facet tile shares
the job it names, so a Grafana outage shows against both cards, and the header
counters count tiles rather than jobs and will say two.

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
See [How to log in to Vault](../how-to/log-in-to-vault.md) for the login
flow itself. Nothing here repeats it.

**One quirk to expect.** The first SSO attempt from a browser with no
existing Vault UI session can fail with a generic error and leave you
unauthenticated. Retrying after logging into the Vault UI succeeds. This is
the same behavior
[step 1 of How to sign in to Nomad with Vault](../how-to/sign-in-to-nomad-with-vault.md)
documents for the Nomad sign-in button. It has been observed but not root-caused, and fixing
it is out of scope here.

## `tiles.json`

`deployments/applications/services/dash/tiles.json` is an array of
groups, and array order is display order, for the headings and for the
tiles inside each one.

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

## What the status backend can and cannot read

`dash`'s backend Nomad token is minted from a dedicated, read-only role
(`deployments/infrastructure/machine_roles.tf`, the `dash` section): `read-job`,
`list-jobs`, and `node:read`, nothing else. No `submit-job`, no
`host-volume-*`, no management capability. It never reads HAProxy's own job
spec (that spec embeds a live credential in plaintext), so tile-to-job
matching comes entirely from each tile's own `jobs` array, not from
HAProxy's routing table. The frontend task holds no credential, no Vault
role, and no Nomad token at all — it serves `index.html` and nothing else.

## Related pages

- [How to add, remove, or reorder a dash tile](../how-to/change-a-dash-tile.md)
- [How to rebuild and deploy the dash images](../how-to/rebuild-the-dash-images.md)
- [How dash reaches two tasks through one route](../explanation/dash-routing.md)
