---
epic = "landing"
depends_on = ["F2-foundation-vault-oidc-provider", "T3-tls-edge-cutover-lab-domain", "A1-audit-plan-premise-sweep"]
priority = 30
summary = "Deploy oauth2-proxy as an OIDC client against Vault's provider, gating the cluster landing page at the HAProxy edge with a flat any-authenticated-user policy and HTTPS-only cookies. Establishes the forward-auth pattern R1 and R4 copy."
tags = ["oauth2-proxy", "haproxy", "oidc", "vault"]
---

# Ticket: L1-landing-oauth2-proxy

## 1. Title
Deploy oauth2-proxy as an OIDC client (against Vault's OIDC provider) that
gates the cluster landing page at the HAProxy edge, with a flat "any
authenticated user is allowed" policy and HTTPS-only cookies.

## 2. Size / Effort
**Medium.** One new Nomad jobspec, one new `nomad_job` + secret in Terraform,
one new OIDC client, and one new HAProxy frontend ACL + backend.
*(Rewritten 2026-08-04.)* The effort driver used to be two cross-ticket
seams — the Vault OIDC credential path and the TLS edge bind — and both are
now closed: F2 and T3 are `done`, the edge serves TLS, and L1 creates its own
client rather than waiting on someone else's. What is left is getting
oauth2-proxy's own flags right against an issuer that emits no `email` claim.
See requirements 5, 7b and 12, each of which is a way for a plausible-looking
jobspec to crash-loop or 500 at the callback.

## 3. Triggered by
Home-lab auth epic. Two human-facing services still sit behind a single
shared HTTP basic-auth user (`openfang_users`) declared inline in
`deployments/infrastructure/services/haproxy.hcl:88-89` and applied to the
phoenix (`haproxy.hcl:143`) and mlflow (`haproxy.hcl:153`) backends. **Not
bifrost**: `B1-bifrost-native-auth-and-virtual-keys` removed its line in
commit `ac3267b`, so `backend bifrost` (`haproxy.hcl:156-157`) is a bare
`server` line. The epic replaces shared basic-auth with real SSO: Vault is
the OIDC IdP (Zitadel dropped), and oauth2-proxy is the per-edge gate. L1
lands that gate for the landing page first and establishes the reusable
pattern that R1 (MLflow) copies.

## 4. Context (re-anchored and re-measured live 2026-08-04)

The whole of this section was rewritten on 2026-08-04. The previous text
described the pre-F3 edge and had been contradicted by requirement 11 inside
the same plan.

- **The edge terminates TLS.** HAProxy is pinned to host `firebat` and binds
  two frontends. `haproxy.hcl:91-93` is `frontend http_in` / `bind *:80` /
  `http-request redirect scheme https code 301 unless { ssl_fc }` — it
  redirects and carries no ACL. `haproxy.hcl:95-96` is `frontend https_in` /
  `bind *:443 ssl crt /secrets/haproxy.pem`, serving a publicly-trusted
  Let's Encrypt wildcard rendered from Vault KV2 by the template at
  `haproxy.hcl:62-72`. The static ports are `haproxy.hcl:10-18`, which
  includes `port "https" { static = 443 }`.
- **All routing lives on `https_in`.** Every `acl` and `use_backend` is at
  `haproxy.hcl:98-118`; the static `server ip:port` backends are at
  `haproxy.hcl:127-157`. Backends are static, not Consul-discovered. **An ACL
  added to `http_in` lands on the redirect-only frontend and can never
  route.**
- Existing auth is HTTP basic-auth: a `userlist` (`haproxy.hcl:88-89`) fed by
  a Terraform `random_password` (`secrets.tf:32-44`), enforced on two
  backends only via `http-request auth unless { http_auth(openfang_users) }`
  (`haproxy.hcl:143`, `:153`).
- **No landing-page service and no `dash.lab.orangecluster.nl` ACL/backend exist**
  today (`grep dash` in `haproxy.hcl` returns nothing; the only `dash`
  matches in the tree are Grafana *dashboard* files). Live: `curl -sI
  https://dash.lab.orangecluster.nl/` returns `503` — the TLS handshake
  succeeds against the wildcard and HAProxy has no matching backend. So DNS
  and the certificate are already in place and nothing is needed there.
- **Vault's OIDC provider exists and F2 is `done`.** The issuer is
  `https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab`
  (`deployments/infrastructure/oidc.tf:95-101`, `https_enabled = true`). The
  provider is named `lab`. **Point at `lab`, never at Vault's built-in
  `default` provider**, whose `allowed_client_ids` is `["*"]` and whose issuer
  is a raw-IP `http://` URL; a check that accidentally hits `default` passes
  against the wrong issuer.
- **F2 did not ship an oauth2-proxy client. L1 adds its own.**
  `local.oidc_provider_client_ids` (`oidc.tf:80-84`) names three clients:
  smoke, nomad, memex. `docs/vault-human-auth.md:264-300` is the written
  consumer procedure and is the authority here, not a guess about what F2
  might have done.
- Vault-templated-secret pattern to copy: Grafana declares `vault {}`
  (`grafana.hcl:29`) and injects a secret through
  `template { ... env = true }` reading
  `{{ with secret "<path>" }}{{ .Data.data.<key> }}{{ end }}`
  (`grafana.hcl:77-84`). The secret itself is a `random_password` +
  `vault_kv_secret_v2` pair (`secrets.tf:47-66`).
- Nomad-job wiring pattern to copy: `resource "nomad_job" "<name>"` with
  `jobspec = templatefile("${path.module}/services/<name>.hcl", { ... })`.
  HAProxy is `services.tf:318-326`; Grafana is `services.tf:346-368`.
- Providers declared: `nomad`, `vault`, `null` and `google`
  (`providers.tf:1-24`, configured at `:26-32`). The Consul provider is
  commented out at `providers.tf:19-22`.
- **Node capacity, measured live 2026-08-04** (`nomad node status`). This
  settles Q6, which the earlier plan left pending exactly this check:

  | node | arch | CPU alloc | memory alloc |
  |---|---|---|---|
  | firebat | **amd64** | 3100/3200 MHz | 6.4/15 GiB |
  | orangepi4a | arm64 | 6400/10828 MHz | 3.2/3.3 GiB |
  | radxa-dragon-q6a | arm64 | 3950/17239 MHz | 3.8/6.9 GiB |
  | ubuntu | arm64 | 2600/6700 MHz | 2.1/3.2 GiB |
  | jetson-orin-nano | arm64 | 4400/9868 MHz | 7.0/6.9 GiB |

  firebat has **100 MHz of reservable CPU left** and is the cluster's only
  amd64 node. Colocating oauth2-proxy there, as the earlier resolution
  preferred, is not possible for any job reserving more than 100 MHz.
  `radxa-dragon-q6a` (192.168.2.50) has the most room on both axes and
  already hosts mlflow and bifrost, which HAProxy reaches at that address
  (`haproxy.hcl:154`, `:157`).

## 5. Non-goals / out of scope
- **No per-user RBAC or group/role mapping.** Access is FLAT: anyone who
  completes Vault login is allowed through. Fine-grained authz is IdP
  territory and is explicitly not wanted.
- **Not F2.** This ticket does not create the Vault OIDC provider, the
  `vault_identity_oidc_client` for oauth2-proxy, the issuer, or the human
  user/identity setup. It consumes them.
- **Not F3.** This ticket does not add the TLS `bind ... ssl` at HAProxy or
  provision Vault PKI certs. It assumes the edge serves HTTPS and sets
  cookie flags accordingly.
- **Not R1/R4.** Do not wire MLflow or Phoenix through oauth2-proxy here.
  L1 only establishes the reusable pattern and documents it.
- Do not migrate or remove the existing `openfang` basic-auth. It survives on
  two backends, phoenix (`haproxy.hcl:143`) and mlflow (`:153`). Leave both
  untouched. Bifrost is not mentioned because B1 already removed its line.
- Do not build the landing-page content/app itself if the operator decides
  it is a separate ticket (see Open Questions Q1).

## 6. Requirements & restrictions
1. oauth2-proxy runs as a Nomad `service` job under
   `deployments/infrastructure/services/`, driver `podman`, on a host with
   room for it, with an image whose architecture **matches the chosen host**.
   Pin an explicit image tag, matching the pinned-tag convention (e.g.
   `grafana.hcl:48`, `nats.hcl:69`).
   *(Rewritten 2026-08-04. This requirement used to say "arm64-compatible
   image, because cluster nodes are Orange Pi / ARM boards". The conclusion
   happened to be right and the reason was wrong: firebat, the host the
   earlier resolution preferred, is the cluster's only **amd64** node, so an
   arm64-only image would not have run at the recommended placement. Pick the
   host and the image architecture together, in that order — see §4's capacity
   table and Q6.)*
2. Client credentials (`client_id`, `client_secret`), the cookie secret, and
   the Vault issuer/discovery URL are injected via a Vault-templated
   `template { env = true }` block reading `secret/data/<ns>/<job>/<entry>`,
   never hardcoded (`CLAUDE.md` Secrets convention; pattern
   `grafana.hcl:77-84`). Requires a `vault {}` stanza (pattern
   `grafana.hcl:29`).
3. The cookie secret is generated in Terraform as a `random_password` and
   written to Vault KV2, mirroring `secrets.tf:46-66`. oauth2-proxy requires
   the cookie secret to be exactly 16, 24, or 32 bytes — size it so the
   stored value decodes to one of those lengths (see Open Questions Q3).
4. Redirect URL is `https://dash.lab.orangecluster.nl/oauth2/callback`; cookies must be
   set `Secure` (`--cookie-secure=true`) so they never traverse cleartext.
   This is why the ticket depends on F3.
5. **Flat access, on both sides of the flow.** The gate is flat only if BOTH
   ends are flat, and it takes an explicit flag at each end. "Leave the
   restriction off" is wrong on both sides.
   - **oauth2-proxy side: the flag is `--email-domain=*`, and the env var is
     `OAUTH2_PROXY_EMAIL_DOMAINS` — plural.** Put it in a jobspec comment so
     copyists keep it. This is not optional and it is not the default:
     oauth2-proxy **refuses to start** when none of `--email-domain`,
     `--authenticated-emails-file` or `--htpasswd-file` is set, aborting with
     "missing setting for email validation" and naming `email-domain=*` as the
     way to authorize everyone (`validation.Validate`, in
     `pkg/validation/options.go`).
     See requirement 17 for why the env name differs from the flag; this is an
     instance of a general rule, not a quirk of this one setting. Two earlier
     drafts of this requirement produced the same crash-loop, first by omitting
     the setting and then by naming it in the singular.
   - **Vault side, which is the one that actually refuses people:** a Vault
     OIDC client is bound to an assignment, and a user outside it is refused
     at the authorize endpoint with `error=access_denied&error_description=
     identity entity not authorized by client assignment`. For flat access
     the answer is branch 3 of the documented procedure
     (`docs/vault-human-auth.md:282-290`): set `assignments = ["allow_all"]`
     on the client — Vault's built-in, `entity_ids [*]`, `group_ids [*]` —
     and create no `vault_identity_oidc_assignment` at all. Do **not** bind
     to `dashboard-users` or any other tier group; that would silently make
     the stated policy false.
6. Wire the gate into HAProxy for the `dash.lab.orangecluster.nl` host: add the
   ACL and `use_backend` **in the `https_in` frontend** (`haproxy.hcl:98-118`)
   and the backend definition alongside the others at `haproxy.hcl:127-157`.
   Reverse-proxy mode, per the operator's resolved Q2: HAProxy routes
   `dash.lab.orangecluster.nl` to oauth2-proxy as an ordinary backend.
7. Terraform must add a `resource "nomad_job" "oauth2_proxy"` using
   `templatefile(...)`, following the HAProxy block at `services.tf:318-326`
   and the Grafana block at `services.tf:346-368`, and pass the Vault secret
   path(s) as template vars.
7a. **Register the client as `client_type = "confidential"`**, which is the
   default and what the cited templates use. oauth2-proxy holds a real client
   secret, so confidential is correct here, and `memex_oidc.tf:80` is `public`
   — an implementer copying that file gets the wrong type.
   **The failure is loud, not silent.** Vault issues **no client secret at all
   to a public client**: secret generation is gated on the confidential type,
   and reading a public client back returns none. Confirmed live —
   `oidc-smoke` (confidential) returns a 75-character secret, `memex` (public)
   returns nothing. So the mistake yields an empty
   `OAUTH2_PROXY_CLIENT_SECRET`, and the pinned container exits 1 with
   `missing setting: client-secret or client-secret-file`. That is the
   `--email-domain` shape — a crash-loop that fails §8 row 1 — **not** the
   silent `--upstream` shape. An earlier draft of this requirement claimed the
   opposite, which would have led an operator with an unhealthy allocation to
   rule `client_type` out as the cause.
   There is a second, independent reason a public client would not work here,
   though nobody reaches it: Vault requires PKCE for public clients, and
   oauth2-proxy sends no code challenge unless `--code-challenge-method` is
   set. The container warns about this at startup.
   **Register the client the way the repo documents.**
   `docs/vault-human-auth.md:264-300` is the procedure and it is not optional
   trivia: a `vault_identity_oidc_client` with the real `redirect_uris`;
   `assignments = ["allow_all"]` per requirement 5; a
   `vault_identity_oidc_key_allowed_client_id` registering the client against
   the `lab` signing key; and an entry appended to
   `local.oidc_provider_client_ids` (`oidc.tf:80-84`). **Omit that last line
   and Vault refuses the authorization request**, since the provider gates on
   `allowed_client_ids` and offers no standalone resource for it.
7b. **`--oidc-email-claim=sub`, because Vault issues no `email` claim.**
   This is the second half of requirement 5 and the second way this job can
   look correct and fail. oauth2-proxy does not merely *filter* on email — it
   requires one to build a session, and errors when the claim is empty
   (`OIDCProvider.EnrichSession`), which surfaces as a **500 at
   `/oauth2/callback`** (`OAuthProxy.OAuthCallback`) after an otherwise
   successful Vault login. Vault's `lab` provider emits `groups` and nothing
   else: its only scope template is `oidc.tf:55-70`, and live discovery
   returns `scopes_supported: ["groups","openid"]` with `claims_supported:
   []`. Pointing the email claim at `sub`, which every Vault ID token carries,
   gives oauth2-proxy the entity UUID to use as an identity; `--email-domain=*`
   is then what lets that non-email value past validation. The two flags only
   work together.
7c. **Request the `groups` scope explicitly if anything reads it.** Vault
   ignores an unrequested scope rather than erroring, so a client that sets
   `--oidc-groups-claim` and leaves `--scope` at its default gets a signed
   token with no `groups` claim and nothing complains
   (`docs/vault-human-auth.md:300-306`). L1 is flat and reads no group claim,
   so `openid` is enough for **scope** purposes — but say so in the jobspec,
   because R1 copies this file and may not be flat. Do not read this as
   "L1 needs no claim configuration at all": requirement 7b still applies.
8. Reusability: document (in a comment header in the new jobspec, and/or the
   HAProxy backend comment) that the same job/pattern fronts MLflow (R1) and
   Phoenix (R4). Keep host/redirect/issuer values as template vars so the
   pattern is copyable without editing the job body. Respect `CLAUDE.md`
   Simplicity/Surgical rules: no speculative multi-app config now.
9. Match existing HCL style; the gate reformats via `nomad fmt` (see below).
10. **DISCHARGED by T3-tls-edge-cutover-lab-domain, 2026-07-26. Nothing to do
    here.** *(This requirement was relayed from
    F3-foundation-haproxy-tls-vault-pki, 2026-07-24, and is kept as a record
    rather than deleted.)* F3 made the edge HTTPS-only while leaving `docs/`
    outside its Code surface, so `docs/haproxy_reverse_proxy.md` and
    `docs/monitoring.md` still described a cleartext edge reached through
    `/etc/hosts`. L1 was assigned the fix as the next ticket to touch the
    edge.
    T3 took it instead, because T3 renamed every hostname in those same
    documents and fixing them anywhere else would have meant editing the same
    lines twice. Both are now current, and the root-CA caveat that used to
    belong here is moot: the edge serves a publicly-trusted Let's Encrypt
    certificate, so no client installs anything.
11. **The host is `dash.lab.orangecluster.nl`, and its ACL goes on
    `https_in`, not `http_in`.** *(Rewritten 2026-07-25, updated 2026-07-26
    once T3 landed. Supersedes the earlier F3-era text, which named
    `dash.localstack` and is now wrong.)*
    - F3 split the single frontend: `:80` only 301-redirects, and every ACL
      lives on the `:443 ssl` frontend `https_in`. An ACL added to `http_in`
      sits on the redirect-only frontend and can never route.
    - T3 renamed the whole edge to `<svc>.lab.orangecluster.nl` and replaced
      the unusable Vault-PKI leaf with a publicly-trusted Let's Encrypt
      wildcard. **L1 depends on T3, not F3** (front-matter updated), so the
      old names are already gone.
    - No cert work follows: the wildcard `*.lab.orangecluster.nl` already
      covers `dash`. No PKI change, no SAN edit, no new firewall rule.
    - `dash.lab.orangecluster.nl` resolves from public DNS via the `*.lab`
      wildcard A record, with no DNS record to add. The dnsmasq resolver that
      used to answer this zone was removed by
      N2-netsec-remove-dnsmasq-for-public-dns.
12. **Pin `--skip-provider-button=false`** (its default). It keeps the sign-in
    page in the flow, which makes the gate's behavior at `/` deterministic for
    §8 row 2, and it avoids jumping a browser straight at Vault's **UI**
    authorize path — the case that fails opaquely when the browser holds no
    Vault UI session (`docs/vault-human-auth.md:324-330`). If a later ticket
    wants the button skipped, it must widen §8 row 2 in the same change.
13. **The health check probes `/ping`, not `/`.** `/ping` is oauth2-proxy's
    dedicated health endpoint, served by `middleware.NewHealthCheck` inside
    `OAuthProxy.buildPreAuthChain` — **ahead of the mux**, which is precisely
    why it answers **200 without authentication** — verified by
    running the container with this ticket's flag set against the live `lab`
    issuer. Pointing a Nomad `check` at `/` gives a permanently unhealthy
    allocation, because `/` is exactly what this ticket makes refuse an
    unauthenticated caller (measured: `403`).
14. **`--provider=oidc`.** The default provider is `google`, so omitting this
    points the whole flow at the wrong IdP regardless of how correct the
    issuer, client and scope settings are.
15. **`--http-address=0.0.0.0:<port>`, where `<port>` is the `static` port.**
    The default is `127.0.0.1:4180`, which is reachable from neither HAProxy
    on another node nor the Nomad `check` on `/ping`. Loopback-only is the
    right default for a laptop and wrong for every deployment here — every
    podman task in this repo runs `network_mode = "host"`, so loopback means
    the chosen node's own loopback. Under host networking the Nomad `to`
    mapping is **inert**: `haproxy.hcl:11-15` declares `static = 80` with
    `to = 8080` while `:30` sets `network_mode = "host"`, and HAProxy binds
    `*:80` regardless. So bind the `static` port, never the `to` port.
16. **Pin the oauth2-proxy version in the jobspec** (requirement 1 already
    requires a pinned tag; this names why it matters twice over). Upstream
    citations in this plan are given as **symbol names**, not line numbers,
    because line numbers drift between the project's main branch and the
    pinned `v7.13.0`: `validation.Validate`, `OIDCProvider.EnrichSession`,
    `SecretBytes`, `OAuthProxy.OAuthCallback`, `OAuthProxy.doOAuthStart`,
    `OAuthProxy.Proxy`, `OAuthProxy.buildPreAuthChain`,
    `middleware.NewHealthCheck`. Every behavioral claim in this plan was verified by
    running the pinned container against the live `lab` issuer rather than by
    reading, so the claims survive the drift even where a coordinate would
    not.
17. **Read every oauth2-proxy env var name off its `cfg` struct tag, not off
    its flag name. Repeatable settings are singular as a flag and PLURAL as an
    env var.** This is the general rule; `--email-domain` in requirement 5 is
    one instance and `--upstream` is another, and each of them has already
    shipped a bug in this plan. The tags were pulled from `/bin/oauth2-proxy`
    inside the pinned `quay.io/oauth2-proxy/oauth2-proxy:v7.13.0` image and
    each behavior confirmed by running the container:

    | flag | env var | same? |
    |---|---|---|
    | `--email-domain` | `OAUTH2_PROXY_EMAIL_DOMAINS` | **no, plural** |
    | `--upstream` | `OAUTH2_PROXY_UPSTREAMS` | **no, plural** |
    | `--oidc-email-claim` | `OAUTH2_PROXY_OIDC_EMAIL_CLAIM` | yes |
    | `--skip-provider-button` | `OAUTH2_PROXY_SKIP_PROVIDER_BUTTON` | yes |
    | `--http-address` | `OAUTH2_PROXY_HTTP_ADDRESS` | yes |
    | `--provider` | `OAUTH2_PROXY_PROVIDER` | yes |
    | `--cookie-secure` | `OAUTH2_PROXY_COOKIE_SECURE` | yes |
    | `--redirect-url` | `OAUTH2_PROXY_REDIRECT_URL` | yes |
    | `--client-id` | `OAUTH2_PROXY_CLIENT_ID` | yes |
    | `--client-secret` | `OAUTH2_PROXY_CLIENT_SECRET` | yes |
    | `--cookie-secret` | `OAUTH2_PROXY_COOKIE_SECRET` | yes |
    | `--oidc-issuer-url` | `OAUTH2_PROXY_OIDC_ISSUER_URL` | yes |
    | `--reverse-proxy` | `OAUTH2_PROXY_REVERSE_PROXY` | yes |
    | `--scope` | `OAUTH2_PROXY_SCOPE` | yes |

    R1 copies this jobspec, so it inherits the check rather than the two
    exceptions. Any setting added later must be looked up the same way.
18. **`--upstream=static://200` is `OAUTH2_PROXY_UPSTREAMS` in env form, and
    getting it wrong is the quietest failure in this ticket.** Unlike the
    email-domain bug, which crash-loops and fails the very first eval row, the
    singular spelling **starts cleanly**. Verified by running the pinned
    container both ways against the live issuer: with the plural name the log
    carries `mapping path "/" => static response 200` and an authenticated
    request returns `200`; with the singular name there is no mapping line at
    all and the same request returns `404 page not found`. The container
    reports `running` in both cases, `/ping` returns 200 in both, and `/`
    returns 403 in both. So it passes §8 rows 2 through 5 and every guardrail,
    and fails only the hand-run browser row — the operator completes a full
    Vault login and lands on a 404 with nine-tenths of the suite green.
19. **Pin `OAUTH2_PROXY_SCOPE=openid`.** oauth2-proxy requests
    `openid email profile` by default (confirmed in the live redirect), while
    Vault's `lab` provider advertises only `["groups","openid"]`. Vault is
    expected to ignore the unsupported extras rather than reject the request,
    but that claim is not verified here — an unauthenticated probe of the
    authorize endpoint returns `permission denied`, so it could not be
    reproduced. Asking only for what the provider advertises costs one env var
    and removes the dependency on that behavior entirely. `--scope` is
    `cfg:"scope"`, singular, so the env name above is correct as written.

## 7. Code surface
- `deployments/infrastructure/services/oauth2-proxy.hcl` **(new)** — the
  Nomad job: `podman` task, an image matching the chosen host's architecture,
  `vault {}` stanza, a `template { env = true }` block for `OAUTH2_PROXY_*`
  env (client id/secret, cookie secret, OIDC issuer, redirect URL), a
  `service` + health `check` **against `/ping`**
  (pattern `nats.hcl:50-66`, `grafana.hcl:31-45`), `network` port, and a
  `resources` block. Header comment noting R1/R4 reuse.
- `deployments/infrastructure/services.tf:318-326` — add a new
  `resource "nomad_job" "oauth2_proxy"` block near the HAProxy job, using
  `templatefile` with the Vault secret path var(s); the fuller pattern to
  copy is the Grafana block at `services.tf:346-368`.
- `deployments/infrastructure/oidc.tf` — the client, its key registration,
  and the `local.oidc_provider_client_ids` entry, per requirement 7a.
- `deployments/infrastructure/secrets.tf:47-66` — add a `random_password`
  (cookie secret) + `vault_kv_secret_v2` pair under **oauth2-proxy's own
  prefix**, mirroring the Grafana admin block.
  **The OIDC client secret is a different matter and must not be copied into
  KV2.** `docs/vault-human-auth.md:314-322` says a consumer that is itself a
  Terraform resource should pass the secret by reference and skip KV2
  entirely, as `nomad_oidc.tf` does. oauth2-proxy is not that case — it reads
  its config at run time through a `template` stanza — so it does write its
  client secret to KV2 under its own prefix. Note the hazard the same
  paragraph records: `detect-private-key` will **not** catch a Vault client
  secret, because it matches a fixed list of PEM headers and `hvo_secret_...`
  is not one. The hook staying green is not evidence the secret stayed out of
  the repo.
- `deployments/infrastructure/services/haproxy.hcl:98-118` — add
  `acl is_dash hdr(host) -i dash.lab.orangecluster.nl` and
  `use_backend dash if is_dash` **in the `https_in` frontend**, beside the
  ten ACLs already there.
- `deployments/infrastructure/services/haproxy.hcl:127-157` — add a `backend
  dash` pointing at the oauth2-proxy address:port, a static `server` line
  matching the existing style. On `radxa-dragon-q6a` that is a
  `192.168.2.50:<port>` line, the same shape as `backend mlflow`
  (`haproxy.hcl:154`) and `backend bifrost` (`:157`).
- **`X-Forwarded-Proto` is not set at the edge, and oauth2-proxy cares.**
  A grep for `forwardfor|X-Forwarded|set-header` over `haproxy.hcl` returns
  nothing: TLS terminates at HAProxy and the backend sees plain HTTP.
  oauth2-proxy's `--reverse-proxy` flag exists for exactly this, controlling
  whether it accepts `X-Forwarded-{Proto,Host,Uri}` for redirect selection.
  Decide both halves together — whether HAProxy starts sending the header and
  whether oauth2-proxy trusts it — or set `OAUTH2_PROXY_REDIRECT_URL`
  explicitly so the redirect never depends on inference. This was an unstated
  requirement hiding under the "purely additive" claim.
- `deployments/infrastructure/variables.tf` — if the OIDC issuer, provider
  name, or oauth2-proxy host is operator-supplied, add a `variable` here and
  thread it through `prod.tfvars`. That file is gitignored and seeded by
  `just worktree_setup`; `vars/prod.tfvars.example` is the tracked template.

## 8. Tests & validation gates

### Repo gate (blessed invocation): `just pre_commit`
Runs `pre-commit run --all-files` (root `justfile` `pre_commit` recipe). The
config is now **Terraform-aware**, so this single command is the full
pre-apply gate for both the HCL jobspec and the `.tf` changes
(`.pre-commit-config.yaml`):
- `nomad-fmt` (`nomad fmt -recursive`, local hook, `types: [hcl]`) on every
  `*.hcl`. New/edited jobspec HCL must be `nomad fmt`-clean; run
  `just format` first.
- `terraform-fmt` (`terraform fmt -check -recursive`, local hook,
  `types: [terraform]`) on every `*.tf`. Edits to `services.tf`,
  `secrets.tf`, and `variables.tf` must be `terraform fmt`-clean.
- `terraform-validate` (`scripts/tf_validate.sh`, local hook,
  `types: [terraform]`) — validates every Terraform root offline
  (`init -backend=false` then `terraform validate`, no remote state, no
  credentials). The new `nomad_job`, `random_password`, and
  `vault_kv_secret_v2` resources must pass `terraform validate` here; this is
  part of the gate, not a separate manual step.
- `check-json` / `check-yaml --unsafe` / `end-of-file-fixer` /
  `detect-private-key` on touched files. The generated cookie/client secrets
  live in Vault, never in-repo, so `detect-private-key` must stay green.
- `.pre-commit-config.yaml` sets `exclude: '^\.(claude|loop)/'`, so this
  ticket file and the `.loop/` tree are not linted.

There is no unit-test harness for Nomad or Terraform jobspecs in this repo, so
the Python testing rule in `.claude/rules/python-testing.md` does not reach
anything this ticket writes. Note the narrower claim: the repo **does** run
pytest, via the `cli/`-scoped pre-commit hook at
`.pre-commit-config.yaml:66-73`, and it **does** have GitHub workflows under
`.github/workflows/`. Neither covers HCL. `terraform validate` through the
gate is the static check; behavioral verification is the live evals below.

### Evals (live) — runnable acceptance
The cluster is reachable from this environment: `VAULT_ADDR`, `VAULT_TOKEN`,
`NOMAD_ADDR`, `NOMAD_TOKEN`, and `CONSUL_HTTP_ADDR` are set, so the acceptance
checks below are runnable, not just documentation.

**Hard dependencies: both satisfied.** F2 (the OIDC issuer) and T3 (the TLS
edge and the `lab.orangecluster.nl` names) are `done` and applied. F3, which
earlier drafts named here as an unmet blocker, is also `done` and was
superseded by T3. Nothing in this section blocks on an unrun ticket any more.
What L1 still adds itself is its own OIDC client (requirement 7a) — F2
shipped the provider, not a client for every consumer.

**Pre-apply (runs in the loop, no cluster mutation):**
1. `just pre_commit` — green (includes `terraform fmt -check` and
   `terraform validate` on the new resources, per the gate above).

**Close-out (operator/live, after F2 + F3 are applied). Each check lists the
command and the expected result:**

1. **oauth2-proxy allocation is healthy.**
   - Command: `nomad job status oauth2-proxy`
   - Expect: `Status = running`, the latest deployment `Successful`, and a
     `running`/`healthy` allocation (0 failed).

2. **An unauthenticated request to `/` is refused, and the refusal is
   oauth2-proxy's own.**
   - Command: `curl -sI https://dash.lab.orangecluster.nl/`
   - Expect, with `--skip-provider-button=false` pinned per requirement 12: a
     **40x** carrying oauth2-proxy's sign-in page. Never a `200` from the
     upstream.
   - The row is written to accept **either** a 40x **or** a 302 whose
     `Location` is Vault's authorize endpoint, because the two are the same
     correct behavior under different flag settings, and a row that admits
     only one of them fails working code. With the button skipped,
     oauth2-proxy calls `doOAuthStart` from the `/` handler
     (`OAuthProxy.Proxy` dispatching into `OAuthProxy.doOAuthStart`) and 302s
  **straight to Vault** —
     not, as an earlier draft of this plan claimed, to a same-host
     `/oauth2/start?rd=…`.
   - What the row rules out is the original defect: a `200` served from the
     upstream, meaning no gate.

3. **The OAuth cycle actually starts at Vault, and at the right provider.**
   - Command: `curl -sI 'https://dash.lab.orangecluster.nl/oauth2/start'` and
     read the `Location` header.
   - Expect: a 302 whose `Location` is on
     `vault.lab.orangecluster.nl` and carries L1's `client_id`. Note the path
     Vault advertises is the **UI** one,
     `/ui/vault/identity/oidc/provider/lab/authorize`, not `/v1/…`
     (`docs/vault-human-auth.md:324-326`). Assert the provider name `lab`
     explicitly: live Vault also carries a built-in `default` provider that
     would accept the probe and prove nothing.

4. **The `/oauth2/callback` route exists (is served by oauth2-proxy).**
   - Command: `curl -sI https://dash.lab.orangecluster.nl/oauth2/callback`
   - Expect: **not** `404`. Any response oauth2-proxy generates itself
     counts. A bare probe with no state carries no CSRF cookie and no code,
     so the realistic answer is a **500** (`OAuthProxy.OAuthCallback`); `302`
     and `400` are also fine. Only `404` fails, meaning the callback path was
     never wired. Do not read the 500 as a defect — it is the correct
     response to a request that is missing everything the callback needs.

5. **Cookies carry `Secure` and `HttpOnly`.**
   - Command: `curl -sI 'https://dash.lab.orangecluster.nl/oauth2/start' | grep -i set-cookie`
   - Expect: whatever cookie is emitted carries both flags. **Probe
     `/oauth2/start`, and do not expect `_oauth2_proxy` here.** That is the
     *session* cookie, created at `/oauth2/callback` after a completed
     exchange; a pre-authentication request emits the CSRF cookie
     (`--cookie-csrf-*`) or none at all. The previous version grepped `/` for
     `_oauth2_proxy`, which returns empty against a correct implementation
     and reads as a failure.

6. **A completed auth-code flow yields an allowed request.**
   - Command: complete the Vault login for `https://dash.lab.orangecluster.nl/`
     in a browser, then re-request with the session cookie.
   - Expect: `HTTP/2 200` **from L1's own upstream**, confirming the flat
     policy lets the session through. See the note below on why this is not a
     check against L2's Homepage.
   - Expect one first-attempt failure mode that is not L1's bug: the Vault
     redirect lands on a **UI** path, so the browser must already hold a
     Vault UI session. Without one the first attempt can fail with a generic
     "Failed to sign in with SSO"; retrying after logging into the Vault UI
     succeeds (`docs/vault-human-auth.md:324-330`). A genuine authorization
     refusal looks different and says
     `identity entity not authorized by client assignment` — if you see
     that, requirement 5's `allow_all` assignment is not in place.

### The L1/L2 upstream, and the cycle it used to create

L1's Definition of Done previously required a `200` "reaching the landing-page
upstream" — which L2 owns, while `.loop/plans/L2-landing-homepage.md:3`
declares `depends_on = ["L1-landing-oauth2-proxy", …]`. L1's acceptance
depended on a ticket that depends on L1, so neither could go first.

**Resolution: L1 ships with a self-contained upstream and asserts only its own
behavior.** `--upstream=static://200` — env
`OAUTH2_PROXY_UPSTREAMS`, **plural**, see requirements 17 and 18 — makes
oauth2-proxy answer an
authenticated request itself, with no backend, which is exactly what L1's
"the gate lets an authenticated session through" row needs to prove. L2 then
changes one flag to point at Homepage and owns the "Homepage renders" check.

This keeps both of the operator's 2026-07-23 resolutions intact — L1 is the
gate only, and it runs in reverse-proxy mode — and reverses only the part that
was unrunnable. It is the same placeholder the plan's own Q1 recommended
before the resolution overrode it. **Operator: confirm.** Nothing else in the
ticket depends on the answer, so this is a check-in, not a blocker.

Also unreconciled and not L1's to fix: L2's ticket text still says
"forward-auth" in its summary and body, describing a mechanism this design
rejected. L1 flagged that on 2026-07-23 and nobody changed it. It belongs on
L2.

The loop's definition of done is: `just pre_commit` green (which now includes
`terraform validate`), and the live evals above recorded in the ticket/PR
description — the pre-apply eval run in the loop, the close-out evals run by
the operator.

