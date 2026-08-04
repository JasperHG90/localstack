---
verdict: pass-with-required-fixes
plan: d6e077019ca09af967fa281086295bdfe4bd29ed90673e08528a2c5c834509fc
---

# Plan review — R6-rollout-memex-human-oidc (pass id: plan-validator)

Supersedes my `814a2eff` verdict. Fingerprint recomputed before and after
writing: `sha256sum .loop/plans/R6-rollout-memex-human-oidc.md` =
`d6e077019ca09af967fa281086295bdfe4bd29ed90673e08528a2c5c834509fc`.

## Deterministic floor

`loopctl verify-plan R6-rollout-memex-human-oidc` → `valid`. No mechanical
defect; proceeded to falsification.

## Premise verdict

**PARTIALLY SOUND.**

The two new design changes are the strongest part of the plan. The
per-client-key mechanism, the `access_token_ttl` coupling, the rule ordering
and the Q7 blocker all survived direct attack against Vault v2.0.3 and memex
v1.2.0 source plus live probes. Three assumptions break or wobble, all in
§8/§9 rather than in the design: the second break-glass lever does not do
what §9 says it does, the roles.tf blast radius is under-stated, and V5's
join/restore step trusts a live-state snapshot in a way that can silently
drop a group member.

None of these sinks the ticket. All three must be fixed before implementation
because §7 requires publishing §9's break-glass text into
`docs/vault-human-auth.md`, so a wrong claim would ship as a runbook.

## Per-assumption findings

Every Vault citation checked against `github.com/hashicorp/vault` tag
`v2.0.3` (tag exists; all cited line numbers resolve). Every memex citation
checked against `github.com/JasperHG90/memex` tag `v1.2.0`. Live probes were
read-only GETs against `vault.lab.orangecluster.nl`.

### The plan's stated premises

**P1 — memex v1.2.0 `credential` setting, names Vault, `audience` = client_id. HOLDS.**
`credential: Literal['access_token','id_token']` at `config.py:1657-1667`,
and its description names "e.g. HashiCorp Vault" and states "The server must
then accept the client_id as an audience". `algorithms` default
`['RS256','ES256']` at `:1495-1498`. Client default `scopes`
`['openid','profile','email','offline_access']` at `:1636-1638`.
`_rule_matches` does membership on a list claim at `server/oidc.py:86-97`.
`TokenCache.bearer_token` returns the id_token under `credential='id_token'`
at `auth_client.py:76-81`, and the id_token is persisted to the cache only
under that credential (`:205-209`) — so V1/V2/V6 can all read `token.json`
as the plan assumes.

**P2 — authorization_code only, no device endpoint, no refresh token. HOLDS.**
Re-ran the discovery probe today:
`grant_types_supported ["authorization_code"]`, `scopes_supported
["groups","openid"]`, `token_endpoint_auth_methods_supported
["none","client_secret_basic","client_secret_post"]`,
`code_challenge_methods_supported ["plain","S256"]`, and no
`device_authorization_endpoint` key. CLI raises `LoginError` on its absence
at `memex_cli/auth.py:253-256`. Vault's token response is built with exactly
`token_type / access_token / id_token / expires_in`
(`identity_store_oidc_provider.go:2166-2171`) — no `refresh_token`.

**P3 — public PKCE client accepted. HOLDS.**
`none` in the live `token_endpoint_auth_methods_supported`; PKCE forced for
public clients at `identity_store_oidc_provider.go:1807-1809` (authorize) and
again at `:2060-2061` (token). CLI sends `code_challenge_method: 'S256'` at
`memex_cli/auth.py:203-204`.

**P4 — id_token `aud` IS the client id. HOLDS.**
`Audience: authCodeEntry.clientID` and `Issuer: provider.effectiveIssuer` at
`identity_store_oidc_provider.go:2124-2126`. Repo corroboration at
`deployments/infrastructure/nomad_oidc.tf:154`.

**P5 — issuer string and RS256 JWKS. HOLDS on the parts I could re-probe.**
Live discovery returns `issuer` exactly
`https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab` and
`jwks_uri` ending `/.well-known/keys`, and the JWKS keys are `alg: RS256`.
The in-container TLS-trust half (`nomad alloc exec`) I did not re-run; it is
R5-era and already load-bearing in production.

