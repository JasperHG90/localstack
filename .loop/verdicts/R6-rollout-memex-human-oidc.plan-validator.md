---
verdict: pass-with-required-fixes
plan: ffa42dd9f88e50dcf5bc0090379dc1bc32cb9928f8e4facb538435b1f85a562e
---

# Plan review: R6-rollout-memex-human-oidc

## Premise verdict

**PARTIALLY SOUND.**

Every load-bearing premise the plan states about the mechanism holds, and
the four that decide whether the ticket is buildable at all (P1, P3, P4,
P8) are confirmed at upstream source and, where a probe was possible,
reproduced live from this checkout. The approach is right: a public PKCE
Vault client, an id_token bearer, and a second provider element whose
`audience` is the client id.

What breaks is evidence, not design: one stale `path:line`, one expected
log string that will not match a working system, and two gaps in §8's
coverage of the human path. All four are cheap to fix and none changes the
plan's shape.

Deterministic floor: `loopctl verify-plan R6-rollout-memex-human-oidc`
returns `valid`. `apm_modules/` does not exist and the plan cites it only
to forbid citing it (plan `:663`).

## Per-assumption findings

Premises P1..P16 are the plan's own. P17..P20 are load-bearing assumptions
it left implicit.

### P1 — memex v1.2.0 adds `credential`, names Vault, needs audience = client_id. HOLDS

`OidcClientConfig.credential` is
`Literal['access_token','id_token'] = Field(default='access_token', ...)`
at `config.py:1657-1667` (v1.2.0), and its validator raises unless
`grant == 'interactive'` and `'openid' in self.scopes`
(`config.py:1715-1732`), with the plan's quoted wording verbatim. The
docstring names HashiCorp Vault at `config.py:1621-1622`. Default scopes
are `['openid','profile','email','offline_access']` (`config.py:1636-1639`),
so the "no groups by default" starting point is real. The how-to lines the
plan cites all resolve and say what it claims: line 40 (selection by `iss`,
then signature, `aud`, `iss`, `exp`), 44 (`_rule_matches` does membership on
a list), 113 (`scopes` replaces the default list), 115 (an id_token's `aud`
is the client id), 140-144 (no `azp` check, do not share the client id).
Server side, `audience: list[str]` carries `min_length=1` and is mandatory
(`config.py:1487-1490`), and a provider needs at least one `grant_rule` or a
`default_policy` (`config.py:1542-1550`), which the plan's element has.

### P2 — authorization_code only, no device endpoint, no refresh token. HOLDS

Live discovery reproduced verbatim from this checkout:
`grant_types_supported: ["authorization_code"]`,
`scopes_supported: ["groups","openid"]`, no `device_authorization_endpoint`,
`issuer` exactly
`https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab`, which is
the string §7 puts in `local.vault_oidc_issuer`. Vault's token response is
built as `{token_type, access_token, id_token, expires_in}` with no
`refresh_token` key (`vault/identity_store_oidc_provider.go:2166-2171` at
v2.0.3). The CLI's device guard string is exact:
`LoginError('provider does not advertise a device_authorization_endpoint.')`
(`memex_cli/auth.py:255-256`). Q6 is correctly SETTLED.

### P3 — a public PKCE client works against this provider. HOLDS

Live: `token_endpoint_auth_methods_supported` contains `none` and
`code_challenge_methods_supported` contains `S256`. Vault requires PKCE for
a public client at both ends, not just accepts it: authorize refuses without
a challenge (`identity_store_oidc_provider.go:1806-1809`) and the token
exchange refuses without a verifier (`:2060-2061`). The CLI always sends
`code_challenge_method: 'S256'` with a fresh verifier
(`memex_cli/auth.py:187-188`, `:204`). The Terraform provider exposes
`client_type` as a first-class optional field
(`resource_identity_oidc_client.go:79-85` at v5.3.0), so `public` is
expressible.

### P4 — a Vault id_token's `aud` IS the client id. HOLDS, and it generalizes

This is unconditional in Vault, not a property of the Nomad client:
`idToken{ Issuer: provider.effectiveIssuer, Subject: authCodeEntry.entityID,
Audience: authCodeEntry.clientID, ... }`
(`identity_store_oidc_provider.go:2122-2132`). The struct's `aud` tag is a
plain string (`vault/identity_store_oidc.go:96-107`), which authlib accepts
alongside the list form R5 already relies on. The in-repo corroboration at
`deployments/infrastructure/nomad_oidc.tf:154` resolves and reads
`bound_audiences = [vault_identity_oidc_client.nomad.client_id]` against
this same provider. So R2 is right and the `audience` for the second element
must be the client id, not `memex`.