Eval marker (five-column acceptance table, `loopctl eval`-validated): see
`.loop/evals/L1-landing-oauth2-proxy.md`.

## 9. Risk assessment
- **Blast radius:** additive. New job, new secret, new HAProxy ACL/backend,
  new OIDC client. The existing ACLs (`haproxy.hcl:98-118`) and backends
  (`:127-157`) are untouched, so current services keep working. The one
  shared-blast surface is `haproxy.hcl` itself: a malformed edit to the
  `https_in` frontend breaks *all* routing, since every routed host shares
  it. Keep the edit purely additive and `nomad fmt`-clean.
- **Reversibility:** high. Removing the `nomad_job`, the ACL/backend lines,
  and the secret reverts cleanly; no state migration, no data.
- **Likeliest failure modes:**
  1. **ACL on the wrong frontend.** An `acl`/`use_backend` added to `http_in`
     (`haproxy.hcl:91-93`) sits on the redirect-only frontend and can never
     route. `dash` would keep returning 503 with a config that looks correct.
     Everything routing goes on `https_in` (`:98-118`).
  2. **The client id is never added to `local.oidc_provider_client_ids`.**
     Vault gates the provider on that list and there is no standalone
     resource for it, so the omission is easy and the symptom is a refused
     authorization request rather than a Terraform error.
  3. **Bound to a tier group instead of `allow_all`.** The gate then refuses
     everyone outside that group, at Vault, while the jobspec says flat
     access. The error names it: `identity entity not authorized by client
     assignment`.
  4. **Issuer/discovery URL mismatch:** oauth2-proxy validates the OIDC
     discovery document. It must be the `lab` provider on
     `vault.lab.orangecluster.nl`, not the built-in `default` provider and
     not a raw-IP address.
  5. **Image architecture that does not match the chosen host.** firebat is
     amd64 and the other four nodes are arm64; pick both together
     (requirement 1).
  6. **Placement failure on a full node.** firebat has 100 MHz of CPU left
     and orangepi4a has ~0.1 GiB of memory left, so a `resources` block that
     looks modest can still fail to place. See §4's table.

