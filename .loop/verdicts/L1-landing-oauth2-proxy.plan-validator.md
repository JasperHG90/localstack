---
verdict: pass
plan: 08c056a4968aa12f8324e99ed9092aeefffac45d0cf3ddb5d87a07e8e8cf17dc
---

# Plan review: L1-landing-oauth2-proxy (seventh pass, confirmation)

**Premise verdict: SOUND.**

Deterministic floor: `loopctl verify-plan L1-landing-oauth2-proxy` returns
`valid` (warnings only, all of the form "ambiguous file basename 'secrets.tf'
/ 'services.tf' / 'providers.tf'", which is the checker resolving a bare
basename against several Terraform roots, not a broken anchor).

Both sixth-pass fixes are applied and both are correct. I re-derived each one
from the live cluster and the pinned `v7.13.0` source rather than from the
plan's summary. No new contradiction was introduced.

## Per assumption

**P1. A `public` Vault client carries no client secret, so the mistake leaves
`OAUTH2_PROXY_CLIENT_SECRET` empty. HOLDS.**
Live read against `VAULT_ADDR=http://192.168.2.30:8200`:
`vault read identity/oidc/client/oidc-smoke` returns `client_type:
confidential` with a 75-character `client_secret`; `vault read
identity/oidc/client/memex` returns `client_type: public` and the response has
**no `client_secret` key at all** (keys returned: `access_token_ttl`,
`assignments`, `client_id`, `client_type`, `id_token_ttl`, `key`,
`redirect_uris`). Requirement 7a's numbers and its "returns nothing" wording
are exact (plan `.loop/plans/L1-landing-oauth2-proxy.md:192-196`).

**P2. The failure is loud: the pinned container exits 1 at startup with
`missing setting: client-secret or client-secret-file`, failing §8 row 1.
HOLDS.** This is the load-bearing half of fix 1 and I ran it. With the plan's
full env (`PROVIDER=oidc`, the live `lab` issuer, `EMAIL_DOMAINS=*`,
`OIDC_EMAIL_CLAIM=sub`, `UPSTREAMS=static://200`, `SCOPE=openid`,
`HTTP_ADDRESS=0.0.0.0:4180`) and `OAUTH2_PROXY_CLIENT_SECRET=""`,
`quay.io/oauth2-proxy/oauth2-proxy:v7.13.0` printed

    [main.go:53] invalid configuration:
      missing setting: client-secret or client-secret-file

and exited **1**. Control run: the identical env with any non-empty secret
starts, reaches the live issuer's discovery document, and serves (`/ping` 200,
`/` 403). So the empty secret alone is the discriminator, the message matches
the plan character for character, and the shape is the `--email-domain`
crash-loop shape, not the silent `--upstream` shape. Requirement 7a
(`:196-202`) is right.

**P3. `memex_oidc.tf:80` is `public` and the cited templates are
`confidential`. HOLDS.** `deployments/infrastructure/memex_oidc.tf:80` is
`client_type = "public"`; `nomad_oidc.tf:54` and `oidc.tf:139` are
`confidential`. The "an implementer copying that file gets the wrong type"
hazard is real.

**P4. The PKCE rejection is a real second reason nobody reaches on this path,
and the container warns at startup. HOLDS.** `providers/providers.go` logs
`Warning: Your provider supports PKCE methods %+q, but you have not enabled
one with --code-challenge-method` when the discovery document advertises
methods and `CodeChallengeMethod` is empty. I saw that warning in the control
run's log. Demoting it to the second, unreachable reason (`:203-206`) is the
correct ordering: with no secret the process never gets to an authorize
request.

**P5. §8 row 1 needs no edit to match requirement 7a. HOLDS.** The plan's §8
close-out row 1 (`:461-464`) states a positive expectation only (`Status =
running`, deployment `Successful`, a `running`/`healthy` allocation, 0 failed)
and enumerates no failure causes, so there is no stale describing sentence to
update. A container exiting 1 fails that expectation directly. No
stale-describing-sentence pattern in the plan.

**P6. `/ping` is served by `middleware.NewHealthCheck` inside
`buildPreAuthChain`, before the auth-gated handler, which is why it answers
200 unauthenticated. HOLDS.** In `v7.13.0` (fetched from the tagged tarball):
`buildPreAuthChain` at `oauthproxy.go:356` appends
`middleware.NewHealthCheck(healthCheckPaths, healthCheckUserAgents)` with
`healthCheckPaths := []string{opts.PingPath}` (`oauthproxy.go:367`, in both
the `SilencePing` and the default branch); `PingPath` defaults to `"/ping"`
(`pkg/apis/options/options.go:104`); `NewHealthCheck` is
`pkg/middleware/healthcheck.go:10`. The chain is installed router-wide at
`oauthproxy.go:317-318` under the comment "Everything served by the router
must go through the preAuthChain first", ahead of the catch-all
`r.PathPrefix("/").Handler(p.sessionChain.ThenFunc(p.Proxy))`
(`oauthproxy.go:333`), and `buildPreAuthChain`'s own doc comment says it
"should process every request before the OAuth2 Proxy authentication logic
kicks in. For example forcing HTTPS or health checks." `/ping` is registered
on no mux route. Live confirmation on the running container: `/ping` 200, `/`
403, and an arbitrary deep path 403, so the gate covers everything except the
health path. Requirement 13's conclusion, mechanism and measured 403 are all
correct.