### P5 — the memex container reaches Vault discovery and JWKS; JWKS is RS256. HOLDS

Reproduced from inside the running alloc (`6ae458c1`), no `verify=False`:
`200` on the Vault discovery doc, `200` on `/.well-known/keys`, `200` on
Nomad's discovery doc. The live JWKS carries `alg: RS256` keys only, which
sits inside memex's default `['RS256','ES256']` (`config.py:1495-1498`), so
leaving `algorithms` unset is right. Vault's `jwks_uri` does end
`/.well-known/keys` and memex discovers rather than assumes
(`server/oidc.py:300-310`).

### P6 — v1.2.0 changes four log paths and one INVERTS R5's D2. HOLDS in substance, two symbol errors

The substance is exactly right and the D2 rewrite is genuinely forced. At
v1.1.0 `verify` returns silently on the unparseable path
(`server/oidc.py:156-159`) and the unknown-issuer path (`:161-164`), and
`_claims_to_context`'s `None` return is unlogged (`:216`). At v1.2.0 all
four lines the plan quotes exist verbatim: `not a parseable JWT`
(`:182-188`), `no configured provider matches issuer ... Configured
issuers` (`:200-205`), `OIDC token rejected for issuer` moved from `info`
to `warning` (`:251` vs v1.1.0 `:209`), and the new verified-but-unauthorized
warning (`:265-271`). The runbook target is confirmed stale:
`docs/memex-oidc-verification.md:152-155` reads "D2 emits **nothing** / A
silent `403` is the pass here."

Two evidence errors in the premise text. The class is `OidcVerifier`, not
`MemexOidcVerifier` (`server/oidc.py:136` at v1.2.0, `:119` at v1.1.0). And
`verify` at v1.1.0 holds four `logger.info` calls, not five; the fifth
(`:289`) is in `setup_oidc`.

### P7 — the bump is safe, no migration rides along. MOSTLY HOLDS, one part UNCERTAIN

The compare is 9 commits over 71 files, confirmed against the GitHub API.
No migration, schema, or API file appears; 52 of the 71 are the upstream
repo's own `.loop/` artifacts. The safety argument is confirmed by diff:
`resolve_client_headers` and `_read_workload_token` are byte-identical
across the tags, and `_resolve_bearer`'s `token_file`/`token_env` branch is
first and untouched (`auth_client.py:288-289` at v1.2.0). So R5's workload
path is genuinely unaffected.

Two small corrections. Four source modules changed, not five: `auth.py`,
`auth_client.py`, `config.py`, `server/oidc.py`, plus six test files. And
`config.py` also changed the `OidcProviderConfig` docstring
(`:1466-1477`), not only the `credential` field, though the conclusion that
R5's `grant: token_file` config validates unchanged still holds.

UNCERTAIN: I could not reproduce the ghcr tag probe. An anonymous pull token
for `jasperhg90/memex-jetson` is refused, so `1.2.0` in the registry rests
on the plan's captured credentialed probe. A wrong tag fails loudly at pull,
so this is not load-bearing for the design.

### P8 — Vault ignores unsupported scopes, so a missing `groups` scope fails silently. HOLDS

This is the plan's most important claim and it survives attack at source.
`pathOIDCAuthorize` requires `openid`
(`identity_store_oidc_provider.go:1744-1749`) and then filters under the
comment "Scope values that are not supported by the provider should be
ignored" (`:1751-1757`). Only the surviving scopes reach the auth-code entry
(`:1794-1801`) and from there `populateScopeTemplates` (`:2140`), which is
what emits the `groups` claim. The provider's supported set is exactly
`["groups"]` (`deployments/infrastructure/oidc.tf:99`), so memex's default
scope list authorizes fine and yields a token with no `groups` claim, and
nothing errors.

Two independent corroborations in this repo, both of which resolve:
`docs/vault-human-auth.md:300-306` records the same rule with a live
2026-07-31 measurement, and `deployments/infrastructure/nomad_oidc.tf:148-151`
shows the working Nomad login sending `scope=openid groups` on purpose. I
reproduced the plan's four-variant probe (all four returned the identical
`access_denied`) and added a fifth: `scope=profile` alone returns
`invalid_request` with `scope parameter must contain the "openid" value`,
which pins the ordering. The plan is honest that the probe cannot
discriminate and rests the claim on the source. That is the right call.

