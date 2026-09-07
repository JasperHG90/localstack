---
epic = "openviking"
depends_on = []
priority = 100
summary = """
Make Vault the authentication provider for OpenViking. A person logs into Vault
once with userpass and holds a renewable token. A Vault identity-token role
mints a short-lived RS256 JWT carrying the person's entity name, and OpenViking
runs auth_mode "oidc" and verifies that JWT against Vault's identity JWKS.
This ticket is the foundation and proves the chain end to end. Hermes re-pointing, deleting
the seed and key apparatus, and the edge/hostname collapse are follow-up tickets
and explicit non-goals. Hermes BREAKS the moment auth_mode flips.
"""
---

# Ticket: OV3-openviking-vault-identity

## 1. Title

Replace OpenViking's seed-derived per-person API keys with Vault identity
tokens: entities and userpass users for both people, a
`vault_identity_oidc_role` whose template emits the entity name, and `auth_mode`
`"oidc"` verifying against Vault's identity JWKS.

## 2. Size / Effort

**L.** Two Terraform roots, a rewrite of the singular human-identity resources
into a `for_each`, a Vault subsystem the repo has never used (identity tokens,
distinct from the OIDC provider), the service config document, the pre-commit
guard that asserts it, and a docs section that becomes false. Blast radius
reaches the CLI's default username and the operator's own login path.

## 3. Triggered by

Operator request: make Vault the identity for OpenViking rather than a gate in
front of it, closing the trade `docs/openviking.md:200` already records as a
known regression ("What this costs against OIDC").

## 4. Context

### What exists