**P6 — v1.2.0 inverts R5's D2. HOLDS.**
All four v1.2.0 paths resolve: `not a parseable JWT (%d dot-separated
segments)` at `server/oidc.py:182-188`, `no configured provider matches
issuer` at `:200-205`, `OIDC token rejected for issuer` (now `warning`) at
`:251`, and `verified ... but matched no grant_rule` at `:265-271`. R5's
runbook at `docs/memex-oidc-verification.md:152-155` does assert `D2 emits
nothing` / "A silent 403 is the pass here". The rewrite is required, and
§10 R6c homes it in the right subticket.

**P7 — the bump is safe, no migration. HOLDS, with one UNCERTAIN sub-claim.**
GitHub compare API for `v1.1.0...v1.2.0`: 9 commits, 71 files, and exactly
four non-test source files — `packages/cli/src/memex_cli/auth.py`,
`packages/common/src/memex_common/auth_client.py`,
`packages/common/src/memex_common/config.py`,
`packages/core/src/memex_core/server/oidc.py`. No migration or schema file.
I extracted and diffed `resolve_client_headers` and `_read_workload_token`
across the two tags: both byte-identical, as claimed.
UNCERTAIN: the `ghcr.io/jasperhg90/memex-jetson:1.2.0` tag. Anonymous ghcr
auth is denied and I did not use the repo's registry credential. Low risk:
the failure is a loud image-pull error and R6c isolates it.

**P8 — Vault ignores unsupported scopes. HOLDS.**
`identity_store_oidc_provider.go:1751-1757` filters requested scopes against
`provider.ScopesSupported` and drops the rest silently. With `lab`'s
`scopes_supported` being `["groups","openid"]` (live), memex's default scope
list yields a valid token with no `groups` claim. §9 mode 1 is real.

**P9 — fallback to the API key at expiry. HOLDS.**
`Cached OIDC token expired and no refresh token is available.` at
`auth_client.py:315`; `{'X-API-Key': ...}` return at `:278`.

**P10 — loopback redirect matching. HOLDS, and sharper than stated.**
`identity_store_oidc_provider_util.go:22-49`: the loopback branch keys on the
INPUT hostname (`:29`), then strips the port from the registered side too
(`allowedURI.Host = allowedURI.Hostname()`, `:41`) and compares the full
string. So `127.0.0.1` and `localhost` are distinct host literals and both
entries are needed, exactly as §7 says. CLI binds
`HTTPServer(('127.0.0.1', 0), ...)` at `memex_cli/auth.py:179` and builds
`http://127.0.0.1:{port}/callback` at `:195`; login timeout is
`_LOGIN_TIMEOUT_SECONDS = 300` at `:46`, matching V1's precondition note.
Authorize check order confirmed at `:1699-1771`: client → redirect →
provider `allowed_client_ids` → scope → response_type → entity. V3's four
claims all sit before the entity check. Note PKCE validation sits at
`:1806-1809`, AFTER the entity check, so V3 correctly does not claim it.

**P11 — one human entity, `admin` empty. UNCERTAIN (not re-verified).**
I have no Vault token and did not re-run the identity reads. The Terraform
side is consistent (`roles.tf:127-136`, `external_member_entity_ids = true`
at `:131`; `auth_userpass.tf` is the only entity source). See P26 below:
V5's restore step is where this snapshot being stale would cost something.

**P12 — `client_type` immutable. HOLDS.** `identity_store_oidc_provider.go:1147-1149`.

**P13 — the creds data source handles a public client. HOLDS.**
`terraform-provider-vault` v5.3.0
`vault/data_identity_oidc_client_creds.go:69-72` branches `if clientType !=
"public"` before reading `client_secret`, and errors `no client found at %q`
at `:55` — §9 mode 4's loud failure.

**P14 — R5 is applied and live. UNCERTAIN (not re-verified).** No cluster
job access attempted. The plan already instructs re-measuring the baseline
before starting, which is the right handling.

**P15 — gates. HOLDS.** `.pre-commit-config.yaml:16-21` `nomad-fmt`,
`:22-27` `terraform-fmt`, `:28-33` `terraform-validate` running
`scripts/tf_validate.sh`, whose roots array at `:8-12` is the three named.
Python hooks scoped `files: '^cli/'` at `:37-53`. `just pre_commit` at
`justfile:18-19`, `worktree_setup` at `:44`. `.loop/config.json` carries
`gates: ["just pre_commit"]`, `require_review: true`, `require_eval: true`.

**P16 — Vault 2.0.3. HOLDS.** Live `sys/health` returns `"version":"2.0.3"`.
Every `v2.0.3` line citation in this plan resolved.

