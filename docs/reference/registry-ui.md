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
is authorized. [How to log in to Vault](../how-to/log-in-to-vault.md) covers the login flow
itself.

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

## The frontend port

The frontend's `nginx.conf` listens on 8002, the group-level `http` port,
because the job runs with `network_mode = "host"` and its proxy dials 8002
on loopback. Copying this file to a new service means changing that number.

## Tests

`deployments/applications/services/registry-ui/backend` is its own uv
project with its own four pre-commit hooks, mirroring dash's. `uv run
pytest` runs the offline suite. The one test that touches the live registry
carries the `cluster` marker and is excluded by default:

```
uv run pytest -m cluster
```

## Related pages

- [How to rebuild and deploy the registry-ui images](../how-to/rebuild-the-registry-ui-images.md)
- [Why registry-ui stays cheap, and where it stops scaling](../explanation/registry-ui-cost.md)