## 10. Subtickets (ordered, dependency-aware)
1. **Pick the host and the image architecture together**, from §4's live
   capacity table. `radxa-dragon-q6a` (arm64, 192.168.2.50) is the
   recommendation: firebat has 100 MHz of CPU left, and it is the only amd64
   node. Re-measure before committing — the table is a snapshot, not a
   guarantee. Verify: `nomad node status <chosen>`.
2. **Register the OIDC client** in `oidc.tf`, per requirement 7a: client with
   `redirect_uris`, `assignments = ["allow_all"]`, the
   `vault_identity_oidc_key_allowed_client_id`, and the entry in
   `local.oidc_provider_client_ids`. Verify: `terraform validate`, then read
   the provider back and confirm the client id is in `allowed_client_ids`.
3. **Provision the cookie secret in Terraform.** `random_password` +
   `vault_kv_secret_v2` under oauth2-proxy's own prefix (mirror
   `secrets.tf:47-66`). Verify: `terraform validate`.
4. **Write `oauth2-proxy.hcl`.** Nomad job: image matching the step-1 host,
   `vault {}`, `template { env = true }` for the `OAUTH2_PROXY_*` env,
   `--upstream=static://200` (env `OAUTH2_PROXY_UPSTREAMS`, plural), service
   and a health `check` **against `/ping`**,
   network port, resources sized to fit the chosen node. Flat-access comment
   and the R1 reuse header.
   **Seven settings decide whether this job works at all**, and every one of
   them passes `nomad fmt` and `terraform validate` while being wrong:
   `--email-domain=*` — env `OAUTH2_PROXY_EMAIL_DOMAINS`, **plural**, and the
   singular spelling fails identically to omitting it;
   `--upstream=static://200` — env `OAUTH2_PROXY_UPSTREAMS`, **also plural**;
   `--oidc-email-claim=sub` (omit it and the callback 500s);
   `--provider=oidc` (default `google`);
   `--http-address=0.0.0.0:<static-port>` (default binds loopback only);
   `--skip-provider-button=false`; and the `/ping` check path (point it at `/`
   and the allocation never turns healthy).
   See requirements 5, 7b, 12, 13, 14, 15, 17, 18.
   Verify: `just format`, then `just pre_commit` green, then
   `nomad job status oauth2-proxy` shows a healthy allocation.
   **A healthy allocation is not the backstop it looks like.** It catches
   three of the seven — `--email-domain`, `--http-address`, and the `/ping`
   check path — because those stop the process starting or stop it answering.
   Proved by running three broken variants: the singular `EMAIL_DOMAIN` exits
   1, a missing `PROVIDER` starts as **Google**, a missing `OIDC_EMAIL_CLAIM`
   starts fine.
   Three others — `--provider`, `--oidc-email-claim` and `--upstream` — pass a
   healthy allocation while broken, and only the browser flow in §8 finds
   them. The seventh, `--skip-provider-button`, changes only which correct
   refusal `/` gives, so §8 row 2 accepts either and nothing fails if it
   drifts. Run the browser row before calling this step done.
