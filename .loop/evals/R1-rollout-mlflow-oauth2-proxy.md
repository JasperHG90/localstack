eval: R1-rollout-mlflow-oauth2-proxy

Definition of Done: MLflow sits behind an oauth2-proxy that redirects
unauthenticated humans to Vault OIDC and validates Nomad Workload Identity
`Authorization: Bearer` JWTs for machines, HAProxy's old basic-auth gate is
gone and its `mlflow` backend points at the proxy, and the six live evals
below pass over the plain-HTTP:80 edge.

Preconditions (ticket §8, §11): these evals depend on L1 (the reusable
oauth2-proxy pattern) and F2 (Vault as OIDC provider registering the MLflow
client); if either has not landed, the human and machine flows cannot pass
and R1 is blocked (Q1). Scheme is `http://` because HAProxy binds only
`*:80` today (`haproxy.hcl:49`, Q4); switch to `https://` only if Q4 puts
TLS in scope. Run each after `terraform apply` of the affected layer(s).

| Behavior | Input | Expected | Scorer | Threshold |
|----------|-------|----------|--------|-----------|
| MLflow and its oauth2-proxy are both running after apply | `nomad job status mlflow` (and `nomad job status <proxy-job>` if the proxy is standalone per Q2) | the `mlflow` task and the oauth2-proxy task both report `running`/`healthy`; deployment `Status = successful` | deterministic check (`nomad job status mlflow`) | 100% |
| An unauthenticated human hitting the UI is bounced to Vault OIDC, not served MLflow | `curl -sI http://mlflow.lab.orangecluster.nl/` | `HTTP/1.1 302` (or 307) with a `Location:` header pointing at the Vault OIDC authorize endpoint on `http://192.168.2.30:8200` ($VAULT_ADDR); NOT `200` and NOT MLflow HTML | deterministic check (`curl -sI http://mlflow.lab.orangecluster.nl/`) | 100% |
| A machine presenting a valid Nomad WI Bearer JWT reaches the MLflow REST API with no login | `TOKEN=$(nomad alloc exec <alloc-id> cat /secrets/mlflow_wi.jwt); curl -s -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $TOKEN" http://mlflow.lab.orangecluster.nl/api/2.0/mlflow/experiments/search` | `200` with a JSON experiments payload; the proxy validated the Bearer JWT and forwarded without a login redirect | deterministic check (`curl -H "Authorization: Bearer ..." .../api/2.0/mlflow/experiments/search`) | 100% |
| One oauth2-proxy instance handles BOTH the Vault OIDC auth-code login and Nomad WI Bearer-JWT validation across two issuers (load-bearing risk, Q3) | run the unauth-redirect input and the Bearer input above against the SAME running proxy alloc, without reconfiguring between them; if one instance cannot trust both issuers, record the fallback taken (dedicated bearer path, or WI tokens minted with the Vault-OIDC audience) in the caveat doc and Q3 | both flows pass from the same instance: unauth request returns 302-to-Vault and the Bearer request returns 200; R1 is NOT silently narrowed to humans-only | model + rubric (adversarial review agent) | 4/5 |
| An unauthenticated API request with neither session cookie nor Bearer token is BLOCKED from the MLflow UI/API (guardrail) | `curl -s -o /dev/null -w '%{http_code}' http://mlflow.lab.orangecluster.nl/api/2.0/mlflow/experiments/search` | `401` (or a `302` login redirect); NOT `200` and NOT the MLflow UI | deterministic check (`curl` unauth to `.../experiments/search`) | 100% |
| The old HAProxy basic-auth gate no longer fronts MLflow | `curl -sI http://mlflow.lab.orangecluster.nl/`; and `nomad alloc exec <haproxy-alloc> grep -A3 'backend mlflow' <cfg>` | no `WWW-Authenticate: Basic` header on the MLflow route, and no `http-request auth ... http_auth(openfang_users)` in the live `mlflow` backend (`haproxy.hcl:116`) — only the oauth2-proxy redirect | deterministic check (`curl -sI` + `nomad alloc exec grep 'backend mlflow'`) | 100% |
| The `/health` endpoint stays reachable unauthenticated so the Consul check does not flap (guardrail) | `curl -s -o /dev/null -w '%{http_code}' http://mlflow.lab.orangecluster.nl/health`; and `nomad job status mlflow` | `/health` returns `200` unauthenticated and the `mlflow` service check is passing | deterministic check (`curl http://mlflow.lab.orangecluster.nl/health`) | 100% |