### P9 — no refresh token means fallback to the API key; earlier of two expiries. HOLDS

`_resolve_bearer` logs `Cached OIDC token expired and no refresh token is
available.` and returns `None` (`auth_client.py:314-316`), after which
`resolve_client_headers` returns `{'X-API-Key': ...}` when `api_key` is set
(`:277-278`). `token_cache_from_response` sets
`expires_at = min(expires_at, id_exp)` with the comment that `expires_in`
describes the ACCESS token (`:189-193`), and raises rather than falling back
when the response carries no id_token (`:183-188`). §9 mode 5 and Q3 follow
correctly.

### P10 — loopback matching is port-agnostic on BOTH sides, exact on host literal. HOLDS

`validRedirect` keys the loopback branch on the INPUT's hostname
(`identity_store_oidc_provider_util.go:29-31`), then strips the port from
the input (`:34`) and from each registered URI (`:41`) before comparing full
URL strings (`:43`). So a registered `127.0.0.1` URI IS treated as loopback,
which is the question R5's review left open. I reproduced all three probe
rows verbatim against the live `nomad` client
(`CFIY4Ai7WsIUIJBDAgPNStfeCn6wAiAG`): `localhost:4649` and `localhost:59999`
both `access_denied`, `127.0.0.1:4649` `invalid_redirect_uri`. The CLI side
holds too: `HTTPServer(('127.0.0.1', 0), _Handler)` (`memex_cli/auth.py:179`)
and `redirect_uri = f'http://127.0.0.1:{port}/callback'` (`:195`). §7's
two registered URIs are the right pair.

The authorize ordering §8's V3 depends on is confirmed: client, redirect,
provider `allowed_client_ids`, and the `openid` scope check all run before
`req.EntityID == ""` (`identity_store_oidc_provider.go:1699-1771`). See P19
for what V3 therefore does not prove.

### P11 — the operator entity is in `developer`. HOLDS

Reproduced live, read-only. Entity `351f302a-ada1-0e79-15d3-e22a4be2e3e4`
carries `group_ids` `[64780816-... , e86ec229-...]`; `developer` is
`64780816-...` with that entity as its only member, `oidc-smoke` is
`e86ec229-...`, and `admin` has `member_entity_ids = null`. So the `groups`
claim will be a list containing `developer`, which `_rule_matches` handles
by membership (`server/oidc.py:86-97`), and gating on `admin` would admit
nobody. Terraform source at `developer_group.tf:158-164` matches.

### P12 — `client_type` immutable, `id_token_ttl` capped by the key. HOLDS

Exact strings confirmed: `client_type modification is not allowed`
(`identity_store_oidc_provider.go:1148`) and `a client's id_token_ttl cannot
be greater than the verification_ttl of the key it references` (`:1136`).
The key's `verification_ttl = 86400` (`oidc.tf:46`), so Q3's 28800 clears
the ceiling.

Worth adding to §9 mode 4: the Terraform provider does NOT mark
`client_type` `ForceNew` (`resource_identity_oidc_client.go:79-85`), so a
wrong value does not surface as a plan-time replace. Terraform attempts an
in-place update and Vault refuses at apply. The remedy the plan names
(destroy and recreate, new client id, matching `audience` edit) is right,
but it needs an explicit `-replace`.

### P13 — the `client_creds` data source exists and handles a public client. HOLDS

`vault_identity_oidc_client_creds` is present in the linux_arm64 provider
binary at the exact path P13 cites (both `darwin_arm64` and `linux_arm64`
are vendored under `deployments/applications/.terraform/`). The source
branches as claimed: `clientSecret := ""; if clientType != "public" { ... }`
(`data_identity_oidc_client_creds.go:68-74`) and errors with
`no client found at %q` (`:55`), which is §9 mode 2's loud failure. Vault
omits `client_secret` from a public client's read
(`identity_store_oidc_provider.go:1247`). Neither root has an `outputs.tf`
or a `terraform_remote_state` block, so this is indeed the only cross-root
channel, and because `name = "memex"` is a literal the read happens at plan
time: wrong order fails the plan, not the apply. R3's ordering claim holds.

### P14 — memex is running and INFO records are visible. HOLDS, and events moved past it