5. **Wire the `nomad_job` in `services.tf`.** `templatefile` block passing the
   Vault path var(s), following `services.tf:346-368`. Verify:
   `terraform validate`.
6. **Add the HAProxy `dash` route.** ACL and `use_backend` in the `https_in`
   frontend (`haproxy.hcl:98-118`), and `backend dash` beside the others
   (`:127-157`) pointing at the chosen host:port. Settle the
   `X-Forwarded-Proto` question here (§7). Verify: `just pre_commit` green.
7. **Record acceptance checks** in the PR/ticket description for the operator
   to run. No code change.

## 11. Open questions
- **Q1 — Does L1 include the landing-page service itself, or only the auth
  gate?** No `dash.lab.orangecluster.nl` backend or landing app exists today. The
  ticket as scoped wires oauth2-proxy as the `dash` backend and treats the
  landing page content as either (a) served by oauth2-proxy's upstream, or
  (b) a separate ticket. *Recommendation:* keep L1 to the auth gate plus the
  HAProxy route, and point the oauth2-proxy upstream at a minimal
  placeholder (or the existing HAProxy stats/a static page) until a
  dedicated landing-page ticket lands. Confirm which.
- **Q2 — Forward-auth vs reverse-proxy mode.** HAProxy has no native
  nginx-style `auth_request`; enforcing forward-auth needs SPOE/Lua, which is
  heavier than anything in the current config. The lighter path is running
  oauth2-proxy in reverse-proxy mode (`--upstream=<landing>`, env
  `OAUTH2_PROXY_UPSTREAMS`) and making it
  the `dash` backend so HAProxy just routes to it. *Recommendation:*
  reverse-proxy mode. Confirm before implementing, because it decides the
  jobspec's `--upstream`/`--http-address` flags and whether the landing
  backend is referenced by HAProxy or by oauth2-proxy.
