# registry-ui: what the cluster registry holds

`registry-ui` is a small Nomad job that serves
`https://registry-ui.lab.orangecluster.nl`: two tabs over the cluster
registry, one for KitOps ModelKits and one for container images. Each
ModelKit opens its own `README.md`, rendered from the kit's `docs` layer.

The split between the tabs is decided per repository by the manifest's
`artifactType`, so an image pushed tomorrow appears without a config change.

The job holds two tasks, the same shape `dash` uses: a `frontend` task
(static files only, no Python) and a `backend` task (the reading). It shares
no code and no process with `dash`; either can fail without the other.

## Signing in

`registry-ui` sits behind its own oauth2-proxy instance, gated on a
completed Vault OIDC login against the `lab` provider. Any successful login
is authorized. `docs/vault-human-auth.md` covers the login flow itself.

That instance
(`deployments/infrastructure/services/oauth2-proxy-registry-ui.hcl`) is a
copy of dash's, which is what dash's own jobspec says the pattern is for.
The two share the OIDC client and the cookie secret, and differ in three
things: the redirect URI, the listen port (4181 rather than 4180), and the
upstreams. HAProxy routes the hostname to 4181.

Neither jobspec sets a skip-auth key, and that absence is the gate.
`scripts/check_oauth2_proxy_guard.py` runs as a pre-commit hook over both
files to keep it that way.

## Nothing here touches model weights

A cold walk reads the catalog, one tag list per repository, one conditional
`HEAD` per tag, then per distinct digest one manifest and its blobs:
`1 + R + T + D + B`, which is 25 requests against today's four
repositories. A warm walk is `1 + R + T`, 13, because a stored digest needs
no manifest and no blob.

`B` is the blob count, and it differs by what the digest holds:

| digest holds | blobs | what they are |
|---|---|---|
| a ModelKit | 2 | the Kitfile, and `README.md` from the docs layer |
| a container image | 1 | its config blob: architecture and build date |
| a manifest index | 0 | an index names no architecture and carries no layers |

An index row therefore shows its digest and a `multi-arch` marker, with no
size and no architecture rather than a guess.

`embark.json` is listed as a layer and never parsed. It is embark's own
serving config, not registry metadata, and a registry browser that read it
would be coupled to one consumer of the registry.

## Why it stays cheap

The backend keeps a SQLite store on the `registry_ui_data` host volume, at
`/var/lib/registry-ui/registry.db`. A `cards` row is keyed by a manifest
digest, and a digest is content-addressed, so the row is never invalidated,
only evicted once no tag references it. A restart re-walks nothing.

Freshness comes from a sweep instead: the catalog, one tag list per
repository, and one conditional `HEAD` per tag carrying `If-None-Match`. A
`304` means the tag still points where the store thinks. Several open tabs
share one sweep through a 30-second floor, and the browser polls once a
minute while its tab is visible (`document.visibilityState`). The section
eyebrow carries a `refresh` button that bypasses the floor after a push.

`If-None-Match` buys time, not requests: a `304` still costs a round trip,
about 147 ms against 181 ms. The sweep count does not change.

Cards render server-side with `markdown-it-py`, once per digest and never
again — the rendered HTML is what the store holds. Rendering in Python
rather than in the browser puts the logic where this repo's tests already
reach; there is no JS or browser test harness here.

The walk runs eight requests in flight, bounded by an
`httpx.Limits(max_connections=8)` and a matching semaphore. Eight because
the latency curve flattens there and the registry is a shared job with a
small reservation, so the bound is as much politeness as speed.

Every database call crosses `asyncio.to_thread`, and each opens its own
connection. `sqlite3` blocks the event loop, and one connection shared
across those threads loses rows under concurrent writes, sometimes raising
and sometimes silently.

Every blob read is capped at 1 MiB and counted as it streams, so a mistaken
fetch of a model layer fails in its first megabyte rather than filling the
backend task's 128 MB reservation.

## Where this stops scaling

Sweep cost is `1 + R + T`, and `T` grows fastest because a model registry
accumulates versions: four repositories at twenty tags each is worse than
twenty at two. At eight-way concurrency it is comfortable to roughly 25
repositories, strained near 50, and past about 100 the sweep no longer fits
its own interval.

Two escape hatches, neither built.

The registry is `distribution` 3.1.1, which supports
`notifications.endpoints` and would replace polling with a push on every
registry write. It needs an inbound route and its own shared secret, and
that is the awkward part: a POST from the registry carries no browser
session, so the route would need exactly the auth exemption the guard above
refuses. If the hatch is taken, the exemption must name that one path and
check its own shared secret. It must never widen to `/api/*` or to the view.

The second is capacity. If `registry-ui` ever runs `count > 1`, the
in-process sweep state stops being shared: each instance sweeps on its own
and two tabs can disagree. That is the point at which the store belongs in
Redis rather than on a host volume.

## When the registry is unreachable

A sweep that fails with a previous payload in hand returns that payload and
reports the failure alongside it, rather than emptying a view that was
correct a minute ago. It raises only when there has never been a good
payload, and the route turns that into a `200` carrying an `error` field
rather than a 500. A Vault template that has not rendered reads the same
way, and builds no store until it has.

## Its credential

The backend reads the registry through `registry.lab.orangecluster.nl`, not
the registry's own port, which admits HAProxy's node alone. Its credential
is this job's own copy at `default/registry-ui/registry`: the
`nomad-workloads` role scopes a job to `secret/data/default/<job_id>/*`, so
reading the registry's own path would 403. Read-only use; this service
never pushes.

`/api/registry` is a path-scoped upstream, which matches exactly rather than
as a prefix, so the frontend fetches the bare path. `/api/registry/` with a
trailing slash falls through to the frontend.

## Rebuilding and deploying

```
cd deployments/applications
just rebuild_registry_ui_backend
just rebuild_registry_ui_frontend
just apply
```

Both tags are read out of `services.tf`, so bump them there before
rebuilding. Each image builds from its own single-directory context
(`services/registry-ui/backend/` and `services/registry-ui/frontend/`).

The frontend's `nginx.conf` listens on 8002, the group-level `http` port,
because the job runs with `network_mode = "host"` and its proxy dials 8002
on loopback. Copying this file to a new service means changing that number.

The `registry_ui_data` volume and the oauth2-proxy instance live in
`deployments/infrastructure`, so a first deployment applies that root too.

## Tests

`deployments/applications/services/registry-ui/backend` is its own uv
project with its own four pre-commit hooks, mirroring dash's. `uv run
pytest` runs the offline suite. The one test that touches the live registry
carries the `cluster` marker and is excluded by default:

```
uv run pytest -m cluster
```