**P7. No other section describes `/ping` as mux-registered. HOLDS.** Every
`/ping` mention in the plan (`:279-286`, `:292`, `:345`, `:364`, `:613`,
`:624`, `:630`, and the history entries at `:910`, `:960`, `:963`, `:982`,
`:1024`, `:1048`, `:1107-1109`) either names the path to probe or repeats the
corrected anchoring. The word "mux" appears once, in requirement 13.

**P8. Requirement 16's list is complete for the symbols the plan uses.
HOLDS.** All eight resolve in `v7.13.0`: `validation.Validate`
(`pkg/validation/options.go:22`), `OIDCProvider.EnrichSession`
(`providers/oidc.go:105`), `SecretBytes` (`pkg/encryption/utils.go:24`),
`OAuthProxy.OAuthCallback` (`oauthproxy.go:857`), `OAuthProxy.doOAuthStart`
(`oauthproxy.go:797`), `OAuthProxy.Proxy` (`oauthproxy.go:1011`),
`buildPreAuthChain` (`oauthproxy.go:356`), `middleware.NewHealthCheck`
(`pkg/middleware/healthcheck.go:10`). Sweeping the plan body (§1 to §11 plus
the Premises block) for upstream identifiers turns up exactly those eight and
no ninth. The extra symbols that appear only inside the review history also
resolve, so the plan carries no dangling upstream anchor anywhere:
`SignInPage` (`oauthproxy.go:634`), `SkipProviderButton` (`:98`),
`prepareNoCache`/`noCacheHeaders` (`:1059-1066`), `allowAll`
(`validator.go:80`), `UserClaim` defaulting to `sub`
(`providers/provider_data.go:206-207`, `oidcUserClaim = "sub"`).

**P9. The two fixes introduce no contradiction in §6, §8, §10 or the Premises
block. HOLDS.** §10 subticket 4's "seven settings" and its 3+3+1 split
(`:616-639`) are scoped to the jobspec env and check path written in that
step; `client_type` is registered in subticket 2 (`:602-606`), so the counts
do not collide. §8 rows 2 to 5 and P8/P9 concern `/`, `/oauth2/start`,
`/oauth2/callback` and cookies, none of which requirement 13's re-anchoring
touches. The Premises block states nothing about `client_type` or the ping
mechanism, so neither fix leaves a premise behind. Requirement 12's `/` shape
and §8 row 2 stay consistent (`OAuthProxy.Proxy` branching on
`SkipProviderButton` into `doOAuthStart` or a 403 `SignInPage`).

## Most dangerous assumption

**P2** — that a `public` client fails loudly at startup rather than silently in
the browser row. It is the whole point of fix 1: it tells an operator staring
at an unhealthy allocation to suspect `client_type`. I did not take it on
trust; I ran the pinned image with an empty secret and got exit 1 with the
exact message the plan quotes.

## Contract hygiene

Clean. Code surface anchors resolve; the tests-and-gates section matches the
repo's real blessed invocation (`just pre_commit`, Terraform-aware); non-goals
are explicit; the eval marker exists at
`.loop/evals/L1-landing-oauth2-proxy.md`; open questions carry
recommendations.

## Required fixes

None.

## Non-blocking observations (no action required for this gate)

1. **The eval's row 1 now under-counts by one.**
   `.loop/evals/L1-landing-oauth2-proxy.md:49` says "Three distinct ways to
   fail this row" and lists `--email-domain`, the `/ping` check path, and
   placement. After fix 1 there is a fourth: a `public` client leaves the
   secret empty and the container exits 1. The row's pass criterion (a healthy
   allocation) is unaffected, so it cannot fail a correct implementation or
   pass a broken one, and the eval is a separate artifact with its own gate.
   Worth folding in next time the eval is touched, since the omission is
   exactly the diagnostic blind spot fix 1 exists to close.
2. **`OAuthProxy.buildPreAuthChain` carries a receiver it does not have.** In
   `v7.13.0` `buildPreAuthChain` is a package-level function in `package
   main` (`oauthproxy.go:356`), called from `NewOAuthProxy` at
   `oauthproxy.go:203`, not a method on `OAuthProxy`. The symbol resolves on a
   bare name grep, which is all requirement 16 asks of a citation, and the
   claim attached to it is correct, so this is cosmetic. Likewise "ahead of
   the mux" is, strictly, "installed as router-wide middleware that runs
   before every route handler"; the behavior it explains is the same and I
   measured it.
3. **The fifth-pass history block (`:1072-1078`) still states the superseded
   silent-failure claim.** The sixth-pass block immediately below
   (`:1093-1106`) names and reverses it, which matches the plan's convention
   of keeping each pass's record intact rather than rewriting it (compare
   requirement 10, kept "as a record rather than deleted"). History is not
   instruction and the live requirement 7a is unambiguous, so nothing to fix.