- **Q3 — Cookie secret length/encoding. SETTLED, with the reasoning
  corrected 2026-08-04.** oauth2-proxy requires a secret that resolves to 16,
  24 or 32 bytes. The recommendation stands — `random_password { length = 32,
  special = false }` passed raw to `OAUTH2_PROXY_COOKIE_SECRET` — but not for
  the reason first given. oauth2-proxy base64url-**decodes** the value before
  measuring it (`SecretBytes`), so 32 alphanumerics arrive
  as **24** bytes, not 32. 24 is one of the three legal sizes, so the
  configuration is valid; the earlier "32 ASCII chars = 32 bytes" arithmetic
  was wrong and would have misled anyone changing the length.
- **Q4 — SUPERSEDED. See the Resolved forks block.** The question assumed F2
  was unmerged and would write oauth2-proxy's credentials somewhere. F2 is
  `done` and did not; L1 creates its own client. The original text is dropped
  rather than kept, because its premise is gone.
- **Q5 — SUPERSEDED. See the Resolved forks block.** The provider is named
  `lab` and the issuer is known and live; there is nothing left to defer.
- **Q6 — Which host and static port for oauth2-proxy? RE-ANSWERED. Do NOT
  read the old recommendation.** It said "colocate on `firebat`", which the
  live capacity check in §4 has since ruled out: firebat has 100 MHz of
  reservable CPU and is the cluster's only amd64 node. The current answer is
  in the Resolved forks block — `radxa-dragon-q6a`, arm64, 192.168.2.50 —
  and the operator still picks the free static port.