**P17 — the per-client key lifts the ceiling. HOLDS. This is the load-bearing
one and it is correct.**
`pathOIDCCreateUpdateClient` resolves the client's OWN key
(`getNamedKey(ctx, req.Storage, client.Key)`,
`identity_store_oidc_provider.go:1115`) and caps against THAT key:
`if client.IDTokenTTL > key.VerificationTTL` at `:1135-1137`. The comparison
is strictly greater, so `id_token_ttl = 2592000` against
`verification_ttl = 2592000` is legal at the boundary. `key` is per-client
and immutable (`:1106-1108`), and delete is blocked while a client references
it (`identity_store_oidc.go:858-869`). Key registration is enforced at the
TOKEN endpoint (`:1982-1986`), not at authorize — so §8's caveat that V3
cannot see a missing `vault_identity_oidc_key_allowed_client_id` is right.
`access_token_ttl` is set at `:1139-1143` with no cap against the key, so
`2592000` there is also legal.

**P18 — the key rules. HOLDS.** `rotation_period >= 1m` at
`identity_store_oidc.go:574-576`; `verification_ttl <= 10x rotation_period`
at `:584-586`. 604800 / 2592000 passes (4.29x). Rotated-out public keys get
`ExpireAt = now + verificationTTL` and stay in the ring
(`rotate`, `:1714-1722`); the periodic function prunes expired ring members
at `:1997-2016`. But see P24 — the plan draws the wrong conclusion from this
same code for its second break-glass lever.

**P19 — the provider JWKS is built from its allowed clients' keys. HOLDS.
This was the other design-critical claim and it is exactly right.**
`pathOIDCReadProviderPublicKeys` calls
`keyIDsReferencedByTargetClientIDs(ctx, req.Storage,
provider.AllowedClientIDs)` at `identity_store_oidc_provider.go:1607`, and
that helper walks each allowed client id, collects `client.Key`
(`:1660-1669`), and emits every KeyID in that key's ring (`:1688-1690`). So
the one-line append at `deployments/infrastructure/oidc.tf:79-84` is what
publishes `memex-human`, and removing it unpublishes it. Live JWKS today
returns 3 keys, first kid `d74dab14-0de3-7716-e36f-870bd2e43a79`, matching
the plan's probe. memex caches at `_JWKS_CACHE_TTL_SECONDS = 3600.0`
(`server/oidc.py:46`) with the unknown-kid forced refetch at `:216-238`.
The 30-day design does NOT fail closed at verification time.

**P20 — memex takes the FIRST matching grant_rule. HOLDS, three ways.**
`for rule in provider.grant_rules: ... break` with a `for/else` fallback at
`server/oidc.py:106-117`; the field description "evaluated in order (first
match wins)" at `config.py:1530-1533`; and `OidcGrantRule`'s docstring "The
first matching rule in a provider's `grant_rules` wins" at `:1399-1407`.
`admin` at index 0 is correct and R19 is real.

**P21 — `access_token_ttl` is coupled to the session. HOLDS end to end. The
reversal of my earlier advice is correct.**
memex: `expires_in = float(data.get('expires_in', 3600))`,
`expires_at = time.time() + expires_in`, then under `credential='id_token'`
`expires_at = min(expires_at, id_exp)` at `auth_client.py:180-193`, with the
in-code comment "`expires_in` describes the ACCESS token".
Vault: `accessTokenExpiry := accessTokenIssuedAt.Add(client.AccessTokenTTL)`
at `identity_store_oidc_provider.go:2079-2080`, and
`"expires_in": int64(accessTokenExpiry.Sub(accessTokenIssuedAt).Seconds())`
at `:2170` — literally `access_token_ttl`, computed independently of anything
the token store does.
Uncapped: I read `TokenStore.create` from `token_store.go:1054` through the
batch branch at `:1206-1225` and there is no TTL clamp or rejection on either
path; the batch branch marshals `TTL: int64(entry.TTL)` straight through.
`expiration.go:61` is `maxLeaseTTL = 32 * 24 * time.Hour`, above 30 days.
So a short `access_token_ttl` would cap the session at that value and the
client would fall back to `X-API-Key` with every request still 200. R18 and
§9 mode 2 are right, and V6 is the only detector.

**P22 — an app-user tier has nowhere to record members. HOLDS.**
`vault_identity_group.app_user` at `roles.tf:165-177` sets `name`, `type`,
`policies` and `metadata` and no `member_entity_ids`. `local.app_user_groups`
at `:152-163` is name-to-description. The provider writes
`member_entity_ids` authoritatively on create at
`resource_identity_group.go:144-147` and on update at `:159-172` (gated on
`d.HasChanges(..., "member_entity_ids", ...)`) whenever
`external_member_entity_ids` is false — which it is, deliberately
(`roles.tf:172-174`). The scaffold's own comment at `roles.tf:158-161` and
`docs/cluster-roles.md:140-141` both point at an edit to `member_entity_ids`
that has no field to land on. Q7 is real and correctly blocking.