R5 has landed since the plan was written. The memex job was resubmitted at
`2026-08-04T07:08:48`, `nomad job inspect memex` now shows
`MEMEX_SERVER__AUTH__OIDC`, and the alloc logs both
`API key authentication enabled (3 key(s) configured, 3 exempt path(s)).`
and `OIDC bearer-token authentication enabled (1 provider(s)).` at `info`.
So §10's assumption that R5 is applied is now fact, and S1's INFO line is
observable. The plan's instruction to re-measure the baseline rather than
trust P14 is the right hedge.

### P15 — the gates. HOLDS

Every anchor resolves: `.pre-commit-config.yaml:1` excludes `^\.(claude|loop)/`,
`:16-21` `nomad-fmt`, `:22-27` `terraform-fmt`, `:28-33` `terraform-validate`,
and the Python hooks carry `files: '^cli/'` at `:45`, `:51`, `:64`, `:72`.
`scripts/tf_validate.sh:8-20` validates the three roots offline.
`justfile:18-19` and `:44` resolve. The applications apply recipe does take
positional `refresh` then `target` (`deployments/applications/justfile:13-24`)
and the infrastructure one takes neither (`deployments/infrastructure/justfile:11-13`),
so R6b's `just apply true nomad_job.memex` is correct. `.loop/config.json`
carries `gates: ["just pre_commit"]`, `require_review`, `require_eval`.

### P16 — Vault 2.0.3. HOLDS

`vault status` reports `Version 2.0.3`, matching the pin at
`bootstrap/inventory/group_vars/all.yml:11`. Nomad is 2.0.4 at `:12`. Every
Vault source citation above was read at tag `v2.0.3`.

### P17 (implicit) — every cited `path:line` says what the plan claims. BREAKS

One anchor is stale. `deployments/applications/services/hermes.hcl:405` does
NOT hold `MEMEX_API_KEY`; it is a comment line reading
`# renewal after the first with no materiality test, which at ttl = 1h`.
`MEMEX_API_KEY` appears at `:201`, at `:437`, and as an `env_passthrough`
entry at `:258` and `:272`. Git shows why: `:405` was correct at `64f4adb`
and shifted when R5's commit `14e56ff` landed the identity stanza. The plan
inherited the anchor from R5's eval marker (`.loop/evals/R5-...md:24`),
which carries the same stale pair. The plan cites it twice, in §5 and in §8
G1, so a guardrail check would be run against a comment.

Everything else I opened resolves and supports its claim, including the
whole of `oidc.tf`, `nomad_oidc.tf`, `memex.hcl:7/38/39/138-148`,
`services.tf:1-9/24-26/125-156/166-188/180`, `secrets.tf:71/79-86`,
`.gitignore:2`, `roles.tf:153`, `developer_group.tf:158-164`,
`docs/vault-human-auth.md:262-306/300-306/331-334/361-369`,
`docs/workload-identity.md:195-198/213`,
`docs/memex-oidc-verification.md:1/21-38/34-35/118-138/140-160/152-155`,
and `.loop/evals/R5-...md:15/18/23/26`.

### P18 (implicit) — §8's V2 expected log line is what memex will emit. BREAKS

V2 expects `OIDC bearer rejected: not a parseable JWT (1 dot-separated
segments).` It will read `(2 ...)`.

memex logs `token.count('.') + 1` (`server/oidc.py:187`). Vault's OIDC
access token is a batch token
(`identity_store_oidc_provider.go:2077-2082`), whose ID is
`consts.BatchTokenPrefix` plus a `base64.RawURLEncoding` blob
(`vault/token_store.go:1243`, `:1266`), where the prefix is `hvb.`
(`sdk/helper/consts/token_consts.go:8`). Base64url contains no dots, and the
namespace suffix is appended only outside the root namespace
(`token_store.go:1269-1271`). So the token is `hvb.<blob>`, one dot, and
memex reports two segments.

This matters because §8 promises "one deterministic row per check above at a
100% bar" and the security-shaped rows include V2. As written the row fails
on a correctly working system. It is the same class of defect as the R5 D2
inversion this ticket exists to fix.

### P19 (implicit) — §8 exercises both directions on the human path. PARTIALLY BREAKS

The GRANT direction is covered by V1 and is honestly scoped: §2 says the
proof is a browser login that cannot be scripted, and §10 R6d isolates it as
the one manual step. Good.