- Human identity is SINGULAR. `deployments/infrastructure/identity.tf:21`
  enables the only human auth backend; `:27`, `:36`, `:50` and `:61` are one
  hardcoded `operator` password, userpass user, entity and alias. `:73` records
  the intended growth path ("adding a second human is one `member_entity_ids`
  entry"), which was never taken.
- The second person exists only as a string. `veerle` appears at
  `deployments/applications/secrets.tf:283` in `openviking_people` and nowhere
  else under `deployments/`. She has no Vault entity, no userpass user, no
  password.
- OpenViking authenticates with keys Terraform derives from a seed.
  `deployments/applications/secrets.tf:288` maps each person to an account of
  the same name. The derived keys land in Vault and the server is reconciled to
  them by `openviking_users` at `deployments/applications/services.tf:502`.
- The service runs `auth_mode` `"api_key"`
  (`deployments/applications/services/openviking/ov.conf.json:67`) with a
  `root_api_key` (`:68`) and Argon2id hashing (`:60`).
- `scripts/check_openviking_config.py:42` pins `EXPECTED_AUTH_MODE` to
  `"api_key"` and treats `"oidc"` as the mutant its self-test must catch
  (`:288`).
- Vault has an OIDC PROVIDER (`deployments/infrastructure/oidc.tf:118`) serving
  the authorization-code flow for browsers. It has NO identity-token role: the
  live `vault list identity/oidc/role` returns "No value found". These are
  different issuers and this ticket uses the identity-token one.

### What is wrong

An OpenViking key never expires, exists in Terraform state and in Vault, and is
revoked only by re-deriving it. A Vault identity token expires on the role's TTL
and is verified cryptographically against a JWKS the server fetches itself. The
person already holds a Vault login, so the OpenViking key is a second secret
that buys nothing the first one does not already establish.

### Measured facts this plan is built on

Full evidence in "Premises / assumptions". The three that shape the design:

1. The identity-token `iss` today is `http://192.168.2.30:8200/v1/identity/oidc`
   (Vault's `api_addr`), NOT the edge hostname, because `identity/oidc/config`
   has no issuer set. OpenViking compares `iss` exactly, so this decides the
   `issuer` string in `ov.conf.json`.
2. The token's `sub` is the entity UUID, not the name. The name must ride its
   own claim and OpenViking must map THAT claim.
3. From inside the running OpenViking container, Vault discovery and JWKS both
   answer 200 and `python-jose` imports. OV1's P22 was never verified. It is
   now.

## 5. Non-goals / out of scope

- **Hermes.** It reads `default/hermes/openviking`
  (`deployments/applications/secrets.tf:402`) and calls OpenViking with jasper's
  derived key. That key stops authenticating the moment `auth_mode` flips, so
  **Hermes breaks in this ticket and is not repaired in it**. Its `jwt-nomad`
  entity alias and the removal of `hermes_openviking_key` belong to a follow-up
  ticket (working name OV4). Say so in the docs rewrite, and do not patch Hermes
  here.
- **Deleting the seed and key apparatus.**
  `random_password.openviking_user_seed`
  (`deployments/applications/secrets.tf:254`), the `openviking_user_keys` local
  (`:311`) and the `openviking-users/` KV writes (`:361`) all stay in place, so
  the change is one revert away from working. A follow-up removes them.

  **The `openviking_users` provisioner is the exception, and it does NOT stay
  unused.** Its trigger is `jobspec = sha1(nomad_job.openviking.jobspec)`
  (`deployments/applications/services.tf:509`), and `ov_conf =
  local.openviking_ov_conf` feeds that jobspec (`:460`), so R4's config edit
  re-runs it. With `detach = false` it runs against a server already in `oidc`
  mode, where both guarded curls exit 1 and fail the apply. Neutralizing it is
  in scope here, not deferred: §7's `:502` row and §10's step 3 own the change,
  and Q1 settles which form it takes.
- **The hostname and edge collapse**, and oauth2-proxy's fate. Follow-up.
- **`ovx` and the dashboard.** No change.
- **Server-side admin under OIDC.** The OIDC plugin returns `Role.USER`
  unconditionally, so nothing in this ticket restores an admin path. See Q3.
- **A runtime gate in CI.** No repo gate exercises a deployed service and this
  ticket does not add one. See Q1.

## 6. Requirements & restrictions

**R1. Both people get a Vault identity.** Replace the singular `operator`
resources at `deployments/infrastructure/identity.tf:27`, `:36`, `:50` and `:61`
with a `for_each` over a people list, so each person has a `random_password`, a
userpass user, an entity and an alias. Entity NAME must equal the person's
OpenViking account id (`deployments/applications/secrets.tf:288` makes account
id equal user id equal person name), because R4 maps the account from the
entity-name claim. Group membership must keep what the existing tiers grant:
`developer` (`deployments/infrastructure/identity.tf:249`, member list at
`:254`) and the app-user tiers (`:410`, `:431`) currently name
`vault_identity_entity.operator.id` and must be re-pointed, not silently
narrowed. Producer for "both people exist": the file itself, listed in §7.

**R2. One `vault_identity_oidc_role` on its own dedicated key.** The operator
delegated this choice, and it is decided and justified here so the implementer
does not re-open it. Use a NEW `vault_identity_oidc_key`, not the `lab` one at
`deployments/infrastructure/oidc.tf:42`, for three cited reasons:

- The `lab` key is the OIDC provider's key ring.
  `deployments/infrastructure/oidc.tf:336` records that unpublishing that ring
  "kills every outstanding memex human token at once". Adding an identity-token
  role to it couples two unrelated revocation surfaces.
- `deployments/infrastructure/oidc.tf:28` records that `allowed_client_ids` is
  deliberately NOT inline on `lab` because the standalone
  `vault_identity_oidc_key_allowed_client_id` resource
  (`deployments/infrastructure/oidc.tf:403`) is how consumers register. The
  provider docs for v5.3.0 forbid mixing the inline list with that standalone
  resource on one key, so reusing `lab` forces the standalone form for a client
  id that is not a client.
- `memex_human` (`deployments/infrastructure/oidc.tf:345`) is the repo's own
  precedent for a second key with its own rotation period.

Set `client_id` explicitly rather than letting Vault generate one, so the
`audience` in R4 is a static literal the R5 guard can assert. Choose `ttl`
deliberately: the API default is 24h, which is longer than a short-lived token
should live when the caller can re-mint on demand. Choose the key's
`verification_ttl` no shorter than `ttl`, matching the constraint stated at
`deployments/infrastructure/oidc.tf:331` and applied to the memex client at
`:395`.

**R3. An ACL grant to read `identity/oidc/token/<role>`.** `developer` already
grants `identity/*` (`deployments/infrastructure/identity.tf:173`), verified
live: `vault token capabilities identity/oidc/token/openviking` returns
`create, delete, list, read, update` for a `developer` token. A person who is
NOT a developer has no such grant, and the app-user tiers cannot carry it:
`deployments/infrastructure/identity.tf:405` records that `policies = []` on
every tier is deliberate and that "a group that grants Vault access is a
different thing and belongs above". Which policy carries the grant is Q2; do not
settle it in the diff.

**R4. `ov.conf.json` runs `auth_mode` `"oidc"` with a `server.oidc` block.**
Under upstream v0.4.17.1 both the server config model and the OIDC config model
are `extra="forbid"`, so a misspelled key is a startup failure rather than a
silent default. The block must carry:

- `issuer` equal, byte for byte, to the `iss` claim the role's tokens carry. Q4
  decides which string that is.
- `audience` equal to the role's `client_id`. Upstream refuses to start without
  `audience` or `client_id`, and its token validation never skips audience
  verification.
- `identity.account_id` and `identity.user_id` both mapped from the entity-name
  claim, `source: "claim"`. Post-OV2 the account and the user are the same
  string per person (`deployments/applications/secrets.tf:288`).
- `identity.account_id.fallback` explicitly `null`. Upstream defaults it to
  `"default"`, and the live server HAS an account named `default` (measured,
  `user_count` 0), so a token missing the claim would silently land every caller
  in one shared account instead of being refused. This is fail-closed and is not
  optional.

- Upstream also accepts an explicit `jwks_uri`, which takes precedence over
  discovery (`openviking/server/auth/plugins/oidc.py`). That is a third
  shape Q4 does not name: leave Vault's issuer at its `api_addr` default and
  point `jwks_uri` at the edge, keeping the key fetch on TLS without a
  cluster-wide Vault write. It does not change what `issuer` must equal, since
  validation still compares `iss`.

Producer for "the config holds these values":
`scripts/check_openviking_config.py`, listed in §7.

**R5. `scripts/check_openviking_config.py` updated for the new shape.**
`EXPECTED_AUTH_MODE` (`:42`), the `auth_mode` failure text (`:129`), the
`root_api_key` assertion (`:137`), the `CLEAN` fixture (`:223`) and the
`auth_mode` mutant (`:288`, which currently uses `"oidc"` as the BAD value) all
invert. Add assertions for the four `server.oidc` fields R4 names. Decide what
happens to two existing checks and state the reason in the module docstring
(`:2`), which enumerates what each check buys:

- `root_api_key` (`:137`): under `oidc` the auth plugin never consults it. Its
  absence no longer stops the server starting. Either drop the assertion or
  restate what it now buys.
- `api_key_hashing` (`:209`): under `oidc` no per-user API key is issued or
  verified on the request path, so "the key store is a list of working
  credentials" describes a store nothing writes. Check whether the setting still
  governs anything reachable and say so. Do not leave a guard whose stated
  reason is false.

**R6. Terraform file layout.** `.claude/rules/terraform-file-layout.md`: entity,
alias, userpass and group work goes in `deployments/infrastructure/identity.tf`;
the OIDC key and role in `deployments/infrastructure/oidc.tf`; per-person
password KV writes in `deployments/infrastructure/secrets.tf`; the jobspec and
config wiring in `deployments/applications/services.tf`. **No new `.tf` file.**

**R7. Prose.** `.claude/rules/plain-language.md`,
`.claude/rules/minimal-comments.md` and `.claude/rules/slop-scan-for-docs.md`
govern every comment and the docs rewrite in R8.

**R8. Rewrite the Authentication section of `docs/openviking.md`.** The whole
section from `:24` through `:98` describes a model this ticket replaces, and the
key table at `:44` is wrong the moment `auth_mode` flips. Two claims in it are
ALREADY false at the pinned tag and must be corrected while there rather than
carried forward:

- `:79` says Web Studio "refuses to run" against `oidc` (`:80`). Upstream uses
  its unsupported-auth-mode flag in exactly one place, as one branch of a
  ternary inside the settings panel. Studio still renders, and the credential
  form is replaced. `:86` ("the entire browser half of the service does not") is
  the same error restated.
- `:88` says trusted mode makes the two people indistinguishable. Upstream's
  trusted plugin uses the root key as a GATE (a constant-time compare) and then
  takes identity from the `X-OpenViking-Account` and `X-OpenViking-User` headers
  or the URL. People stay distinguishable.

Also record in that section that Hermes is broken until its follow-up ships.

## 7. Code surface

| Path | Anchor | Change |
|---|---|---|
| `deployments/infrastructure/identity.tf` | `:27`, `:36`, `:50`, `:61` | Replace the four singular `operator` resources with `for_each` over a people list. Entity name equals the person's OpenViking account id. |
| `deployments/infrastructure/identity.tf` | `:254` | Re-point `member_entity_ids` from the singular entity to the for_each'd entities. |
| `deployments/infrastructure/identity.tf` | `:431` | Re-point `app_user_group_members` to the for_each'd entities. |
| `deployments/infrastructure/identity.tf` | after `:255` | Q2's grant: a `vault_policy` naming `identity/oidc/token/<role>` and the group carrying it, in the human-identity half of the file per `:405`. |
| `deployments/infrastructure/identity.tf` | `:1` | Header comment lists four sections. Update it if a section is added. |
| `deployments/infrastructure/oidc.tf` | after `:47` | New `vault_identity_oidc_key` for identity tokens, with inline `allowed_client_ids`, plus the `vault_identity_oidc_role` and its claims template. |
| `deployments/infrastructure/oidc.tf` | `:1` | Header comment describes the file as the provider and its clients. Extend it to name the identity-token role as a second, separate issuer. |
| `deployments/infrastructure/secrets.tf` | `:170` | `vault_operator_credentials` becomes one KV write per person. |
| `deployments/infrastructure/variables.tf` | `:67` | `vault_operator_username` and the email beside it become a people map or list. |
| `deployments/applications/services/openviking/ov.conf.json` | `:67`, `:68` | `auth_mode` to `"oidc"`; add the `server.oidc` block; decide `root_api_key`'s fate per R5. |
| `deployments/applications/services.tf` | `:422` | `openviking_ov_conf` may need a new `templatefile` variable if Q4 makes the issuer non-static. Prefer a static literal so the R5 guard can assert it, per the rule stated at `:418`. |
| `deployments/applications/services.tf` | `:468` | `openviking_root_key_secret` stays or goes with `root_api_key`. |
| `deployments/applications/services.tf` | `:502`, `:509` | `openviking_users` provisioner: Q1 decides its fate. Its `jobspec` trigger changes with `ov_conf`, so it RE-RUNS on the flip; its account-creation call is root-only upstream and 401s under `oidc` (the provisioner sends no bearer token), failing the apply. |
| `scripts/check_openviking_config.py` | `:2`, `:42`, `:129`, `:137`, `:209`, `:223`, `:288` | Invert the auth-mode expectation, add the `server.oidc` assertions, update the docstring, the `CLEAN` fixture and the mutant set. **This file is the home for every test named in §8.** |
| `cli/src/localstack_cli/commands/login.py` | `:76` | The `"operator"` default username stops resolving if R1 renames the entity. Change it or keep `operator` as a person; do not leave it dangling. |
| `deployments/infrastructure/oidc.tf` | `:141` | Third holder of `vault_identity_entity.operator.id`. Re-point with R1's `for_each`. |
| `cli/tests/commands/test_auth_commands.py` | `:252`, `:279` | Assert the `operator` username. In the DEFAULT pytest run §8 commits to keeping green, so these cannot be deferred. |
| `cli/tests/fixtures/cluster.py` | `:85` | Same `operator` assumption, same default run. |
| `cli/tests/auth/test_live_login.py` | `:43` | `operator` in a cluster-marked test, excluded from the default run. Update alongside the rest. |
| `docs/cli-login.md` | `:38`, `:44` | Names `operator` as the login username. |
| `docs/vault-human-auth.md` | `:20`, `:47` | Names `operator` as the human entity. |
| `docs/openviking.md` | `:24`-`:98`, `:200` | Rewrite per R8. |
| `.pre-commit-config.yaml` | `:91`, `:100` | The guard's `files:` pattern already covers both changed paths. Touch only if a path moves. |

**R6 has no file of its own.** It is the cross-cutting constraint on this table:
every row above lands in a `.tf` file that already exists in its root, and a
diff adding a `.tf` file is an R6 violation whatever else it does. Same for
**R7**, which governs the prose inside these files and the `docs/openviking.md`
row rather than adding a row.

Not in surface, deliberately: `deployments/applications/secrets.tf` (the seed
and key apparatus, §5), and `deployments/applications/services/openviking.hcl`
(its `template` block at `:99` binds the root-key secret, which only changes if
`root_api_key` goes. If it does, this file joins the surface and that is an
expected widening, not an `out-of-scope-fix-needed`).

## 8. Tests & validation gates

**Gate command:** `just pre_commit` (`.loop/config.json` `gates`; `justfile:18`
runs `pre-commit run --all-files`). `.pre-commit-config.yaml` is the source of
truth for which checkers run. The ones this diff trips:

- `terraform-fmt` (`.pre-commit-config.yaml:22`) and `terraform-validate`
  (`:28`, running `scripts/tf_validate.sh` over both roots).
- `openviking-config-guard` (`:91`) and its self-test (`:100`).
- `ruff`, `ruff-format` and `mypy` (`:37`, `:46`, `:52`). All three include
  `scripts/`, and mypy runs strict, so the guard's new code is type-checked.
- `check-json` (`:6`) parses `ov.conf.json`.
- `pytest` (`:106`) runs `cli/tests` and fires on any `cli/` change, so the
  `login.py:76` edit must keep the suite green.

**Tests to add**, all in `scripts/check_openviking_config.py` (§7). `scripts/`
holds no pytest project (`.pre-commit-config.yaml:68` says so), so the script's
own `--self-test` is the test mechanism and each item below is a new mutant in
`_self_test` (`:268`) plus its assertion in `failures` (`:94`):

1. `EXPECTED_AUTH_MODE` inverted: `CLEAN` (`:223`) carries `"oidc"` and the
   `auth_mode` mutant (`:288`) carries `"api_key"` as the value that must be
   caught. This is the reproducing case for the guard that would otherwise pass
   the old config unchanged.
2. A mutant deleting `server.oidc` entirely. Upstream exits the process on that,
   so the guard must catch it statically.
3. A mutant changing `server.oidc.issuer` to a value other than the one Q4
   settles. A wrong issuer is accepted at startup and fails every request with
   an invalid-claims error, which is the silent failure this check exists for.
4. A mutant changing `server.oidc.audience` away from the role's `client_id`.
5. A mutant pointing the account or user claim at `sub`. Measured: `sub` is the
   entity UUID, so this yields one account per UUID and looks healthy.
6. A mutant setting the account mapping's `fallback` to `"default"` or removing
   it. Measured: `default` is a real account on the live server, so this
   silently pools every unmapped caller into it.
7. Whatever replaces the `root_api_key` (`:137`) and `api_key_hashing` (`:209`)
   assertions per R5 keeps a mutant each, or loses its mutant in the same commit
   that loses the assertion.

**Runtime validation is NOT a gate.** The guard's own docstring (`:25`) states
it "does not measure whether the service accepts a key". Nothing in this repo
runs a deployed service. Q1 is the fork for that.

**R6 and R7 are checked by eye, not by a hook.** No gate in
`.pre-commit-config.yaml` counts `.tf` files or reads prose, so R6 (no new `.tf`
file) and R7 (plain language, minimal comments, the slop scan) are the
reviewer's to confirm against the §7 table and the diff.

**Terraform proof of the identity rewrite.** R1 restructures existing resources
into a `for_each`, which is a state move, not a text move, so
`.claude/rules/terraform-file-layout.md`'s `scripts/tf_block_diff.py` does not
apply. Run `terraform plan` against `deployments/infrastructure` and account for
every destroy it lists: renaming an entity destroys and recreates it, taking its
id with it, and every group referencing that id must move in the same apply.

## 9. Risk assessment

**Blast radius: the cluster's human identity, wider than OpenViking.** R1
rewrites the resources every human login flows through. A botched `for_each`
locks both people out of Vault, and the recovery path is the root token plus an
unseal.

**Likeliest failure modes, worst first:**

1. **Entity recreate orphans group membership.** Changing an entity's Terraform
   address or name destroys and recreates it with a new UUID.
   `deployments/infrastructure/identity.tf:254`, `:431` and the OIDC assignments
   hold that UUID. If any reference is missed, the apply succeeds and the person
   silently loses a tier. `deployments/infrastructure/identity.tf:383` also
   warns that `admin` uses `external_member_entity_ids = true`, so hand-added
   membership there is invisible to `plan` and is lost on a recreate with no
   diff to show it.
2. **Issuer mismatch.** OpenViking compares `iss` exactly. A trailing slash, or
   the edge hostname when the token carries the raw IP, produces a healthy
   startup and a 401 on every call.
3. **Hermes 401s.** Expected and stated in §5, but it will look like a
   regression to anyone reading alerts.
4. **The provisioner 403s the apply.** `openviking_users`
   (`deployments/applications/services.tf:502`) posts to a root-only route.
   Under `oidc` the plugin resolves `Role.USER` for every caller, so that call
   fails and takes the apply with it. Q1.
5. **Silent pooling into `default`.** If R4's `fallback: null` is dropped, every
   caller whose token lacks the claim lands in one shared account with a 200.
6. **The person's own login breaks.** `login.py:76` defaults to `operator`. If
   R1 renames that entity and the CLI is not updated, `localstack login` fails
   for the operator who is mid-change.

**Reversibility: good, deliberately.** §5 keeps the entire seed and key
apparatus in place. Reverting is `auth_mode` back to `"api_key"` plus the guard,
and the derived keys still work because nothing deleted them. The one
irreversible part is an entity UUID change, which no revert restores.

## 10. Subtickets

Ordered. If these become separate plan files, encode the order in each file's
`depends_on` front matter.

1. **Human identity for both people.** R1 alone: the `for_each` rewrite, the
   per-person KV writes, the group re-pointing, and the `login.py` default.
   Lands with `terraform plan` accounted for and both people able to
   `localstack login`. Touches no OpenViking config, so it is independently
   revertible.
2. **The identity-token role.** R2 and R3: the dedicated key, the role, the
   claims template, the ACL grant. Verified by minting a token as each person
   and decoding its claims. OpenViking is untouched and still on `api_key`.
3. **The flip.** R4 and R5 together: `ov.conf.json`, the guard, and whichever
   provisioning answer Q1 settles. This is the step Hermes breaks on.
4. **The docs.** R8, under R7's prose rules. Separable only after step 3 lands,
   because it describes the result.

R6 binds every step: none of them adds a `.tf` file.

## 11. Open questions

### Q1. Nothing in the repo can measure that the chain works `unmeasurable-requirement`

The ticket's own headline requirement is that a live Vault identity token is
accepted by the deployed service and resolves to the right account. That demands
an OBSERVABLE (an HTTP status from a running service), and **no producer for it
exists in the declared code surface or anywhere in the repo**. The one guard
that touches this config says so itself at
`scripts/check_openviking_config.py:25`. OV1 hit the same wall and settled it
with a labelled proxy (ledger `premise.Q7`).

Compounding it: the OIDC plugin performs no account lookup and creates nothing
(P8), so whether a read or a write SUCCEEDS for an `account_id` whose tree was
never initialized is genuinely unknown, and it decides whether any provisioning
is needed at all. It cannot be probed today (P10): the api-key path always
verifies existence, root is refused on data routes, and the OIDC path only
exists once this ticket flips the mode.

**The probe that settles it**, to run at implementation time after the flip,
from a host that reaches the API. Probe BOTH directions:

```
# grant: an account that exists
TOK=$(vault read -field=token identity/oidc/token/<role>)
curl -sS -o /dev/null -w 'existing-account: %{http_code}\n' \
  -H "Authorization: Bearer $TOK" \
  https://openviking-api.lab.orangecluster.nl/api/v1/stats/memories

# denial: an entity whose name matches no OpenViking account.
# Create a scratch entity and alias, mint against it, read the status,
# then delete both in the same run and read the deletion back.
```

Options, in the order the contract requires:

- **`widen-surface`.** Add a runtime harness to §7 (a script beside
  `scripts/bifrost_smoke.py`, the repo's precedent for probing a deployed
  service) that mints a token and asserts the two statuses. Makes the headline
  requirement measurable and revises §2 upward.
- **`split-ticket`.** Move the runtime proof to its own plan file with
  `depends_on = ["OV3-openviking-vault-identity"]`.
- **`drop-requirement`.** Cut "prove the chain works" from §6 and record in §5
  that runtime verification is out of scope. Ships an unverified auth flip.
- **`declared-proxy`.** Keep the requirement and score it with the static guard,
  explicitly LABELLED, with the eval row's Expected cell stating that the proxy
  does NOT measure whether a live token is accepted, whether a foreign audience
  is refused, or whether an uninitialized account tree is writable.

**Recommendation: `widen-surface`.** OV1 took `declared-proxy` and the result is
that OV3 inherited an unverified premise (its P22, which turned out to hold but
went two tickets unchecked). The runtime half is small here: one script, one
mint, two asserts, and it doubles as the answer to the provisioning question. If
the operator prefers the smaller diff, `split-ticket` is the second choice;
`declared-proxy` third.

**If the probe shows an uninitialized tree fails**, provisioning becomes a live
problem and the sub-options are:

- **(a) Pre-create out of band.** Keep `openviking_users`
  (`deployments/applications/services.tf:502`) but run it while briefly in
  `api_key` mode, or move its account-creation calls to a documented hand step.
  Simplest; leaves an ordering trap for any future person.
- **(b) A chained auth plugin.** Accept either a Vault JWT or the root key.
  Upstream has no chaining (OV1 P8: exactly one plugin, no fallback), so this
  means carrying a patch in the derived image. Expensive, and the repo then owns
  a fork of an auth path.
- **(c) Drop server-side admin.** Accept that accounts are created by hand and
  never by Terraform. Honest, and consistent with Q3 below.

Recommendation among those: **(a)**, since accounts are created once per person
and the seed apparatus (§5) is still in place to do it with.

### Q2. Which policy carries the `identity/oidc/token/<role>` grant

`developer` already grants it via `identity/*`
(`deployments/infrastructure/identity.tf:173`, verified with
`vault token capabilities`). A non-developer has nothing. Options: put both
people in `developer`; add a narrow `vault_policy` on a new group holding
everyone; or attach a policy to each entity directly.

**Recommendation: a narrow policy on a new group.**
`deployments/infrastructure/identity.tf:76` records that `developer` "is NOT a
containment boundary" and can reach root in three commands, so making a second
person a developer to let them read one path is a large grant for a small need.
`deployments/infrastructure/identity.tf:405` already says a group that grants
Vault access belongs in the upper half of the file, which is where this goes. A
group beats per-entity policies because it survives an entity recreate.

### Q3. Under OIDC there is no admin path at all, and that is permanent

Upstream returns `ResolvedIdentity(role=Role.USER, ...)` unconditionally and
never calls its role mapper, even though a role-mapping config exists and is
parsed. The source comment says operators needing admin "should use the root API
key mechanism", which does not work here: the root key is not consulted under
`oidc`, and account creation is decorated root-only (P9).

What is lost, concretely: every person stops being ADMIN of their own account.
`docs/openviking.md:44` currently promises "everything in their own account".
Account settings, user settings, key regeneration and user management all move
out of reach for everyone, including the operator. Account creation and deletion
become root-only operations with no root.

**Recommendation: accept and document it.** This is upstream's design, not a
configuration mistake, and OV2's ledger `premise.Q2` already recorded that
per-account ADMIN "grants nothing over any other account", so the capability
being lost is small. Say plainly in `docs/openviking.md` what is no longer
possible and that account lifecycle becomes a hand step. If the operator wants
ADMIN back, that is a patched image and belongs in its own ticket.

### Q4. Which issuer string, and whether to set `identity/oidc/config`

Measured (P2): `identity/oidc/config` has no issuer, so `iss` is
`http://192.168.2.30:8200/v1/identity/oidc`. The discovery document served at
the edge hostname reports that same raw-IP issuer. OpenViking verifies `iss`
exactly, so the two options are:

- **(a) Leave it unset**, and configure OpenViking with
  `http://192.168.2.30:8200/v1/identity/oidc`. Zero Vault-wide change. The JWKS
  fetch is plaintext HTTP over the LAN, and the issuer hardcodes a backend IP
  that `deployments/infrastructure/variables.tf:62` explicitly says the edge
  hostname exists to avoid.
- **(b) Add a `vault_identity_oidc` resource** setting the issuer to the edge
  base URL, and configure OpenViking with
  `https://vault.lab.orangecluster.nl/v1/identity/oidc`. HashiCorp's API docs
  state the issuer is a base URL and that setting it to `""` restores the
  default, so it is reversible. The named OIDC providers are unaffected: their
  issuer comes from `issuer_host` and is measured to be a different string
  already (P3). Nothing consumes identity tokens today (P4), so nothing can
  break.

**Recommendation: (b).** It matches
`deployments/infrastructure/variables.tf:62`'s stated reason for using the edge
hostname, keeps the JWKS fetch on TLS, and survives a backend IP change. Both
routes are measured reachable from inside the container (P5). Cost: one
cluster-wide Vault setting Terraform now owns. **Not settled here** because that
write is cluster-wide and a probe of it was refused in this session, so option
(b)'s exact resulting `iss` string is documented (P14), not measured. Verify it
at implementation time before writing the string into `ov.conf.json`, by minting
one token and decoding `iss`.

### Q5. Does `operator` survive as a person

R1 makes entity names equal OpenViking account ids, which are `jasper` and
`veerle`. The `operator` entity, its userpass user, its KV password path
(`deployments/infrastructure/secrets.tf:170`) and the CLI default
(`login.py:76`) all name `operator`. Options: rename `operator` to `jasper` and
drop the name; keep `operator` as a third identity alongside; or keep `operator`
and decouple the OpenViking account from the entity name with an entity-metadata
claim.

**Recommendation: rename.** R1's for_each is exactly the shape
`deployments/infrastructure/identity.tf:73` anticipated, and carrying a third
identity that is really the same person doubles the login surface. Cost: one
entity recreate (see §9 risk 1) and one CLI default change. The decoupling
option is worth naming because it avoids the recreate entirely, at the price of
a second source of truth for who someone is, which is the thing this ticket is
trying to remove.

### Q6. Does the CLI learn to mint the token

The goal statement says the CLI mints a short-lived token per call, but no
requirement names it and no non-goal excludes it.
`cli/src/localstack_cli/commands/token.py` is the natural home: it already
prints exactly one token to stdout for `vault`, `nomad` and `consul`, and
`cli/src/localstack_cli/auth/vault.py:117` and `:142` are the working precedent
for a renewable session.

**Recommendation: out of scope for this ticket, and say so in §5 at settlement
time.** `vault read -field=token identity/oidc/token/<role>` proves the chain
without any CLI change, and adding a fourth service to that command pulls in the
session cache, its tests and `cli/tests`, which is a subticket's worth of work
on its own. If the operator wants it here, it is subticket 2b and §2 goes up.

## Premises / assumptions

**P1.** Vault identity tokens carry the entity NAME only if a template emits it;
`sub` is the entity UUID. MEASURED. A scratch key and role were created, one
token minted and decoded, then both deleted and the deletion read back:

```
CLAIMS: {"aud": "ovprobe-client", "email": "jasperginn@gmail.com",
         "exp": 1788727853, "groups": ["app-memex-admins","developer","oidc-smoke"],
         "iat": 1788727253, "iss": "http://192.168.2.30:8200/v1/identity/oidc",
         "name": "operator", "namespace": "root",
         "sub": "351f302a-ada1-0e79-15d3-e22a4be2e3e4"}
```

Template used:
`{"name": {{identity.entity.name}}, "groups": {{identity.entity.groups.names}}, "email": {{identity.entity.metadata.email}}}`.
Unquoted placeholders, matching the warning at
`deployments/infrastructure/oidc.tf:79`. Cleanup verified by read-back: "No
value found at identity/oidc/role/ovprobe".

**P2.** The identity-token issuer is Vault's `api_addr`, not the edge hostname.
MEASURED. `vault read identity/oidc/config` returns `issuer  n/a`, and
`GET https://vault.lab.orangecluster.nl/v1/identity/oidc/.well-known/openid-configuration`
returns `{"issuer":"http://192.168.2.30:8200/v1/identity/oidc", ...}`. This is
the raw IP even when fetched through the edge.

**P3.** The identity-token issuer is independent of the named OIDC providers.
MEASURED.
`GET .../v1/identity/oidc/provider/lab/.well-known/openid-configuration` returns
`issuer: https://vault.lab.orangecluster.nl/v1/identity/oidc/provider/lab`. The
reason it cannot move is not that the strings differ today: a named provider
reads its OWN `Issuer` field and falls back to `redirectAddr`, never consulting
`identity/oidc/config` (`vault/identity_store_oidc_provider.go`, v1.18.3).
This is what makes Q4 option (b) safe for the browser flow that
`deployments/infrastructure/oidc.tf:118` serves.

**P4.** No identity-token role exists anywhere, in the repo or live. MEASURED.
`vault list identity/oidc/role` returns "No value found at identity/oidc/role";
`grep -rn vault_identity_oidc_role deployments/` finds nothing. Existing keys
are `default`, `lab`, `memex-human`, matching
`deployments/infrastructure/oidc.tf:42` and `:345`.

**P5.** The OpenViking container can reach Vault's issuer, discovery and JWKS at
request time, and has the JWT libraries. MEASURED from inside the running
container on the OpenViking host:

```
$ sudo podman exec <openviking> python -c '...'
discovery 200 http://192.168.2.30:8200/v1/identity/oidc
jwks 200 3 keys
python-jose importable
```

The edge route also works from inside the container (`edge https: 200`), so TLS
trust is present. This settles OV1's P22, which was recorded unverified.
`deployments/applications/services/openviking.hcl:70` sets `network_mode` to
host, which is why host reachability and container reachability are the same
question.

**P6.** A `developer` token can already read `identity/oidc/token/<role>`.
MEASURED. `vault token capabilities identity/oidc/token/openviking` returns
`create, delete, list, read, update` for a token whose `identity_policies` is
`['developer']`, matching the `identity/*` grant at
`deployments/infrastructure/identity.tf:173`.

**P7.** The account `default` exists on the live server with zero users.
MEASURED. Evidence:
`GET https://openviking-api.lab.orangecluster.nl/api/v1/admin/accounts` with the
root key returns accounts `default` (`user_count` 0), `jasper` (1), `lab` (3),
`veerle` (1). This is what makes upstream's default account `fallback` of
`"default"` a live hazard rather than a theoretical one, and it is why R4
requires `fallback: null`.

**P8.** The OIDC plugin performs no account lookup, creates nothing, and always
resolves `Role.USER`. Source: upstream at the pinned tag, read with
`gh api "repos/volcengine/OpenViking/contents/openviking/server/auth/plugins/oidc.py?ref=v0.4.17.1" --jq '.content' | base64 -d`.
Its `resolve_identity` maps the account and user ids, sanitizes both against a
character allowlist, and returns `ResolvedIdentity(role=Role.USER, ...)`
unconditionally; the role mapper is never called. Confirmed downstream in
`openviking/server/auth/__init__.py`, whose request-context builder takes the
resolved identity with no existence check.

**P9.** Account creation is root-only and therefore unreachable under `oidc`.
Read at the pinned tag in `openviking/server/routers/admin.py`: the
`POST /accounts` route carries a root-only decorator. Combined with P8 this is
why `openviking_users` (`deployments/applications/services.tf:502`) stops
working.

**P10.** A root key cannot stand in for a user on data routes against the LIVE
server, so the uninitialized-tree question cannot be probed there without
changing `auth_mode`. It CAN be probed before the flip, off the live server.
MEASURED. Evidence:
`GET https://openviking-api.lab.orangecluster.nl/api/v1/stats/memories` with the
root key returns HTTP 403, `PERMISSION_DENIED`, "ROOT API keys cannot access
tenant-scoped data APIs in api_key mode." The api-key path is also closed:
upstream's key resolver returns an identity only when the account is in its
account map and the user is in that account.

That denial names its own way out: "Use a user/admin API key for data access, or
trusted mode for upstream identity assertion"
(`openviking/server/auth/plugins/api_key.py`).
`openviking/server/auth/plugins/trusted.py` gates
on a constant-time compare against `root_api_key` and then takes the account and
user from headers with NO existence check, so a local run of the pinned image in
`trusted` mode asserts an account that was never created. That is Q1's probe,
and it needs no change to the deployed service.

**P11.** Under `api_key` mode the `X-OpenViking-Account` and `X-OpenViking-User`
headers are stripped, not honored. Source: upstream at the pinned tag,
`openviking/server/auth/plugins/api_key.py`, which removes both headers with the
comment "Silently ignore identity assertion headers in api_key mode". Recorded
because it falsifies an obvious-looking impersonation probe.

**P12.** The OIDC config model, the three identity-mapping models and the server
config model are all `extra="forbid"` at the pinned tag; the account mapping's
`fallback` defaults to `"default"` while the user mapping's defaults to `None`.
Source: upstream at the pinned tag, `openviking/server/auth/oidc_config.py`,
`openviking/server/auth/identity_mapping.py` and `openviking/server/config.py`.
The mapper applies `fallback` when the claim is absent and raises only when the
result is still `None`, which the plugin converts to an authentication failure.

**P13.** `vault_identity_oidc_role` exists in the pinned provider and takes
`name`, `key`, `template`, `ttl` and `client_id`; `vault_identity_oidc` sets the
`identity/oidc/config` issuer. Source: the provider's own docs at tag `v5.3.0`,
matching the version in `deployments/infrastructure/.terraform.lock.hcl`, and
both resource names are present in the installed provider binary. The same docs
carry the note that an inline `allowed_client_ids` list cannot be combined with
the standalone `vault_identity_oidc_key_allowed_client_id` resource, which is
R2's third reason.

**P14.** Vault's role `ttl` defaults to 24h and `client_id` is generated when
unset; the `identity/oidc/config` issuer is a base URL and `""` restores the
`api_addr` default. Source: HashiCorp's `api-docs/secret/identity/tokens.mdx`,
and DEMONSTRATED in Vault's own source: `getOIDCConfig` appends `"/v1/" +
ns.Path + issuerPath` to the configured issuer after falling back to
`redirectAddr` (`vault/identity_store_oidc.go`, v1.18.3). So the issuer written
to `identity/oidc/config` must carry NO path — Vault rejects one with "must
include only a scheme, host, and optional port" — and writing
`https://vault.lab.orangecluster.nl` yields the effective issuer
`https://vault.lab.orangecluster.nl/v1/identity/oidc`, byte for byte what R4
puts in `ov.conf.json`. Q4 stays a fork because the write was refused in this
session, not because its effect is uncertain.

**P15. UNCERTAIN.** Whether a read or a write succeeds for an `account_id` whose
directory tree was never initialized. P8 shows nothing checks. Upstream's
account creation writes an accounts index and the account's users file and
nothing else, which suggests the data tree is created lazily on write, but that
is inference from reading and is exactly the kind of claim this section refuses
to assert. P10 gives the probe: a local run of the pinned image in `trusted`
mode, which asserts an arbitrary account with no existence check, before the
flip and against no deployed service. Q1 carries it.

**P16. UNCERTAIN.** Whether `encryption.api_key_hashing`
(`deployments/applications/services/openviking/ov.conf.json:60`) still governs
anything reachable under `oidc`. The guard at
`scripts/check_openviking_config.py:209` justifies itself with "the server
stores every key verbatim, so its key store is a list of working credentials",
and under `oidc` no key is minted or verified on the request path. R5 requires
this be checked rather than carried forward unexamined.

**P17.** The `veerle` string has exactly one home under `deployments/`.
MEASURED: `grep -rn veerle deployments/` returns only
`deployments/applications/secrets.tf:283`. R1 therefore adds an identity rather
than reconciling two.
