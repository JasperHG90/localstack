# How dash reaches two tasks through one route

`dash` runs a static `frontend` task and a `backend` task behind one
hostname, described in [dash](../reference/dash.md). This is how one route
serves both.

`index.html` makes one same-origin call, `fetch('/api/status')`. Since the
frontend is static-file-only, oauth2-proxy itself splits the traffic
(`deployments/infrastructure/services/oauth2-proxy.hcl`,
`OAUTH2_PROXY_UPSTREAMS`): a catch-all upstream to the frontend task's
loopback port (8000) and a second upstream scoped to `/api/status`,
pointed at the backend task's loopback port (8001). Verified against a
real oauth2-proxy v7.13.0 container: the path-scoped upstream matches
`/api/status` exactly, not as a prefix, which is exactly what the one
fetch call needs.
