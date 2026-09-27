# Why registry-ui stays cheap, and where it stops scaling

`registry-ui` walks the cluster registry to show what it holds, described in
[registry-ui](../reference/registry-ui.md). This page says why that walk stays
cheap and at what size it stops fitting.

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
session, so the route would need exactly the auth exemption the guard
(`scripts/check_oauth2_proxy_guard.py`, see
[registry-ui](../reference/registry-ui.md#signing-in)) refuses. If the
hatch is taken, the exemption must name that one path and check its own
shared secret. It must never widen to `/api/*` or to the view.

The second is capacity. If `registry-ui` ever runs `count > 1`, the
in-process sweep state stops being shared: each instance sweeps on its own
and two tabs can disagree. That is the point at which the store belongs in
Redis rather than on a host volume.
