eval: B2-bifrost-oauth2-proxy

Definition of Done: a browser hitting `https://bifrost.lab.orangecluster.nl`
must pass a Vault OIDC login before seeing any Bifrost content, while
`/v1/*` and `/anthropic/*` pass through the edge to Bifrost's own
virtual-key auth untouched, and no direct consumer (Hermes, Memex,
Prometheus, Terraform) changes at all.

Rows 1-7 are static assertions against the ticket's diff and rendered
HCL/TF, runnable by the loop. Rows 8-9 need a `terraform apply` the loop
never performs; the operator runs them post-apply.

| Behavior | Input | Expected | Fails-when | Scorer | Threshold |
|----------|-------|----------|------------|--------|-----------|
| Skip-auth list is exactly the two anchored inference prefixes | `grep -n 'SKIP_AUTH' deployments/infrastructure/services/oauth2-proxy-bifrost.hcl` | One skip-auth env (exact name container-verified per plan P10, plural form) whose value contains `^/v1/` and `^/anthropic/` and no other route entry | An entry lacks its `^` anchor (so `/foo/v1/` would skip), a third prefix appears, or the env name is a singular/misspelled variant the container silently ignores | Deterministic grep on that one jobspec | 100% |
| Proxy upstreams to Bifrost over loopback | `grep -n 'UPSTREAMS' deployments/infrastructure/services/oauth2-proxy-bifrost.hcl` | A single catch-all upstream `http://127.0.0.1:8080` | The upstream names `bifrost.lab.orangecluster.nl`, `192.168.2.50`, or any port other than 8080 | Deterministic grep on that one jobspec | 100% |
| Edge routes bifrost traffic through the new proxy | `grep -n -A1 'backend bifrost' deployments/infrastructure/services/haproxy.hcl` | The `backend bifrost` server line reads `192.168.2.50:4181`; the `is_bifrost` acl and `use_backend` lines are unchanged | The server line still says `:8080`, or any haproxy.hcl line outside `backend bifrost` changed | Deterministic grep + `git diff` scoped to haproxy.hcl | 100% |
| Guardrail: the applications root is untouched | `git diff --stat <ticket base>..HEAD -- deployments/applications/` | Empty output: `bifrost.hcl`, the bifrost provider, and the virtual keys are byte-identical | Any file under `deployments/applications/` appears in the diff | Deterministic git diff | 100% |
| The OIDC client is fully registered against provider `lab` | `grep -n 'oauth2_proxy_bifrost\|oidc_provider_client_ids' deployments/infrastructure/oidc.tf` | A confidential `vault_identity_oidc_client` with `assignments = ["allow_all"]`, a matching `vault_identity_oidc_key_allowed_client_id`, and its client id appended to `local.oidc_provider_client_ids` | The client resource exists but its id is absent from `local.oidc_provider_client_ids` (terraform applies clean, Vault refuses every authorize at runtime) | Deterministic grep on oidc.tf | 100% |
| Guardrail: secrets live only in KV under the job-name prefix | `grep -rn 'client_secret\|cookie' deployments/infrastructure/secrets.tf deployments/infrastructure/services/oauth2-proxy-bifrost.hcl` | Client and cookie secrets exist only as KV2 resources at `default/oauth2-proxy-bifrost/oidc` and `default/oauth2-proxy-bifrost/cookie`, rendered into the job via `template { env = true }`; no secret literal in any `.tf` or jobspec | A literal secret value appears in tracked source, or the KV path prefix differs from the Nomad job name (nomad-workloads policy denies the read) | Deterministic grep over the two files | 100% |
| Firewall admits only HAProxy to the proxy port | `grep -n '4181' deployments/infrastructure/services.tf` | A ufw rule allowing `192.168.2.30` to port 4181/tcp, shaped like the existing 4180 rule, and no wider allow for 4181 | The rule is missing (HAProxy cannot reach the proxy) or allows from any/LAN-wide source | Deterministic grep on infrastructure services.tf | 100% |
| A human at the edge meets Vault login before any Bifrost content (verdict: pending-operator) | A fresh browser session opening `https://bifrost.lab.orangecluster.nl/` | Redirect to the Vault `lab` provider authorize page; after userpass login the Bifrost dashboard loads (its own admin login is then the accepted second factor) | Any Bifrost UI or `/api/*` response is served without the OIDC redirect first | Human (operator, post-apply) | 100% |
| Edge inference passes through to virtual-key auth untouched (verdict: pending-operator) | `curl -X POST https://bifrost.lab.orangecluster.nl/v1/chat/completions` with no credentials, then the same with a valid `x-bf-vk` virtual key | First call returns Bifrost's own 401 JSON (virtual-key refusal), not a 302/login HTML from oauth2-proxy; second call returns a model response | The keyless call gets a 302 or login page (skip regex wrong or env name ignored), or the keyed call is blocked by the cookie gate | Human (operator, post-apply) | 100% |

signed-off-by: jasperginn 2026-09-03
plan: c30e3a5e0fc66584acd6eaa259a9423b62111b5917e39464b3231e8a5fa85260
