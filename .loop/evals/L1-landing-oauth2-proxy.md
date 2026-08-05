eval: L1-landing-oauth2-proxy

Definition of Done: oauth2-proxy runs healthy on the cluster and gates
`dash.lab.orangecluster.nl` at the HAProxy edge. An unauthenticated request is
refused, the OAuth cycle starts at Vault's `lab` provider, the
`/oauth2/callback` route is served, cookies are Secure and HttpOnly, and a
completed Vault login lets any authenticated user through to L1's own
upstream.

Rows re-cut twice on 2026-08-04, after two plan-validator passes each found
rows that fail a correct implementation. What the rows now encode:

- **A refusal at `/` can be a 40x OR a 302 to Vault.** Which one appears turns
  on `--skip-provider-button`. With it `false` (pinned by requirement 12) `/`
  renders the sign-in page; with it `true` the `/` handler redirects **straight
  to Vault**, not to a same-host `/oauth2/start` as a middle draft of the plan
  claimed. The row accepts both. The original marker demanded only the 302 and
  the first correction demanded only the 40x; each failed correct code under
  one flag setting.
- **`_oauth2_proxy` is the post-callback session cookie.** A pre-authentication
  request emits the CSRF cookie or none, so grepping `/` for `_oauth2_proxy`
  returns empty against correct code.
- **The final row asserted a 200 from L2's Homepage**, which L1 does not own
  and which declares a dependency on L1. L1 now ships
  `--upstream=static://200` and proves only its own gate.
- **Seven settings decide whether the job works**, and all seven are now
  scored in the guardrail row. **Two have env names that differ from their
  flag names** — oauth2-proxy reads env vars off each field's `cfg` struct
  tag, so every repeatable setting is singular as a flag and plural as an env
  var: `--email-domain` is `OAUTH2_PROXY_EMAIL_DOMAINS` and `--upstream` is
  `OAUTH2_PROXY_UPSTREAMS`. The upstream one is the dangerous half of this
  marker: the wrong spelling **passes every other row here** and fails only
  the hand-run browser row, so an operator sees nine-tenths green and then a
  404 after a full Vault login.
- Rows 2 through 5 were verified by running the container with this ticket's
  flag set against the live `lab` issuer: `/ping` 200 unauthenticated, `/`
  403, `/oauth2/start` 302 to
  `https://vault.lab.orangecluster.nl/ui/vault/identity/oidc/provider/lab/authorize`
  with `Set-Cookie: _oauth2_proxy_csrf=…; HttpOnly; Secure`, and a bare
  `/oauth2/callback` 500.