- **Q7 — SUPERSEDED. See the Resolved forks block.** `--cookie-secure=true`
  stands, and the F3 ordering it worried about is moot: F3 and T3 are both
  `done` and the edge serves TLS today. No interim, nothing to block on.

## Resolved forks (operator, 2026-07-23)

- **Q1 → Auth gate only. AMENDED 2026-08-04 to break a dependency cycle.**
  L1 is the oauth2-proxy gate; it does NOT build the landing app. L2
  (Homepage/gethomepage) owns the landing app at
  `dash.lab.orangecluster.nl`. That part stands.
  What changes: L1 **ships** with `--upstream=static://200` (env
  `OAUTH2_PROXY_UPSTREAMS`, plural) and asserts only its own gate, rather than
  pointing it at L2's Homepage. The
  original wording made L1's acceptance depend on L2, while L2 declares
  `depends_on = ["L1-landing-oauth2-proxy"]` — a cycle in which neither
  ticket could go first. L2 changes the one flag when it lands and owns the
  "Homepage renders" check. See §8. Operator to confirm; nothing else depends
  on the answer.
- **Q2 → Reverse-proxy mode.** oauth2-proxy runs as the `dash` backend
  with `--upstream=<L2 Homepage>` (env `OAUTH2_PROXY_UPSTREAMS`, plural);
  HAProxy just routes `dash.lab.orangecluster.nl`
  to it. No SPOE/Lua forward-auth. NOTE: L2's ticket text says
  "forward-auth" and must be reconciled to this reverse-proxy wiring.
- **Q3 → `random_password { length = 32, special = false }`, raw.** Pass
  the 32 ASCII chars directly to `OAUTH2_PROXY_COOKIE_SECRET` (no base64).
- **Q4 → SUPERSEDED 2026-08-04. L1 creates its own client.** The old
  resolution asserted that F2 writes `client_id`/`client_secret` to
  `secret/data/default/oauth2-proxy/oidc`. F2's plan never promised that, and
  F2 has now shipped without it: `local.oidc_provider_client_ids`
  (`oidc.tf:80-84`) names smoke, nomad and memex only. The architecture is
  one client per consuming service, created by that service's own ticket.
  L1 therefore creates its client (requirement 7a) and writes its own secret
  under its own KV2 prefix. There is no F2 seam left to block on.
- **Q5 → SETTLED, no variable needed for the provider name.** The issuer is
  `https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab`
  (`oidc.tf:95-101`). The provider is named `lab`. Keep the host as a
  variable if the operator wants it configurable, but the value is known.
- **Q6 → RE-RESOLVED 2026-08-04 with the live numbers: not firebat.** The
  earlier resolution preferred colocating on firebat and deferred to a
  capacity check. That check has now been run (§4). firebat has 100 MHz of
  reservable CPU and is the cluster's only amd64 node, so it fails on both
  the capacity and the architecture the old requirement 1 assumed.
  **Recommendation: `radxa-dragon-q6a`** (arm64, 192.168.2.50, ~13 GHz CPU
  and ~3 GiB memory free), which already hosts mlflow and bifrost at the
  address HAProxy uses for them. The cost is one cross-node hop from the edge
  to the gate. Operator to confirm the host and pick a free static port.
- **Q7 → cookie-secure=true. Its dependency is discharged.** F3 and T3 are
  both `done` and the edge serves TLS, so there is nothing left to block on
  and no cleartext-cookie interim to consider.

**Dependencies:** F2, T3 and A1 are all `done` and satisfied. **L2 depends on
L1**, and L1 no longer depends on L2 — see the amended Q1.
## Premises / assumptions

- **P1.** The edge terminates TLS on `*:443` and `*:80` only redirects.
  `Evidence:` `deployments/infrastructure/services/haproxy.hcl:95-96` is
  `frontend https_in` / `bind *:443 ssl crt /secrets/haproxy.pem`; `:91-93`
  is `http_in` with the 301; `:62-72` renders the certificate from Vault KV2.
  `probe:` `curl -sI https://grafana.lab.orangecluster.nl/` returns a 302 over
  HTTP/2.

- **P2.** All routing lives on `https_in`, so an ACL on `http_in` can never
  route. `Evidence:` every `acl` and `use_backend` is at `haproxy.hcl:98-118`;
  `http_in` (`:91-93`) has no ACL; backends are `:127-157`.

- **P3.** `dash.lab.orangecluster.nl` resolves and the wildcard certificate
  already covers it, so no DNS or SAN work is needed.
  `probe:` `curl -sI https://dash.lab.orangecluster.nl/` returns 503 — the TLS
  handshake succeeds and HAProxy has no matching backend. Probed 2026-08-04.

- **P4.** Shared basic auth survives on two backends, not three.
  `Evidence:` `haproxy.hcl:143` (phoenix) and `:153` (mlflow) are the only
  `http-request auth` lines; the userlist is `:88-89`; `backend bifrost`
  (`:156-157`) lost its line to B1 in commit `ac3267b`.

- **P5.** Vault's `lab` OIDC provider exists, is HTTPS, and F2 is `done`.
  `Evidence:` `deployments/infrastructure/oidc.tf:95-101` sets
  `https_enabled = true` and `issuer_host = var.vault_issuer_host`.
  `docs/vault-human-auth.md:441` gives the issuer URL in full.

- **P6.** F2 shipped no oauth2-proxy client, so L1 creates its own.
  `Evidence:` `oidc.tf:80-84` lists three client ids — smoke, nomad, memex.
  The procedure L1 follows is written down at
  `docs/vault-human-auth.md:264-300`.

- **P7.** Flat access requires `assignments = ["allow_all"]` on the client,
  not merely the absence of an oauth2-proxy allowlist.
  `Evidence:` `docs/vault-human-auth.md:282-290` describes the built-in
  assignment as the answer when "who is allowed in" is "anyone who can log
  in"; `:331-333` gives the refusal text seen when it is not used.

- **P8.** An unauthenticated `/` on oauth2-proxy is refused rather than passed
  through, and what the refusal looks like depends on
  `--skip-provider-button`. With it `false` (the default, and pinned by
  requirement 12) `/` renders the sign-in page as a 40x. With it `true`, the
  `/` handler calls `doOAuthStart` and 302s **straight to Vault's authorize
  URL** — not to a same-host `/oauth2/start?rd=…`, which an earlier draft of
  this plan asserted and which is false. §8 row 2 accepts either shape for
  that reason. What never happens on a correctly gated deployment is a `200`
  from the upstream.
  `source:` upstream oauth2-proxy, `OAuthProxy.Proxy` dispatching into
  `OAuthProxy.doOAuthStart`. Symbols, not line numbers — see requirement 16.

- **P9.** `_oauth2_proxy` is the post-callback session cookie, so a pre-auth
  request does not emit it. `Evidence:` oauth2-proxy sets the
  `--cookie-csrf-*` family on the way into the flow. `probe:` running the
  pinned container against the live issuer, `/oauth2/start` emits
  `_oauth2_proxy_csrf=…; HttpOnly; Secure`. Probed 2026-08-04. §8 row 5 still
  asserts the flags rather than the name, so it survives a rename.

- **P10.** Vault's authorize endpoint is a **UI** path, which shapes the login
  experience and the eval. `Evidence:`
  `docs/vault-human-auth.md:324-330` records the redirect to
  `/ui/vault/identity/oidc/provider/lab/authorize` and the first-attempt
  failure when the browser holds no Vault UI session.

- **P11.** firebat cannot host this job. `probe:` `nomad node status`
  2026-08-04 reports firebat at `3100/3200 MHz` CPU with 4 allocations, and
  `nomad node status -verbose` reports `cpu.arch = amd64`; the other four
  nodes are arm64. Full table in §4.

- **P12.** The edge forwards no proto header, so oauth2-proxy's redirect
  scheme cannot be inferred. `Evidence:` a grep for
  `forwardfor|X-Forwarded|set-header` over
  `deployments/infrastructure/services/haproxy.hcl` returns nothing, and the
  `defaults` block is `:76-86`.

