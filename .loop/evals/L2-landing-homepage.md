eval: L2-landing-homepage

Definition of Done: the Homepage (gethomepage) Nomad job runs healthy in
`deployments/applications/` on a dynamic host volume (if kept), and L1's
already-deployed oauth2-proxy (`dash.lab.orangecluster.nl`) reverse-proxies to
it — replacing the `static://200` placeholder — so an authenticated operator
sees the themed landing page with tiles and live-status widgets for the eight
services that still exist on this cluster, an unauthenticated request is
still blocked exactly as it is today (L2 changes nothing about that gate),
and oauth2-proxy's own allocation stays healthy after the upstream edit.

Rewritten 2026-08-23 after the plan-validator `fail` verdict
(`.loop/verdicts/L2-landing-homepage.plan-validator.md`, required fix 5) found
every row here probing `http://`, which since T3 (the edge TLS cutover) only
ever returns a 301 to HTTPS — so the security-critical "unauthenticated
visitor is blocked" row passed against a cluster with no Homepage and no auth
wired at all. What changed:

- **Every row now probes `https://dash.lab.orangecluster.nl/` directly**, not
  the port-80 redirect.
- **The unauthenticated-block row copies L1's own eval pattern**
  (`.loop/evals/L1-landing-oauth2-proxy.md`, behavior "An unauthenticated
  visitor is refused rather than served the upstream"), which already solved
  exactly this problem for the same host: it asserts the response is a 40x
  carrying oauth2-proxy's own sign-in page, or a 302 whose `Location` is
  Vault's authorize endpoint — never a bare "any redirect" and never a `200`.
- **The old "no regression" row (comparing a port-80 status line) is
  retired.** L2 makes zero `haproxy.hcl` edits, so a port-80 redirect check
  could never have detected anything this ticket changes — it was vacuous
  even before the TLS cutover made it doubly so. It is replaced with a
  guardrail on the one shared-blast-radius file L2 *does* edit: L1's
  already-deployed `oauth2-proxy` job. If the upstream edit is malformed,
  this is the row that catches oauth2-proxy itself going unhealthy.
- **The nine-tile check becomes an eight-tile check** and no longer greps raw
  HTML. `deployments/applications/storage.tf:23-26` and commit `fab7e53`
  confirm MLflow's service (job, secrets, database, HAProxy route) is fully
  gone, not merely de-routed — a `grep -Eio` for "mlflow" would match a
  tile that cannot exist. The row now reads the rendered Homepage config
  directly for the exact service-name set, and the tile-status row is scored
  by an adversarial review agent inspecting the rendered page (a raw
  substring match over HTML would pass against a tile that merely mentions a
  service name in a CSS class or favicon path without ever resolving its
  status).
- **A new guardrail row reads the rendered `OAUTH2_PROXY_UPSTREAMS` value.**
  `${homepage_upstream}` is a plain Terraform `templatefile()` interpolation
  (not a Nomad/consul-template secret), so by the time the job is registered
  it is a literal string visible via `nomad job inspect oauth2-proxy` — no
  exec into the allocation, no extra credential beyond the `NOMAD_TOKEN`
  already assumed by every other row here.

Preconditions: L1 (`done`) already deployed oauth2-proxy and the `dash`
route; both stay untouched by this ticket except for the one upstream value.
The authenticated rows need a completed Vault login for
`https://dash.lab.orangecluster.nl/` — the same browser flow L1's own
close-out eval (behavior "A user who completes the Vault login gets
through, under the flat policy") already establishes; this eval does not introduce a
new credential or fixture, it reuses that one.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| The operator's Homepage job is deployed and healthy | `nomad job status homepage` | The `homepage` group is `Running` with `Healthy` equal to `Desired`/`Placed`, 0 restarts, and the task's health `check` passing | deterministic check (`nomad job status homepage`) | 100% |
| Homepage's rendered config declares exactly the eight expected services and no MLflow | `nomad alloc fs <homepage-alloc-id> local/services.yaml` (or `nomad alloc exec` equivalent) | The rendered config names MinIO, Postgres, Grafana, Phoenix, Memex, and NATS as service entries, and Prometheus and Loki as informational-only entries (no URL). `mlflow` appears nowhere — the service was fully removed by commit `fab7e53` (`deployments/applications/storage.tf:23-26`) | deterministic check (read the rendered config file for the exact name set) | 100% |
| oauth2-proxy's own allocation stays healthy after the upstream edit (regression guard on L1's already-deployed job) | `nomad job status oauth2-proxy` | `Status = running`, latest deployment `Successful`, a `running`/`healthy` allocation with 0 failed and 0 restarts since the edit. A malformed `${homepage_upstream}` render is the one way this ticket's single shared-blast-radius edit could break the already-working `dash` gate | deterministic check (`nomad job status oauth2-proxy`) | 100% |
| oauth2-proxy's rendered upstream now points at Homepage, not the placeholder | `nomad job inspect oauth2-proxy` (read the `OAUTH2_PROXY_UPSTREAMS` line in the rendered `template` block) | The value is `http://<homepage-host>:<homepage-port>` — the real Homepage address chosen in Requirement 1/Q3 — and is NOT `static://200`. Since `${homepage_upstream}` is a Terraform `templatefile()` interpolation (resolved before Nomad sees the job), this is visible directly in the rendered jobspec with no exec into the allocation | deterministic check (`nomad job inspect oauth2-proxy`, string match on the rendered value) | 100% |
| An unauthenticated visitor is still blocked at `dash`, unchanged from L1 | `curl -sI https://dash.lab.orangecluster.nl/` with no session cookie | A `40x` carrying oauth2-proxy's own sign-in page, **or** a `302` whose `Location` is Vault's authorize endpoint (`vault.lab.orangecluster.nl/ui/vault/identity/oidc/provider/lab/authorize`) — matching `.loop/evals/L1-landing-oauth2-proxy.md`'s "An unauthenticated visitor is refused rather than served the upstream" row exactly, since L2 changes nothing about this gate. Never a `200` from Homepage or from the old `static://200` placeholder | deterministic check (`curl -sI` on `/`, expecting 4xx or a 302 to Vault's authorize endpoint — not a bare "any redirect") | 100% |
| An authenticated operator reaches Homepage itself, not the old placeholder | Complete the Vault auth-code flow for `https://dash.lab.orangecluster.nl/` in a browser (same procedure as `.loop/evals/L1-landing-oauth2-proxy.md`'s "A user who completes the Vault login gets through, under the flat policy" row), then re-request with the session cookie: `curl -s --cookie "<oauth2-proxy session cookie>" https://dash.lab.orangecluster.nl/` | `HTTP/2 200` and a body that is Homepage's own rendered HTML (non-trivial length, carries Homepage's app markup) — explicitly NOT the literal 3-byte `200` body the old `static://200` placeholder served. This is the row that proves the upstream rewire actually took effect, not just that the env var reads correctly | deterministic check (authenticated `curl`; status 200 AND body length/content check ruling out the placeholder's bare "200" response) | 100% |
| The operator sees a correctly themed landing page with working tiles for the eight current services | Adversarial review agent views the authenticated rendered Homepage against §6 (eight tiles, `siteMonitor`/service widgets) and §5 non-goals | The page renders the themed tiles correctly: MinIO, Postgres, Grafana, Phoenix, Memex, and NATS each show a resolved (non-error) `siteMonitor`/service-widget status tied to that specific tile — not generic page text a substring match could false-positive on; Prometheus and Loki appear as informational tiles with no clickable URL and no `siteMonitor`/status widget; no MLflow tile anywhere; coherent theme; flat access (no per-user RBAC surfaced); no Zitadel reference | model + rubric (adversarial review agent) | 4/5 |
