eval: L1-landing-oauth2-proxy

Definition of Done: oauth2-proxy runs healthy on the cluster and gates
`dash.localstack` at the HAProxy edge — every unauthenticated request is
BLOCKED and 302-redirected to the Vault OIDC authorize endpoint, the
`/oauth2/callback` route is served, session cookies are Secure+HttpOnly, and
a completed Vault auth-code flow lets any authenticated user through to the
landing upstream. Hard deps: F2 (Vault OIDC client) and F3 (TLS edge bind)
must be merged and applied before the close-out rows can pass.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| The oauth2-proxy job is deployed and its allocation is healthy | `nomad job status oauth2-proxy` | `Status = running`, the latest deployment is `Successful`, and a `running`/`healthy` allocation with 0 failed | deterministic check (`nomad job status oauth2-proxy`) | 100% |
| An unauthenticated visitor to the protected landing page is redirected to Vault to log in | `curl -sI https://dash.localstack/` | `HTTP/2 302` with a `Location:` header pointing at the Vault OIDC authorize endpoint under `$VAULT_ADDR/v1/identity/oidc/provider/<provider-name>/authorize?...` (matching F2's issuer host and path) | deterministic check (`curl -sI https://dash.localstack/`) | 100% |
| An unauthenticated visitor is BLOCKED from the landing upstream — never served through | `curl -sI https://dash.localstack/` | Response is the `302` redirect to Vault, NEVER a `200` from the landing upstream; no request without a valid session cookie reaches the backend | deterministic check (`curl -sI https://dash.localstack/`) | 100% |
| The OIDC callback path is served by oauth2-proxy, not a dead route | `curl -sI https://dash.localstack/oauth2/callback` | Not a `404` — oauth2-proxy handles the route (a `302`/`400` from the proxy is fine); a `404` means the callback was never wired | deterministic check (`curl -sI https://dash.localstack/oauth2/callback`) | 100% |
| The session cookie is set Secure+HttpOnly so it never traverses cleartext (requires F3 TLS, else redirect loop) | `curl -sI https://dash.localstack/ \| grep -i set-cookie` | The `_oauth2_proxy` cookie in `Set-Cookie` carries both `Secure` and `HttpOnly` attributes | deterministic check (`curl -sI https://dash.localstack/ \| grep -i set-cookie`) | 100% |
| A user who completes the Vault login reaches the landing page under the flat any-authenticated-user policy | Complete the Vault auth-code flow for `https://dash.localstack/` in a browser (or scripted), then `curl -sI https://dash.localstack/` with the session cookie | `HTTP/2 200` reaching the landing-page upstream, confirming the flat "any authenticated user allowed" policy lets the session through | model + rubric (adversarial review agent) | 4/5 |