- **P13.** The repo gate is `just pre_commit` and it is Terraform-aware.
  `Evidence:` `justfile:18-19`; `.pre-commit-config.yaml` declares
  `nomad-fmt`, `terraform-fmt` and `terraform-validate`
  (`scripts/tf_validate.sh`); `.pre-commit-config.yaml:1` excludes
  `^\.(claude|loop)/`.

- **P14.** The jobspec and `.tf` patterns L1 copies all resolve.
  `Evidence:` `vault {}` at
  `grafana.hcl:29`, the env template at `grafana.hcl:77-84`, the pinned tag at
  `grafana.hcl:48`, the service and check at `nats.hcl:50-66`; the
  `random_password` + `vault_kv_secret_v2` pair at `secrets.tf:47-66`; the
  `nomad_job` blocks at `services.tf:318-326` (HAProxy) and `:346-368`
  (Grafana).

## Plan review history

### 2026-07-30 (A1 premise sweep) — PARTIALLY SOUND, `fail`

Reviewed by `loop-plan-reviewer` against the repo and the live cluster as part
of `A1-audit-plan-premise-sweep`. The verdict is
`.loop/verdicts/L1-landing-oauth2-proxy.plan-validator.md`.

The plan had been repaired in place on 2026-07-25/26, but only in some
sections: requirement 11 stated the post-F3 edge correctly while Context, Risk
and Subtickets still described a cleartext `*:80`-only HAProxy and pointed the
ACL work at the redirect-only frontend. An implementer following the subtickets
in order would have read the wrong instruction. Two deeper defects: the eval's
redirect and cookie expectations were wrong for oauth2-proxy's documented flow,
so a correct implementation failed 100%-threshold rows; and L1's Definition of
Done required a 200 from an upstream that L2 owns, while L2 declares a
dependency on L1.

### 2026-08-04 — required fixes applied

All nine required fixes are in, checked against the repo and the live cluster
as they stand now. F2 has landed since the verdict was written, which settles
three of the open seams outright.

1. **§4 rewritten whole** to the post-T3 edge, with the two frontends, the
   certificate template and the current line ranges. The
   "cleartext `*:80` only" sentence and its anchors are gone.
2. **§9 and §10 now say `https_in`** and carry current ranges, so the plan
   no longer instructs the implementer twice, contradictorily.
3. **The basic-auth claim is corrected** in §3 and §5: userlist at
   `haproxy.hcl:88-89`, auth on phoenix `:143` and mlflow `:153` only, bifrost
   dropped from both the claim and the non-goal.
4. **The F2 secret path is de-inlined.** It was never F2's to promise. Q4 is
   superseded: L1 creates its own client and writes its own secret, following
   the procedure at `docs/vault-human-auth.md:264-300`.
5. **The flat-access contract is settled at the Vault end** — requirement 5
   now names `assignments = ["allow_all"]` and says why the oauth2-proxy half
   alone is not enough.
6. **§8 rows 2 to 5 rewritten** against oauth2-proxy's actual flow: a 40x at
   `/`, the Vault redirect probed at `/oauth2/start`, the `lab` provider named
   explicitly so the built-in `default` cannot pass by accident, the `/ui/`
   authorize path, and cookie flags asserted without naming `_oauth2_proxy`.
7. **The L1/L2 cycle is broken** by `--upstream=static://200`, keeping both
   operator resolutions intact and moving the "Homepage renders" row to L2.
8. **Q6 re-resolved with live numbers.** firebat has 100 MHz free and is the
   only amd64 node; `radxa-dragon-q6a` is the recommendation. Requirement 1
   and the risk section now tie image architecture to the chosen host rather
   than to "Orange Pi boards".
9. **Anchors fixed:** HAProxy `nomad_job` at `services.tf:318-326`, Grafana at
   `:346-368`, and the provider list corrected — `providers.tf` declares
   `null` and `google` too.

Structural: the plan now carries the `# Ticket:` header, numbered contract
sections, and a `Premises / assumptions` section.

### 2026-08-04, second pass — BROKEN, `fail`

The revision above fixed what the first verdict named, then introduced three
new factual errors about oauth2-proxy itself, two of them fatal. All nine
required fixes are now applied.

1. **Requirement 5 was inverted, and it was the killer.** It said flat access
   means setting no `--allowed-*` restriction. oauth2-proxy **refuses to
   start** without an email allowlist, aborting with "missing setting for
   email validation" and naming `email-domain=*` as the fix
   (`validation.Validate`). Flat access is an
   explicit `--email-domain=*`. As written the job crash-looped and eval row 1
   failed at 100%.
2. **Requirement 7b was half right and wholly wrong.** "L1 is flat and reads
   no claim, so it needs only `openid`" is true of the *scope* and false of
   the *flow*: oauth2-proxy requires an email to build a session and errors
   when it is empty (`OIDCProvider.EnrichSession`), surfacing as a 500 at
   `/oauth2/callback` (`OAuthProxy.OAuthCallback`). Vault's `lab` provider emits
   no `email`. `--oidc-email-claim=sub` is now mandatory, and it only works
   paired with `--email-domain=*`.
3. **The eval rewrite carried its own version of the original defect.** The
   claim that `--skip-provider-button=true` redirects to a same-host
   `/oauth2/start?rd=…` is false — the `/` handler calls `doOAuthStart` and
   goes straight to Vault (`OAuthProxy.Proxy` into `OAuthProxy.doOAuthStart`). Row 2 now
   accepts a 40x **or** a 302 to Vault, and requirement 12 pins the flag.
4. **The health check needed a path.** `/ping`, not `/` — checking `/` on a
   gate that refuses callers leaves the allocation permanently unhealthy. Now
   requirement 13.
5. **Stale §11 recommendations marked superseded inline.** Q4, Q5, Q6 and Q7
   still carried their pre-F2 answers while the Resolved-forks block reversed
   them, the same read-the-wrong-instruction defect the first verdict flagged
   in §9 and §10. Q6's "colocate on firebat" was the dangerous one.
6. **Eval row 4's expectation corrected.** A bare callback probe realistically
   returns 500 (`OAuthProxy.OAuthCallback`), not 302 or 400, so an operator would
   have read a correct response as a failure.
7. **Anchor drift:** `haproxy.hcl:99-118` to `:98-118` in five places
   (`acl is_minio` sits at `:98`); the `allow_all` citation widened to
   `docs/vault-human-auth.md:282-290`.
8. **§8's "no pytest, no CI workflow" was false.** Pytest runs for `cli/` at
   `.pre-commit-config.yaml:66-73` and `.github/workflows/` exists. The
   sentence is narrowed to the true claim: no harness covers HCL.
9. **Q3's arithmetic corrected.** oauth2-proxy base64url-decodes the cookie
   secret before measuring it (`SecretBytes`), so 32
   alphanumerics are 24 bytes, not 32. Still legal, so the recommendation
   stands and only the reason changed.

What the second verdict explicitly did not dispute: the §4 rewrite, the
capacity measurements, the Vault-side flat-access contract, the
`lab`-vs-`default` hazard, the UI authorize path, the `X-Forwarded-Proto` gap,
and the `static://200` cycle break.

### 2026-08-04, third pass — PARTIALLY SOUND, `fail`

This pass ran the actual oauth2-proxy container against the live `lab` issuer
rather than reading source, which settled most of the plan and found one
defect that reading could not.

**The killer: `OAUTH2_PROXY_EMAIL_DOMAIN` is not the env var.** It is
`OAUTH2_PROXY_EMAIL_DOMAINS`, plural. oauth2-proxy derives env names from each
field's `cfg` struct tag rather than its flag name, and `EmailDomains` carries
`flag:"email-domain"` with `cfg:"email_domains"`. Proven by running the
container both ways: the singular spelling exits with "invalid configuration:
missing setting for email validation", the plural one starts and serves. This
was the crash-loop requirement 5 exists to prevent, arriving for a **third**
time — first by omitting the setting, then by naming it in the singular. The
new eval guardrail row scored the wrong name too, so it would have failed a
correct implementation. Both are fixed, and the requirement now states the
flag and the env var separately because they genuinely differ.

Four smaller fixes, all applied:

1. **`--provider=oidc` was never stated** and the default is `google`, so the
   whole flow would have pointed at the wrong IdP however correct the issuer
   settings were. Now requirement 14.
2. **`--http-address=0.0.0.0:<port>` was never stated** and the default
   `127.0.0.1:4180` is reachable from neither HAProxy nor the `/ping` check.
   Now requirement 15.
3. **Requirement 13's anchor was wrong**: it pointed at `SignInPage` rather
   than the ping registration. Citations are now by symbol name (requirement
   16), so this class of miss cannot recur.