Preconditions: F2, T3 and A1 are `done` and applied. F2 shipped the `lab`
provider but no oauth2-proxy client, so L1 registers its own — the client, its
`allow_all` assignment, its key registration, and the entry in
`local.oidc_provider_client_ids`.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| The oauth2-proxy job is deployed and its allocation is healthy | `nomad job status oauth2-proxy` | `Status = running`, the latest deployment is `Successful`, and a `running`/`healthy` allocation with 0 failed. Four distinct ways to fail this row, all of which look like configuration that should work: (a) omitting `--email-domain=*` — oauth2-proxy **refuses to start** without an email allowlist and crash-loops, and note the env spelling is the plural `OAUTH2_PROXY_EMAIL_DOMAINS`; (b) registering the Vault client as `public` instead of `confidential` — Vault issues no client secret to a public client, so `OAUTH2_PROXY_CLIENT_SECRET` arrives empty and the container exits 1 with `missing setting: client-secret or client-secret-file`; (c) pointing the Nomad `check` at `/` instead of `/ping`, which leaves the allocation permanently unhealthy because `/` is what this ticket makes refuse callers; (d) placement — firebat has ~100 MHz of reservable CPU and is the only amd64 node, so a job sized or built for the wrong host never places | deterministic check (`nomad job status oauth2-proxy`) | 100% |
| An unauthenticated visitor is refused rather than served the upstream | `curl -sI https://dash.lab.orangecluster.nl/` | A `40x` (oauth2-proxy's sign-in page, the expected shape with `--skip-provider-button=false` pinned) **or** a `302` whose `Location` is Vault's authorize endpoint. Both are correct refusals; which one appears depends on that flag, and with the button skipped the `/` handler redirects straight to Vault rather than to a same-host `/oauth2/start`. The row accepts either so it cannot fail working code. What it rules out is a `200` from the upstream, which would mean the gate passes traffic through unauthenticated | deterministic check (`curl -sI` on `/`, expecting 4xx or a 302 to Vault) | 100% |
| The OAuth cycle starts at Vault, at the `lab` provider, with L1's client | `curl -sI 'https://dash.lab.orangecluster.nl/oauth2/start'` and read the `Location` header | A `302` whose `Location` is on `vault.lab.orangecluster.nl`, path `/ui/vault/identity/oidc/provider/lab/authorize`, carrying L1's `client_id`. The provider name `lab` must be asserted explicitly: live Vault also carries a built-in `default` provider whose `allowed_client_ids` is `["*"]`, so a probe that lands there passes while proving nothing | deterministic check (`curl -sI` on `/oauth2/start`) | 100% |
| The OIDC callback path is served by oauth2-proxy, not a dead route | `curl -sI https://dash.lab.orangecluster.nl/oauth2/callback` | Not a `404`. A bare probe carries no CSRF cookie and no authorization code, so the realistic response is a **500**; `302` and `400` also pass. Only `404` fails, meaning the callback was never wired. The 500 here is the correct answer to a request missing everything the callback needs — do not chase it | deterministic check (`curl -sI` on the callback) | 100% |
| Cookies carry Secure and HttpOnly, so nothing traverses cleartext | `curl -sI 'https://dash.lab.orangecluster.nl/oauth2/start' \| grep -i set-cookie` | Whatever cookie is emitted carries both `Secure` and `HttpOnly`. The row asserts the flags, not a name: at this point in the flow oauth2-proxy sets its CSRF cookie, not `_oauth2_proxy`, and it may set none at all — in which case the row is satisfied by the completed-flow row below instead | deterministic check (`curl -sI` on `/oauth2/start`, inspecting `Set-Cookie`) | 100% |
| A user who completes the Vault login gets through, under the flat policy | Complete the Vault auth-code flow for `https://dash.lab.orangecluster.nl/` in a browser, then re-request with the session cookie | `HTTP/2 200` from L1's own `static://200` upstream, and the `_oauth2_proxy` session cookie now present with `Secure` and `HttpOnly`. Two expected first-attempt behaviors that are NOT L1 bugs: Vault's authorize path is a UI path, so a browser holding no Vault UI session can fail the first attempt with a generic "Failed to sign in with SSO" and succeed on retry; and a refusal reading `identity entity not authorized by client assignment` means the client is bound to a tier group instead of `allow_all`, which is a real defect | model + rubric (adversarial review agent) | 4/5 |
| Guardrail: the seven settings that decide whether the job works are all correct | Read the rendered jobspec env for `OAUTH2_PROXY_EMAIL_DOMAINS`, `OAUTH2_PROXY_UPSTREAMS`, `OAUTH2_PROXY_OIDC_EMAIL_CLAIM`, `OAUTH2_PROXY_PROVIDER`, `OAUTH2_PROXY_HTTP_ADDRESS`, `OAUTH2_PROXY_SKIP_PROVIDER_BUTTON`, and the Nomad `check` path | **Two of these are plural in env form while their flags are singular**, because oauth2-proxy derives env names from each field's `cfg` struct tag: `EMAIL_DOMAINS` (flag `--email-domain`) is `*`, and `UPSTREAMS` (flag `--upstream`) is `static://200`. Both singular spellings are silently ignored. The email one then exits with "missing setting for email validation"; **the upstream one starts cleanly and passes every other row in this marker**, serving `404` to an authenticated user — verified by running the pinned container both ways. `OIDC_EMAIL_CLAIM` is `sub`; `PROVIDER` is `oidc` (default `google`); `HTTP_ADDRESS` binds `0.0.0.0` on the **static** port (default `127.0.0.1:4180` is unreachable, and under `network_mode = "host"` the Nomad `to` mapping is inert); `SKIP_PROVIDER_BUTTON` is `false`; the check path is `/ping`, not `/`. None of the seven shows up as a Terraform or `nomad fmt` error | deterministic check (read the rendered job env and check stanza) | 100% |
| Guardrail: the flat policy is flat at the Vault end, not just in the jobspec | Read the client's `assignments` in `oidc.tf`, and confirm the client id appears in `local.oidc_provider_client_ids` | `assignments = ["allow_all"]` with no `vault_identity_oidc_assignment` created for L1, and the client id present in the provider's allowed list. Omitting the list entry makes Vault refuse the authorization request; binding a tier group instead of `allow_all` makes the stated any-authenticated-user policy false while every other row still passes | deterministic check (read the two `oidc.tf` sites) | 100% |
| Guardrail: existing edge auth and routing are untouched | Inspect the live HAProxy config after apply | `backend phoenix` still carries `http-request auth unless { http_auth(openfang_users) }` and so does `backend mlflow`; the ten pre-existing ACLs still route; the `dash` ACL was added to `https_in`, not `http_in`. An ACL on `http_in` sits on the redirect-only frontend and can never route, which presents as `dash` still returning 503 with a config that looks correct | deterministic check (config inspection) | 100% |