The DENY direction is thinner than it reads. V2 denies an opaque token, and
V3 proves the Vault-side gate is reachable while explicitly conceding it
does not prove another group is refused. But the plan's own §9 mode 1 names
"the `groups` claim never reaches the id_token" as "the single most likely
fault and it is invisible from the response", and §8 has NO check that
exercises it. D2 is offered as the detector, and the log line is the right
detector, but D2 as specified presents a Nomad workload token from R5's
throwaway job, so it never puts a Vault id_token through that path.

Closing it is one operator action inside R6d, which is already manual: after
V1 passes, re-run `memex auth login` once with `scopes: ["openid"]`, expect
`403` plus the verified-but-unauthorized warning naming the claims present,
then restore `["openid","groups"]` and log in again. The config validator
permits that shape, since only `openid` is required
(`config.py:1728-1732`).

Two smaller notes on V3. Vault validates PKCE AFTER the entity check
(`identity_store_oidc_provider.go:1806-1809`), and a root token has no
entity, so V3 proves the four things it claims and nothing about PKCE or
`client_type`; V1 is the only proof of those. And the live response carries
a third field, `"state":"abcdefghij"`, alongside the two the plan quotes.

### P20 (implicit) — V1 is a clean one-shot operator step. PARTIALLY BREAKS

This repo already records that the first attempt through this provider can
fail for a reason that has nothing to do with R6.
`docs/vault-human-auth.md:322-329` warns that the redirect lands on a Vault
**UI** path, so the browser must already hold a Vault UI session or the
first attempt fails with a generic "Failed to sign in with SSO", observed
2026-08-02 and not root-caused. Live discovery confirms the endpoint:
`authorization_endpoint` is
`https://vault.lab.orangecluster.nl/ui/vault/identity/oidc/provider/lab/authorize`.

For memex this is worse than for the Nomad button. The CLI's loopback server
only completes on a `/callback` GET (`memex_cli/auth.py:154-179`), so when
the authorize page fails the redirect never arrives and the command sits for
the full `_LOGIN_TIMEOUT_SECONDS = 300` (`:46`) before raising
`LoginError('timed out waiting for the browser redirect.')` (`:221-222`).
An operator running V1 cold would read that as a broken ticket.

The plan mentions this nowhere: not in V1, not in §9's failure modes, not in
Q1. It is the single most likely thing to go wrong on the one step that
cannot be scripted.

### P21 (implicit) — R5's artifacts are still at their unarchived paths. BREAKS (it broke during this review)

Q4 predicted this and it has now happened. `loopctl archive` relocated R5's
artifacts partway through this pass. `.loop/evals/R5-rollout-memex-oidc-auth.md`
no longer exists; the file is now
`.loop/archive/R5-rollout-memex-oidc-auth/eval.md`, byte-identical, so the
line numbers `:15`, `:18`, `:23` and `:26` still land on the rows the plan
names. R5's plan and its plan-validator verdict moved the same way, to
`.loop/archive/R5-rollout-memex-oidc-auth/plan.md` and
`.loop/archive/R5-rollout-memex-oidc-auth/verdict.plan-validator.md`.

So four citations are now dead paths: §3's pointer to R5's review, §4's
three eval rows, §7's supersession-note target, and Q4's anchors. More than
a citation, §10 R6e's third deliverable is "the supersession note on
`.loop/evals/R5-rollout-memex-oidc-auth.md`", which names a file that is
gone. The substance is untouched: the rows still say what the plan says they
say.

## Most dangerous assumption

**P8, that the `groups` claim is opt-in on the REQUEST.** The plan already
identifies it as the likeliest silent failure, and it is: login succeeds,
the token verifies, and every request then `403`s with nothing in the
response to say why. I attacked it hardest and it HOLDS, at Vault's source
(`identity_store_oidc_provider.go:1751-1757`) and twice more in this repo
(`docs/vault-human-auth.md:300-306`, `nomad_oidc.tf:148-151`). R7 is
correctly a hard requirement.

Because the premise holds, the danger moves to its detection, which is P19:
the plan names the fault, states its detector, and then never runs a check
that exercises it.

## Required fixes

1. **Fix the stale hermes anchor.** Replace `:405` with `:437` in §5 and in
   §8 G1. `MEMEX_API_KEY` is at `deployments/applications/services/hermes.hcl:201`
   and `:437`; `:405` is a `change_mode` comment. (P17)