4. **The upstream citations drift.** They were read against the project's main
   branch rather than the pinned `v7.13.0`. Requirement 16 now cites upstream
   code by **symbol name** instead of line number, and pins the version.

### 2026-08-04, fourth pass — PARTIALLY SOUND, `fail`

The pass pulled the `cfg` struct tags out of `/bin/oauth2-proxy` inside the
pinned `v7.13.0` image and checked all thirteen settings this plan names.

**A second flag-vs-`cfg` mismatch, and it is worse than the first.**
`--upstream` is `OAUTH2_PROXY_UPSTREAMS`, plural. The other eleven checked
settings match their flag names, so the rule is specifically that repeatable
settings pluralize. Proved by running the pinned container both ways against
the live issuer: with the plural name the log carries
`mapping path "/" => static response 200` and an authenticated request returns
`200`; with the singular name there is no mapping line and the same request
returns `404 page not found`. **The container reports `running` in both
cases**, `/ping` returns 200 in both, `/` returns 403 in both.

That is why this one matters more than the email-domain bug. The email bug
crash-loops and fails eval row 1 immediately. This one starts cleanly, passes
rows 1 through 5 and every guardrail, and fails only row 6 — the manual
browser flow, model-scored, run last and by hand. The operator completes a
full Vault login and lands on a 404 with nine-tenths of the suite green. The
plan walked an implementer straight into it: `grep -c OAUTH2_PROXY_UPSTREAM`
over the plan and eval returned **0** while requirement 2, §7, §10.4 and the
guardrail row all mandate env-based config.

Seven fixes, applied:

1. **`OAUTH2_PROXY_UPSTREAMS` named at every site** that mentions
   `--upstream`, with the same flag-and-env treatment requirement 5 gives
   `--email-domain`. New requirement 18 records the silent-failure shape.
2. **Requirement 5 generalized into requirement 17**, which states the rule
   (env names come from the `cfg` tag; repeatable settings pluralize) and
   carries the checked table for all fourteen settings, so R1 inherits the
   check rather than the two exceptions.
3. **The eval guardrail row now scores seven settings**, including the
   upstream, and is retitled off "the four settings".
4. **§10 subticket 4's closing claim corrected.** It said a healthy allocation
   is the backstop; it is not. It catches three of seven, and `--provider`,
   `--oidc-email-claim` and `--upstream` all pass it while broken.
5. **Requirement 16 made executable.** Its diagnosis was wrong — most
   citations landed within ~5 lines of `v7.13.0`, not ~200 — and two were
   genuinely misattributed: the `doOAuthStart` reference pointed at a
   `noCacheHeaders` map, and requirement 7b's empty-email 500 pointed at a
   different branch. "Find the symbol" was unexecutable because six of eight
   citations named no symbol. Upstream code is now cited by symbol name.
6. **New requirement 19 pins `OAUTH2_PROXY_SCOPE=openid`.** oauth2-proxy
   requests `openid email profile` by default while Vault advertises only
   `["groups","openid"]`. The plan depended on Vault ignoring the extras, a
   claim that lived only in this history and could not be reproduced. Asking
   for only what is advertised removes the dependency.
7. **Requirement 15 sharpened.** Under `network_mode = "host"` the Nomad `to`
   mapping is inert (`haproxy.hcl:11-15` declares `to = 8080` with
   `network_mode = "host"` at `:30` and still binds `*:80`), so the bind must
   use the `static` port.

What passes three and four both verified live and could not break, listed here
once: `/ping` returns 200
unauthenticated; `/` returns 403; `/oauth2/start` 302s to
`https://vault.lab.orangecluster.nl/ui/vault/identity/oidc/provider/lab/authorize`
carrying the `client_id`, with `Set-Cookie: _oauth2_proxy_csrf=…; HttpOnly;
Secure`; a bare `/oauth2/callback` returns 500. So §8 rows 2 to 5 and
requirements 12 and 13 are correct as written, and row 2 is consistent with
requirement 12. `--oidc-email-claim=sub` needs nothing alongside it: it feeds
the session email directly, and because the claim is not literally `email` it
also disables the `email_verified` check; `UserClaim` already defaults to
`sub`, so no `--user-id-claim`; a missing `groups` claim is not an error, so
no `--oidc-groups-claim`. `--email-domain=*` genuinely admits a UUID — the
validator rejects only the empty string and then `allowAll` passes anything
non-empty, and Vault always emits `sub`. The scope trap that bit G1 is not
present here: oauth2-proxy sends `openid email profile` by default and Vault
ignores the unsupported extras silently.

### 2026-08-04, fifth pass — PARTIALLY SOUND, `pass-with-required-fixes`

**No fourth crash-loop-class bug.** All four attack points came back clean.
Requirement 17's table was verified against the v7.13.0 tree: `email-domain`
and `upstream` are the only two of the fourteen that pluralize, and a sweep of
all 25 slice-typed options found no third exception among the settings this
plan touches. Requirement 19 is safe — the container was run with the plan's
full env against the live issuer and starts, maps the static upstream, answers
`/ping` 200 and `/` 403, and sends `scope=openid`; nothing needs `email` or
`profile` because `--oidc-email-claim=sub` skips the `email_verified` check and
`UserClaim` already defaults to `sub`. Requirement 19's own hedge is also
discharged: the live OpenBao 2.0.3 silently drops unsupported scopes at both
authorize and userinfo, so pinning the scope is belt-and-braces rather than
load-bearing. §10.4's "three of seven" split was proved by running three
broken variants.

Four fixes, applied:

1. **The previous round's citation fix was half-applied.** Four line-number
   citations survived, three of which miss in v7.13.0 — including §8 row 2
   still pointing at `prepareNoCache`/`noCacheHeaders` for `doOAuthStart`,
   verbatim the miscitation the fourth pass reported as fixed. Every upstream
   citation in the plan is now a symbol name, including the ones inside this
   history, so the wrong numbers are not preserved anywhere.
2. **Two `--upstream` sites in §11 Q2 and its resolved fork** still carried no
   `OAUTH2_PROXY_UPSTREAMS`, so "named at every site" was not true.
3. **P9's `UNCERTAIN` was stale.** The CSRF cookie was observed live:
   `_oauth2_proxy_csrf=…; HttpOnly; Secure`.
4. **§10.4 left `--skip-provider-button` out of both groups.** It belongs in
   neither: it changes only which correct refusal `/` gives, and §8 row 2
   accepts both.

**One observation promoted to a requirement.** Requirement 7a never named
`client_type`. The default and the cited templates are `confidential`, which is
right for oauth2-proxy, but `memex_oidc.tf:80` is `public` — and a public
client makes Vault reject the authorize with "PKCE is required for public
clients", a failure that clears rows 1 through 5 and dies only in the browser
row. That is the same silent-failure shape as the `--upstream` bug, so
requirement 7a now states it outright.

### 2026-08-04, sixth pass — PARTIALLY SOUND, `pass-with-required-fixes`

All four of the fifth pass's fixes verified correct: no line-number citations
remain, both `--upstream` sites name the plural env var, P9's probe matches the
container's own startup line, and §10.4's split is 3+3+1 and consistent with
§8 row 2. All six symbols in requirement 16 resolve in `v7.13.0` and support
the claims attached to them, and §8 row 2 is exactly right — `OAuthProxy.Proxy`
branches on `SkipProviderButton` into either `doOAuthStart` or a 403
`SignInPage`, which is both shapes the row accepts. Requirement 17's table was
re-confirmed against the `cfg` tags: still only two plurals.

Two fixes, applied:

1. **Requirement 7a mandated the right thing for the wrong reason, and the
   wrong reason was the failure shape.** `confidential` is correct — confirmed
   twice over — but the previous round claimed a public client fails silently
   in the browser row. It does not. **Vault issues no client secret at all to a
   public client**: generation is gated on the confidential type, and reading a
   public client back returns none. Live proof: `oidc-smoke` (confidential)
   returns a 75-character secret, `memex` (public) returns none. So the mistake
   leaves `OAUTH2_PROXY_CLIENT_SECRET` empty and the pinned container exits 1
   with `missing setting: client-secret or client-secret-file` — the loud
   `--email-domain` shape that fails §8 row 1, not the silent `--upstream`
   shape. The old wording would have led an operator staring at an unhealthy
   allocation to rule `client_type` out as the cause. The PKCE rejection is
   real but unreachable on this path, and is now recorded as the second,
   independent reason rather than the primary one.
2. **Requirement 13's `/ping` was attached to the wrong symbol.** It is served
   by `middleware.NewHealthCheck` inside `OAuthProxy.buildPreAuthChain`, ahead
   of the mux — which is *why* it answers unauthenticated. The conclusion was
   right and the location was not. Both symbols are added to requirement 16's
   list.
