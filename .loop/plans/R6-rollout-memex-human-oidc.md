---
epic = "rollout"
depends_on = ["F2-foundation-vault-oidc-provider"]
priority = 5
summary = "Give humans SSO into memex instead of a shared static admin key. Split out of R5 after plan review proved the obvious route impossible: Vault's OIDC provider issues an opaque access token, and memex verifies the access token and rejects opaque ones."
stub = true
---

# Ticket: R6-rollout-memex-human-oidc

## Triggered by

Split out of `R5-rollout-memex-oidc-auth` on 2026-08-03. R5 originally
covered both memex OIDC paths. Its plan review
(`.loop/verdicts/R5-rollout-memex-oidc-auth.plan-validator.md`, verdict
`fail`) proved the human half impossible as designed. R5 kept the workload
half and this ticket carries the human half forward.

Humans share one static memex admin key today. That is the thing to fix.

## Vision & rough premises

Goal: a developer runs `memex auth login` and gets an identity, instead of
holding a shared admin key.

The blocking fact, VERIFIED during R5's review and not to be re-litigated:

- Vault's OIDC provider issues an **opaque batch token** as `access_token`
  and puts the signed JWT in `id_token`.
- memex verifies the **access** token and its docs reject both opaque
  tokens and id_tokens: "Only providers that issue signed JWT access
  tokens work here, because the server verifies tokens locally against the
  provider's JWKS. Providers with opaque access tokens (Google, GitHub)
  are not supported on this path."
  (<https://raw.githubusercontent.com/JasperHG90/memex/main/docs/how-to/configuring-server/oidc.md>)
- No overlap. Pointing memex at the Vault `lab` provider 403s every login.

So this ticket is a fork, not an implementation. Three routes, each
UNVERIFIED:

1. **Teach memex to verify Vault's `id_token`.** The operator owns memex,
   so this is available in a way it would not normally be. Largest scope
   (upstream feature plus a release), but the only route that reaches Vault
   SSO with no new component in the cluster. UNVERIFIED: whether accepting
   an id_token as a bearer credential is acceptable upstream, and what it
   costs.
2. **Front memex with something that issues signed JWT access tokens.**
   oauth2-proxy (`L1-landing-oauth2-proxy`, currently blocked) or Bifrost.
   UNVERIFIED: whether either issues a JWT access token memex would accept,
   and whether it can carry a `groups`-equivalent claim for the developer
   gate.
3. **Drop human OIDC.** Humans keep static API keys. Cheapest; leaves the
   shared-key problem standing.

Two findings from R5's review that survive and apply here, both VERIFIED,
so route 1 or 2 does not need to re-derive them:

- Vault matches loopback redirect URIs **port-agnostically** (it strips the
  port from both sides when the host is `localhost`, `127.0.0.1`, or
  `::1`), but the host literal and path must match exactly. memex binds an
  ephemeral port, so a naive registration would fail at authorize time.
- The `developer` group gate works upstream of the token: Vault refuses to
  issue a token at all to an entity outside the assignment, with
  `{"error":"access_denied","error_description":"identity entity must be
  associated with the request"}`.

## Non-goals

- The workload path. R5 owns hermes and Nomad Workload Identity.
- Removing static API keys. The memex browser extension uses them, and
  they are the fallback that makes R5's failure modes recoverable. A
  separate ticket retires them, once something has replaced them.
- Changing the Vault `lab` provider (F2) itself, or any other consumer of
  it. Grafana and the Nomad UI use the id_token and are unaffected.

## Open questions

- **Which route?** Operator decision, and the reason this is a stub. Flesh
  it out only once the route is picked, since the code surface, the gates,
  and the risk are entirely different per route.
- If route 1: does memex accept an id_token as a bearer credential, or does
  it need a distinct config field to say "this provider's credential is the
  id_token"? Does that weaken anything for providers that do issue JWT
  access tokens?
- If route 2: does the fronting proxy issue a JWT access token memex
  accepts, and can it carry the developer-group claim? Does it change how
  the memex CLI logs in, or only the browser path?
- What policy level do humans get (`reader` / `writer` / `admin`), and
  scoped to which vaults? R5 left this open; the operator holds the admin
  key today, so anything narrower is a capability cut that needs stating.
- Does the CLI need a headless login? Vault advertises no
  `device_authorization_endpoint`, so `memex auth login --device` cannot
  work against it. Only matters if a non-browser login is a real need.