2. **Fix §8 V2's expected string** to `not a parseable JWT (2 dot-separated
   segments)`. Vault's batch token is `hvb.` plus base64url
   (`sdk/helper/consts/token_consts.go:8`, `vault/token_store.go:1243`,
   `:1266`) and memex logs `token.count('.') + 1`
   (`server/oidc.py:187`). Carry the correction into R6's eval row. (P18)
3. **Add a human-path DENY for the missing `groups` claim** to §8 and to
   R6d: re-login once with `scopes: ["openid"]`, expect `403` plus the
   verified-but-unauthorized warning naming the claims present, then
   restore. Without it the plan's own §9 mode 1 ships untested.
   (`server/oidc.py:265-271`, `config.py:1728-1732`) (P19)
4. **Record the Vault UI session precondition on V1**, in §8 and in Q1's
   snippet: log into the Vault UI in the same browser first, or the first
   `memex auth login` hangs 300 s and then reports a redirect timeout.
   (`docs/vault-human-auth.md:322-329`, `memex_cli/auth.py:46`, `:221-222`)
   (P20)
5. **Correct P6 and P7's evidence text.** The class is `OidcVerifier`, not
   `MemexOidcVerifier` (`server/oidc.py:136` at v1.2.0, `:119` at v1.1.0),
   and `verify` at v1.1.0 has four `logger.info` calls, not five (the fifth
   is in `setup_oidc` at `:289`). P7's compare touched four source modules,
   not five, and also changed the `OidcProviderConfig` docstring
   (`config.py:1466-1477`). Neither slip changes a conclusion, but a premise
   that names a symbol which does not exist is not evidence.

6. **Repoint every R5 artifact path to the archive.** R5 was archived
   during this review. `.loop/evals/R5-rollout-memex-oidc-auth.md` is now
   `.loop/archive/R5-rollout-memex-oidc-auth/eval.md` (content and line
   numbers unchanged), R5's plan is `.../plan.md` and its review is
   `.../verdict.plan-validator.md`. Update §3, §4, §7 and Q4, and make
   §10 R6e's supersession note land on the archived file. (P21)

## Recommended, not blocking

- **§9 mode 4:** note that `client_type` is not `ForceNew` in the provider
  (`resource_identity_oidc_client.go:79-85`), so a wrong value fails at
  apply with Vault's own error rather than planning a replace. The remedy
  needs an explicit `-replace`.
- **§8 V3:** say that PKCE is validated after the entity check
  (`identity_store_oidc_provider.go:1806-1809`), so V3 proves the four
  things it claims and nothing about PKCE or `client_type`. The live
  response also carries a `state` field.
- **P7's registry probe** is the one claim I could not reproduce; an
  anonymous ghcr token for that package is refused. Failure would be loud at
  pull, so this is a note, not a fix.
- The applications root uses `provider "vault" {}` with no explicit auth
  (`deployments/applications/providers.tf:36`), so the new data source read
  rides the ambient `VAULT_TOKEN`, which is root today. Worth one line in §9
  if F12's deployer privilege split ever scopes that token, since
  `identity/oidc/client/memex` would then need a read capability.

## Contract hygiene

- **Code surface with resolved anchors:** clean apart from the `:405` slip
  in fix 1.
- **Discovered, not assumed, gates:** P15 verified against
  `.pre-commit-config.yaml`, `scripts/tf_validate.sh`, both root justfiles
  and `.loop/config.json`. Correct, including the positional-argument shape
  of the applications apply recipe.
- **Explicit non-goals:** §5 is specific and anchored, and correctly ring-
  fences R5's first array element and the hermes wheels.
- **Tests homed in the code surface:** §8's artifacts are declared in §7
  (`docs/memex-oidc-verification.md`, `docs/vault-human-auth.md`, the R5
  eval note), and the eval marker path is named.
- **Forks surfaced:** Q1, Q2, Q3, Q4, Q5 each carry a recommendation, and Q6
  is marked SETTLED with the evidence that settles it. Q4's call to append a
  supersession note rather than edit R5's operator-signed rows is the right
  one, and its three named rows (`:15`, `:18`, `:23`) are exactly the rows
  that go false: `:17` survives because it asserts the message and not the
  level, and `:15`'s `info` level is still correct on v1.2.0
  (`server/oidc.py:345-348`). Q4's warning about `loopctl archive` moving the
  path was not hypothetical: the move happened during this review. See P21.
