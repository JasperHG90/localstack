eval: R4-rollout-phoenix-oauth2-proxy

Definition of Done: browsing the Phoenix UI at `phoenix.localstack` requires a
completed Vault OIDC login via oauth2-proxy (unauth is bounced to the Vault
sign-in), while OTLP trace ingest survives the port-6006 split — `memex`'s HTTP
`/v1/traces` POST stays ungated and gRPC 4317 stays reachable — and the old
HAProxy basic-auth on the Phoenix backend is gone with no double auth.

Preconditions (ticket §8, §11): these evals depend on **L1** (the reusable
oauth2-proxy forward-auth pattern) and **F2** (Vault as OIDC provider
registering the Phoenix client) being applied first (Q1/Q2); until both land
there is no auth backend for the UI check to redirect to and R4 is blocked. Run
each after `terraform apply` and the Nomad deploy have landed. The
ingest-not-broken (row on `/v1/traces`) and gRPC-reachable (row on 4317) rows
are the load-bearing guardrails — a pass requires the UI to gate AND both
ingest checks to stay ungated; breaking either side is a fail.

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| Phoenix and its oauth2-proxy are both running after apply | `nomad job status phoenix` (and `nomad job status <proxy-job>` if the proxy is standalone per Q1) | the `phoenix` task and the oauth2-proxy task both report `running`/`healthy`; deployment `Status = successful` | deterministic check (`nomad job status phoenix`) | 100% |
| An unauthenticated browser hitting the Phoenix console is bounced to the Vault OIDC login, not served the app | `curl -sI https://phoenix.localstack/` | `HTTP/1.1 302` (or 307) with a `Location:` header pointing at the Vault OIDC login (`vault.localstack` / oauth2-proxy `/oauth2/start` sign-in); NOT `200` and NOT the Phoenix HTML console | deterministic check (`curl -sI https://phoenix.localstack/`) | 100% |
| HTTP OTLP trace ingest still works and is NOT gated — the `memex` ingest path (`memex.hcl:143`) survives the port-6006 split (load-bearing guardrail) | `curl -s -o /dev/null -w '%{http_code}\n' -X POST http://192.168.2.29:6006/v1/traces -H 'content-type: application/json' -d '{"resourceSpans":[]}'` | a non-auth status returned by Phoenix's collector itself — `200`, `415`, or `400`/parse error — proving the request reached Phoenix; it must NOT be `302` or `401` (either means oauth2-proxy intercepted ingest and `memex` trace ingest is broken) | deterministic check (`curl -X POST http://192.168.2.29:6006/v1/traces ...`) | 100% |
| gRPC OTLP ingest (4317) is still reachable and never routed through HAProxy/oauth2-proxy (load-bearing guardrail) | `nc -z -w3 192.168.2.29 4317 && echo "4317 open"` (fallback: `timeout 3 bash -c '</dev/tcp/192.168.2.29/4317' && echo "4317 open"`) | the port is open (`4317 open`); R4 leaves this path unchanged and services reach `192.168.2.29:4317` directly | deterministic check (`nc -z -w3 192.168.2.29 4317`) | 100% |
| The old HAProxy basic-auth gate no longer fronts Phoenix and is not stacked on top of oauth2-proxy (no double auth) | `curl -sI https://phoenix.localstack/`; and `nomad alloc exec <haproxy-alloc> grep -A3 'backend phoenix' <cfg>` | no `WWW-Authenticate: Basic` header on the Phoenix route, and no `http-request auth ... http_auth(openfang_users)` in the live `phoenix` backend (`haproxy.hcl:100`) — only the oauth2-proxy forward-auth; MLflow/Bifrost basic-auth lines left intact | deterministic check (`curl -sI` + `nomad alloc exec grep 'backend phoenix'`) | 100% |
| Behind a completed Vault login the Phoenix console renders correctly, and the UI-vs-ingest split holds under review | complete the auth-code flow in a browser (or with a session cookie), load `https://phoenix.localstack/`; hand the reviewer the row (b)/(c) ingest-survival evidence per `.claude/rules/adversarial-reviews.md` | the Phoenix console renders authenticated with no broken assets or auth loop, AND the reviewer confirms the port-6006 split gates the UI while leaving `/v1/traces` and gRPC 4317 ungated | model + rubric (adversarial review agent) | 4/5 |