**P23 — `reader` is READ only and the probe route is `require_write`-guarded. HOLDS.**
`Policy` enum and `POLICY_PERMISSIONS` at `config.py:1318-1330`;
`require_write = require_permission(Permission.WRITE)` at
`server/auth.py:288`; `@router.patch('/notes/{note_id}/title',
dependencies=[Depends(require_write)])` at `server/notes.py:370`, with
`rename_note` defined at `:371` — the dependency does run before the handler,
so a fabricated note id mutates nothing. The V1/V5 discriminator is sound.

### Load-bearing assumptions the plan left implicit

**P24 — "repeat `rotate verification_ttl=0` until no key that signed a live
token remains" (§9 break-glass lever 2). BREAKS.**
`namedKey.rotate` stamps `ExpireAt` on the CURRENT signing key ONLY:

```go
// vault/identity_store_oidc.go:1715-1722
if k.SigningKey != nil {
    for _, key := range k.KeyRing {
        if key.KeyID == k.SigningKey.KeyID {
            key.ExpireAt = now.Add(verificationTTL)
            break
        }
    }
}
```

Then `k.SigningKey = k.NextSigningKey` (`:1740`). Keys rotated out earlier
keep the `ExpireAt` they were stamped with at their own rotation — up to 30
days out under this key's `verification_ttl` — and nothing in `rotate`
revisits them. With `rotation_period = 604800` inside a 30-day window the
ring carries roughly four such keys, and each of them signed live tokens.

So repeating does not converge. Call 1 expires the key signing right now;
call 2 expires the freshly promoted `NextSigningKey`, which has signed
nothing; every further call expires another unused key. The older ring
members are never touched, stay in the JWKS (`keyIDsReferencedByTargetClientIDs`
emits every ring KeyID at `identity_store_oidc_provider.go:1688-1690`, and
the periodic prune at `identity_store_oidc.go:1997-2016` only removes ones
whose own `ExpireAt` has passed), and tokens they signed keep verifying.

The escape hatch is also shut: lowering the key's `verification_ttl` through
the update path does not re-stamp existing ring members
(`identity_store_oidc.go:568-676` writes key fields only), and the write is
refused outright while a referencing client's `id_token_ttl` exceeds the new
value (`:612-620`) — which it would, at 2592000.

Lever 2's true reach is "tokens issued since the last rotation", at most 7
days' worth. Lever 1 is unaffected and remains total.

**P25 — "the roles.tf edit's plan diff is one new group and no change to
`admin`" (§9). BREAKS.**
`local.all_app_user_group_ids = values(local.app_user_group_ids)`
(`roles.tf:199-201`) is consumed by `vault_identity_oidc_assignment.smoke`:

```hcl
# deployments/infrastructure/oidc.tf:129
group_ids  = concat([vault_identity_group.smoke.id], local.all_app_user_group_ids)
```

