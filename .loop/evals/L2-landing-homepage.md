eval: L2-landing-homepage

Definition of Done: the Homepage (gethomepage) Nomad job runs healthy on a
dynamic host volume, HAProxy routes `dash.localstack` to it behind L1's
oauth2-proxy forward-auth (dep: L1 ⇒ F2, F3), so an authenticated operator
sees the themed landing page with tiles and live-status widgets for all nine
services, an unauthenticated request is blocked by L1 (redirected to Vault
login, never served a 200 homepage), and no existing route regresses.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| The operator's Homepage job is deployed and healthy | `nomad job status homepage` | The `homepage` group is `Running` with `Healthy` equal to `Desired`/`Placed`, 0 restarts, and the task's health `check` passing | deterministic check (`nomad job status homepage`) | 100% |
| An authenticated operator reaches the landing page and sees all nine services | `curl -s --cookie "<oauth2-proxy session cookie>" http://dash.localstack/ \| grep -Eio 'minio\|postgres\|grafana\|prometheus\|loki\|phoenix\|memex\|mlflow\|nats'` | HTTP 200 Homepage HTML body whose grep matches all nine service names (minio, postgres, grafana, prometheus, loki, phoenix, memex, mlflow, nats) | deterministic check (authenticated `curl` piped to `grep -Eio` for the nine names) | 100% |
| Each service tile resolves to a live status against a reachable URL | Inspect each tile's `siteMonitor`/service widget in the authenticated rendered page or Homepage's service-status API | Every tile's widget resolves (status shown, not error), each pointing at a reachable URL per §6 req 5 (`*.localstack` HAProxy hostnames, Postgres firebat:5432, NATS radxa:8222) | deterministic check (authenticated `curl` of Homepage service-status API; each tile status resolves) | 100% |
| The operator sees a correctly themed landing page with working tiles | Adversarial review agent views the authenticated rendered Homepage against §6 (themed page, nine tiles, live-status widgets) and §5 non-goals | The page renders the themed tiles correctly: nine service tiles laid out with live up/down widgets, coherent theme, flat access (no per-user RBAC surfaced), no Zitadel reference | model + rubric (adversarial review agent) | 4/5 |
| An unauthenticated visitor is blocked by L1, never served the homepage | `curl -sI http://dash.localstack/` with no L1 session cookie | A `302` redirect to the Vault/oauth2-proxy login (`Location:` header pointing at the L1 auth endpoint), NOT `HTTP/1.1 200`; a 200 here fails acceptance (Risk 1) | deterministic check (unauthenticated `curl -sI http://dash.localstack/` returns 302 to Vault login, not 200) | 100% |
| No existing route regresses from the HAProxy heredoc edit | `curl -sI http://grafana.localstack/` compared against the pre-apply baseline status line | Grafana returns the same status line recorded at baseline, and the rendered HAProxy config is syntactically valid | deterministic check (`haproxy -c -f <rendered.cfg>` valid AND `curl -sI http://grafana.localstack/` matches baseline) | 100% |