Adding `app-memex-readers` to `local.app_user_groups` therefore also grows
the smoke assignment's `group_ids`. That is F2's deliberate design
(`oidc.tf:125-128`, `roles.tf:196-198`), not a bug — but the plan never says
it. Effective access does not change today, since the only entity is already
in `oidc-smoke`. What does change is the apply: an implementer holding §9's
detector ("exactly one new `vault_identity_group.app_user[...]` and no change
to `vault_identity_group.admin`") and §5's "No change to the smoke client"
meets an unexplained diff on a shared resource and has no way to tell
expected from wrong.

**P26 — "V5 can restore `admin` to empty because it has no other members".
UNCERTAIN, and the failure is destructive.**
Membership is replaced, not merged (`docs/cluster-roles.md:96-100`), the
group is `external_member_entity_ids = true` so Terraform holds no record
(`roles.tf:131`), and the file says so itself: "leaving yourself in `admin`
after an incident is invisible to every `terraform plan`. Checking is a
habit, not a gate" (`roles.tf:125-126`). V5 leans on P11's snapshot for both
the join (`nothing else needs listing`) and the restore
(`member_entity_ids=`). If anyone joined `admin` between the probe and the
run, V5 silently evicts them.

## Most dangerous assumption

**P24.** The plan's honesty about the 30-day bearer rests on §9 offering two
working levers, and §7 requires writing that text into
`docs/vault-human-auth.md` as guidance for every future consumer. Lever 2 as
written tells an operator mid-incident to keep rotating until the tokens are
dead. That loop never terminates in the way described, and the operator would
conclude they had revoked credentials that are still live for up to three
more weeks. A revocation instruction that reads as sufficient and is not is
worse than no second lever at all.

## Required fixes

1. **Rewrite §9's break-glass lever 2 (and its P18 tail).** State what
   `rotate verification_ttl=0` actually reaches: only the key signing at that
   moment, so at most the tokens issued since the last rotation. Delete
   "repeat ... until no key that signed a live token remains" — repetition
   expires freshly promoted keys that signed nothing, never the older ring
   members. Evidence: `identity_store_oidc.go:1714-1722` and `:1740`.
   Name lever 1 as the only total one, and add the honest third option if
   full revocation is wanted while keeping the client: destroy the client,
   then the key (that order, per `identity_store_oidc.go:858-869`), and
   recreate — which mints a new `client_id` and forces a server `audience`
   edit, the cost §9's Reversibility paragraph already states. Keep this
   correction in the `docs/vault-human-auth.md` own-key rule §7 mandates.

2. **Record the smoke-assignment consequence.** In §9's roles.tf blast-radius
   bullet, add that `vault_identity_oidc_assignment.smoke.group_ids`
   (`deployments/infrastructure/oidc.tf:129`, via
   `local.all_app_user_group_ids` at `roles.tf:199-201`) also grows by one,
   that this is F2's intent and not a defect, and that effective access is
   unchanged because the only entity is already in `oidc-smoke`. Extend the
   detector to expect that diff, and note in §5 that the smoke ASSIGNMENT
   moving is expected even though the smoke CLIENT (`oidc.tf:133-148`) does
   not.

3. **Make V5 restore what was there, not empty.** Have V5 read
   `vault read identity/group/name/admin` immediately before the join, join
   with `<existing-members> + operator`, and restore to exactly the
   pre-existing set instead of `member_entity_ids=`. P11's snapshot is a
   point-in-time read of a group Terraform does not manage and no plan can
   diff (`roles.tf:125-126`, `:131`).

4. **Mark the ghcr `1.2.0` tag claim in P7 as probe-reported.** The
   compare-API half of P7 is independently confirmed; the registry half I
   could not reproduce. One clause is enough — R6c already isolates it and
   the failure is loud.

## Contract hygiene

All twelve sections present. Anchors resolved: `roles.tf:127-136`, `:131`,
`:152-163`, `:165-177`, `:192-194`, `:199-201`, `:31-36`;
`oidc.tf:28-32`, `:42-47`, `:55-70`, `:72-84`, `:94-100`, `:104-107`,
`:123-131`, `:133-148`; `nomad_oidc.tf:30-34`, `:44-57`, `:61-64`;
`services.tf:1-19`, `:24-26`, `:167-188`, `:180`;
`memex.hcl:138-148`; `hermes.hcl:201` and `:437` (R6 corrects R5's stale
`:405`); `docs/vault-human-auth.md:262-306`, `:322-329`, `:331-334`;
`docs/cluster-roles.md:96-105`, `:107-114`, `:118-126`, `:140-141`;
`docs/memex-oidc-verification.md:21-38`, `:140-160`;
`.loop/archive/R5-rollout-memex-oidc-auth/eval.md:15`, `:18`, `:23`, `:26`.
Gates match the repo (P15). Non-goals explicit, including the `lab`-key one
with G4 behind it. Every §8 artifact is homed in §7
(`docs/memex-oidc-verification.md`). Q7 is a genuine fork carried in Open
Questions with a recommendation, which the create-ticket contract asks for
rather than forbids; its shape-1 recommendation is sound and shape 3 is
rightly rejected, since the `for_each` at `roles.tf:166` would apply
`external_member_entity_ids` to every future tier.

On the §8 rows the briefing asked about: V5 detects rule ordering (P20 gives
it teeth, P23 gives it a clean discriminator) subject to fix 3; V6 detects
the `access_token_ttl` trap and nothing else does (P21); G4 detects the
`lab`-key shortcut on both halves, since the standalone
`vault_identity_oidc_key_allowed_client_id` against `memex-human` leaves
`lab.allowed_client_ids` alone. V2's "two, not one" segment count is right —
`_unverified_parts` unpacks `token.split('.')` into three names at
`server/oidc.py:82`, so a one-dot `hvb.` token raises and `token.count('.')
+ 1` logs 2 — and the plan's instruction to confirm against the live token
rather than trust either number is the correct discipline.
