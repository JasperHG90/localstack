# Two-factor auth on Vault logins

Handoff, updated 2026-09-12. Ready to apply, mount-wide. The enrollment
tooling is built and tested, `localstack login` speaks Login MFA, and the
Terraform is in `deployments/infrastructure/identity.tf`. What is left is to
apply it in the order below, because enforcing before a person holds a secret
locks that account out of userpass.

ov-dash was the one service an enforced mount would have broken. It now signs
people in at Vault's own page rather than through a password form of its own,
so the factor is asked where Vault asks it and the dashboard never sees a
password. The `jwt-lab` section of `identity.tf` carries the mechanism.

## Why the Vault login is the place to do it

Vault is the OIDC provider for humans here, so a person reaches an app by
completing a Vault login first. Six clients are registered with the `lab`
provider (`deployments/infrastructure/oidc.tf`): the smoke client, nomad,
memex, oauth2-proxy (which fronts dash), grafana and ov-dash. A second factor
on the Vault login therefore reaches all six without touching any of them.

## Why the enforcement names the mount

`auth_method_accessors = [vault_auth_backend.userpass.accessor]` covers every
human login that carries a password, including the one Vault runs behind its
own OIDC provider page. The factor is asked once per Vault session, and every
app behind SSO inherits it.

It also covers anything that posts a username and password straight at
`auth/userpass/login/*`. There were two of those, and both are settled.

**`localstack login`** raised unless the reply carried `auth.client_token`, and
Vault answers an enforced mount with HTTP 200, an `auth` block whose
`client_token` is empty, and the challenge at `auth.mfa_requirement`. The CLI
reported that as "returned no token. Check the username", which sends the
reader looking for a typo that is not there. It now raises `MFARequired`,
prompts for the passcode, and finishes at `sys/mfa/validate`. This mattered
more than it looked: all three `mfa_*` recipes open with
`eval "$(localstack env)"`, so an unfixed CLI would have stranded the operator
with no way to reach `just mfa_reset` once a session lapsed.

**ov-dash** posted at the same mount under `AUTH_MODE=vault-userpass`, and it
cannot answer a challenge: there is no MFA code in the image, so an enforced
login fails with "Vault accepted the login but returned no token". It no longer
posts there. Under `AUTH_MODE=vault-oidc` a person signs in at Vault's page,
ov-dash trades the ID token it gets back for a Vault token on the `jwt-lab`
mount, and mints the OpenViking token as them. No password reaches the
dashboard, and nothing challenges it.

**The enforcement must not reach `jwt-lab`.** That trade is a login too, and
ov-dash can no more answer a challenge there than at the password form. Naming
the userpass accessor keeps it out. Naming an entity would not: Vault matches
an enforcement wherever that entity authenticates, mount included, so
`identity_entity_ids = [operator]`, which is what this was, challenges the
trade and strands the operator at the first hop while sparing everyone outside
the list. The scoping is not a widening of the old one for its own sake. It is
the shape the chain requires.

## What was decided, and why

**Vault generates the QR, one person at a time.** The alternative was
`enable_self_enrollment`, which makes Vault hand the QR back during the blocked
login. Vault 2.0.3 supports the flag. No Terraform provider exposes it: absent
from the pinned 5.3.0 and from the current 5.11.0, both checked on 2026-09-11.
Setting it would take a `vault_generic_endpoint` write restating the method's
whole config, because a POST to the method path resets every unsent field to
its default. For two people, enrolling once costs less than carrying that
workaround. Self-enrollment also lets anyone holding a password bind their own
authenticator, so it guards a password stolen after enrollment and not before.

**No enrollment app on dash.** dash sits behind oauth2-proxy, which
authenticates against the `lab` provider, so reaching dash requires a completed
Vault login. Once enforcement is on, an unenrolled person cannot complete that
login and so never reaches dash. Every app behind SSO has this shape, and the
only people who could use such an app are the ones who do not need it.
Enrollment has to happen at the one moment an unenrolled user is talking to
Vault, which is the login Vault is refusing. Vault's own UI at
`vault.lab.orangecluster.nl` is the GUI for everything after that.

**The enforcement names the mount accessor, not the mount type.** Vault matches
an enforcement's targets as a union, so every target added widens what is
enforced. Naming `vault_auth_backend.userpass.accessor` keeps `jwt-nomad`
outside it, and workload identity is unaffected.

## The Terraform

Two resources for the factor itself, in
`deployments/infrastructure/identity.tf` beside `vault_auth_backend.userpass`,
because human auth backends live in that file: `vault_identity_mfa_totp.lab`
and `vault_identity_mfa_login_enforcement.userpass`. The comment above the
second records why it names the accessor rather than an entity.

The ov-dash chain is what lets the enforcement name the mount at all, and it is
four more places:

| Where | What |
|---|---|
| `identity.tf`, `jwt-lab` section | the `jwt` mount, the `ov-dash` role, and one entity alias per person |
| `oidc.tf`, ov-dash section | the `openviking` scope, the assignment, the client, and its key registration |
| `secrets.tf` | the client id and secret, published to `default/ov-dash/oidc` |
| `applications/services.tf` and `services/ov-dash.hcl` | `AUTH_MODE=vault-oidc`, the issuer, the mount and role names, and the templates that read the client credentials |

None of it has been applied. `terraform validate` and `terraform fmt` pass.
`terraform plan` runs from the devcontainer once `eval "$(localstack env)"` has
put a live token in the environment; an earlier note here said the Consul token
lacked `key:read` on `terraform/infrastructure`, and that is no longer true.

## Rollout order

Five steps, and the order is the whole point: the enforcement lands last,
because it is the only step that can lock somebody out, and the ov-dash chain
lands before the dashboard that depends on it.

Every apply below is targeted. Both roots carry unrelated pending work, and an
untargeted apply on the infrastructure root restarts MinIO while one on the
applications root re-registers OpenViking. Check `git status` first and know
what else is in the tree.

**1. The TOTP method, on its own.**

```sh
cd deployments/infrastructure
eval "$(localstack env)"
terraform apply -var-file=./vars/prod.tfvars \
  -target=vault_identity_mfa_totp.lab
```

**2. Enroll everyone who logs in at userpass.** Scan each QR and confirm a code
works before going further. The enforcement is mount-wide, so an unenrolled
account cannot complete a login at all. `just mfa_status` lists who it covers.

```sh
just mfa_enroll operator
just mfa_enroll veerle
```

**3. The ov-dash chain, in one apply.** The mount, the role and the aliases go
together: a login that arrives before its alias invents an entity and an alias
of its own, and the next apply then fails on "already exists".

```sh
terraform apply -var-file=./vars/prod.tfvars \
  -target=vault_identity_oidc_scope.openviking \
  -target=vault_identity_oidc_assignment.ov_dash \
  -target=vault_identity_oidc_client.ov_dash \
  -target=vault_identity_oidc_key_allowed_client_id.ov_dash \
  -target=vault_identity_oidc_provider.lab \
  -target=vault_kv_secret_v2.ov_dash_oidc_client \
  -target=vault_jwt_auth_backend.lab \
  -target=vault_jwt_auth_backend_role.ov_dash \
  -target=vault_identity_entity_alias.ov_dash_operator \
  -target=vault_identity_entity_alias.ov_dash_consumer
```

The provider is in that list because it gates on `allowed_client_ids` and
`scopes_supported`, and the new client and scope have to reach both.

**4. The dashboard.** Move `ov_dash_image` in
`deployments/applications/services.tf` to a release that carries the jwt trade,
then apply that one job. Applying it on an older image leaves a dashboard
nobody can sign in to, because `AUTH_MODE=vault-oidc` is already set in the
jobspec.

```sh
cd ../applications
terraform apply -var-file=./vars/prod.tfvars -target=nomad_job.ov_dash
```

Sign in through the provider page and read `/api/session`. Three hops can fail
and only the first announces itself: the authorize request, the trade on
`jwt-lab`, and the mint.

Then leave the tab for eleven minutes and reload. The session should still be
good: `id_token_ttl` is ten minutes and the ID token is spent at the callback,
so a session that dies with it means ov-dash holds the wrong token, and the
client's TTL has to rise to SESSION_TTL_SECONDS with the exposure that carries
(see "What this does not cover").

**5. The enforcement, last and alone.**

```sh
cd ../infrastructure
terraform apply -var-file=./vars/prod.tfvars \
  -target=vault_identity_mfa_login_enforcement.userpass
```

Verify with `localstack login`, which should ask for the password and then a
TOTP passcode, and with a second ov-dash sign-in, which should ask for both at
Vault's page and nothing at the dashboard. If the rollout goes wrong, the root
token still logs in and can delete
`identity/mfa/login-enforcement/userpass-totp`.

## Turning it off

**Delete the enforcement, not the method.** The enforcement is the only thing
that makes Vault ask. Removing it stops every challenge at once, and it takes
effect on the next login, because enforcement is read per login rather than
baked into a token.

The method and the per-person secrets survive that, which is the point: turning
MFA back on later is one apply, and nobody rescans a QR code.

Through Terraform, which leaves no drift:

```sh
# Delete the vault_identity_mfa_login_enforcement.userpass block, then:
cd deployments/infrastructure
eval "$(localstack env)"
terraform apply -var-file=./vars/prod.tfvars \
  -target=vault_identity_mfa_login_enforcement.userpass
```

Targeted, like every apply in the rollout above. This is the recipe somebody
runs under pressure, and an untargeted apply here also restarts MinIO.

In a hurry, at the cost of drift the next apply silently reverts:

```sh
vault delete identity/mfa/login-enforcement/userpass-totp
```

Confirm either way with `just mfa_status`, which should report `(none)` under
login enforcements.

### If you cannot log in to do it

A lost phone with no live session is the case this has to survive. The root
token bypasses Login MFA, because it is token auth rather than a userpass
login, so the break-glass path already documented still works: SSH to firebat
and read `/opt/vault/init.json`, or run `localstack breakglass` for the
runbook. Then run the `vault delete` above with that token.

`docs/breakglass.md` is the long form. Nothing about MFA changes it.

### Removing it completely

Order matters, and getting it backwards is a lockout. **Delete the enforcement
first, then the method.** An enforcement naming a method that no longer exists
has no way to be satisfied, so logins fail closed with no route back except the
root token. There is no reason to find out exactly how that presents.

```sh
# enforcement first
vault delete identity/mfa/login-enforcement/userpass-totp
# then the method, which drops every enrolled secret with it
vault delete identity/mfa/method/totp/<method-id>
```

`just mfa_status` prints the method id. Doing this in Terraform instead, by
deleting both blocks in one apply, is safer: Terraform destroys the enforcement
before the method it depends on.

## Running it

| Command | Does |
| --- | --- |
| `just mfa_status` | Shows the method, the enforcements, and who logs in through userpass |
| `just mfa_enroll <username>` | Writes that person's QR to `tmp/`, then asks for a code to confirm the scan. Refuses if they already have a secret |
| `just mfa_reset <username>` | Destroys the old secret and issues a new QR. For a lost phone |

All three call `scripts/vault_mfa.sh`, which holds the traps in comments. The
QR lands in `tmp/`, which the repo gitignores. It carries the seed in full, so
it stays a secret until it is scanned and deleted.

Terraform owns the method and the enforcement. The script owns only the
per-person secret, and Terraform must never hold that: the secret is the second
factor, so putting it in state files both factors in one place.

## What a second factor on the Vault login actually reaches

Covered, because they redirect to the `lab` provider and the prompt happens at
Vault: nomad, memex, dash, registry-ui (it reuses the `oauth2_proxy` client),
Grafana's Vault sign-in button and ov-dash. The factor is asked once per VAULT
session, not once per app, so every SSO redirect after that sails through on
the browser's existing Vault session.

Three surfaces never touch that login path, so no enforcement here reaches
them:

| Surface | Credential | Why it is missed |
| --- | --- | --- |
| Grafana | `GF_SECURITY_ADMIN_USER = "admin"` plus a KV password | The local login form is not disabled; `GF_AUTH_DISABLE_LOGIN_FORM` appears nowhere in `grafana.hcl` |
| MinIO console | `MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` | Its six `IDENTITY_OPENID_*` settings point at Nomad's provider for workload identity. There is no human OIDC on MinIO at all |
| Vault | the root token | Token auth, not userpass |

Neither password is reachable without an MFA-protected Vault login today,
because both live in KV. They are still standing shared credentials, so one
leak is a permanent bypass that a second factor cannot take back. Closing them
is separate work: disable Grafana's login form, and give MinIO a human OIDC
client on the `lab` provider.

### ov-dash is covered, and not by answering a challenge

ov-dash sends people to Vault's provider page, so the factor is asked there and
the dashboard never handles one. The ID token it gets back is traded for a
Vault token on `jwt-lab`, the mount the enforcement deliberately leaves out.

Two things to check after the apply. That the deployed release carries the
trade: `ov_dash_image` in `deployments/applications/services.tf`. And that each
person has an alias on `jwt-lab`. Without the alias Vault invents a fresh
entity for the login rather than refusing it, and that entity is in no group,
so its token holds `default` alone and the mint answers 403. It fails closed,
but the error to look for is Vault's permission denied at the mint, not
anything ov-dash says about claims.

## What this does not cover

- **Only the userpass mount is enforced.** Every human who logs in with a
  password is covered, and that is everyone today.
- **The ID token is a no-factor bearer credential while it lives.** Anyone
  holding one for the ov-dash client can trade it on `jwt-lab` without a
  password, a client secret or a passcode, and for the operator the token that
  comes back carries `developer`, which reaches root in a few commands. Vault
  only issues such a token to a login that already met the factor, so the
  window is the ID token's TTL and nothing else: `id_token_ttl = 600` on the
  client in `oidc.tf` is that window, kept to ten minutes for this reason.
- **The root token bypasses it.** That is a token-auth login, not a userpass
  one. Terraform applies keep working and break-glass stays open, which is also
  the hole: this is only as strong as control of that token.
- **Tokens already issued stay valid.** MFA is checked at login. Step-up MFA on
  individual requests is an Enterprise feature.
- **A `developer` can delete the enforcement.** That policy grants `identity/*`,
  so turning this off is one command. Same non-boundary `docs/cluster-roles.md`
  records for the group. This raises the cost of a stolen password, not of a
  developer acting in bad faith.
- **Nothing records an enrollment or a reset.** No audit device is enabled on
  this cluster, so a `mfa_reset` leaves no trace. That is the weakest point in
  the scheme, because a reset is a full second-factor replacement.
- **`mfa_reset` leaves a gap with no second factor.** It destroys the old
  secret before minting the new one, so a failure in between leaves the entity
  unenrolled. Re-running it recovers, but only while you still hold a Vault
  token.

## Traps measured while building this

All measured against Vault 2.0.3 on 2026-09-11.

**`admin-generate` on an already-enrolled entity exits 0 and returns
`data: null`**, with `Entity already has a secret for MFA method ""` in
`warnings`. Piping that to `base64 -d` writes a 0-byte PNG and reports success.
`scripts/vault_mfa.sh` checks for the null, and `just mfa_enroll` refuses and
points at `mfa_reset`.

**Nothing lists who is enrolled.** Reading an entity returns the same keys
before and after enrollment, and there is no MFA field. Re-enrollment is the
only way to find out, and it fails closed with the warning above.

**The authenticator label is the entity id, not the username.** Vault builds
the `otpauth://` URL as `issuer:entity_id`, so an app shows
`vault.lab.orangecluster.nl (<entity-id>)`. Rename it by hand after scanning.
`just mfa_enroll` prints the id so it can be matched.

**The challenge is nested inside `auth`, not at the top level.** Vault answers
an enforced login with HTTP 200 and an `auth` block whose `client_token` is an
empty string, carrying the challenge at `auth.mfa_requirement`. The API
contract describes a top-level `mfa_requirement`, and a client that reads there
finds nothing and reports "no token" against a perfectly good password. This
cost an afternoon, because the CLI's test fixture was written from the contract
rather than captured from the wire: every test passed while every real login
failed. Capture the response, do not transcribe the docs.

**Vault activates a TOTP secret the moment it issues one.** There is no pending
state to confirm against, so a mis-scan is only discovered at the next login,
by which point `admin-generate` has already replaced whatever the authenticator
held. That is a lockout with no warning. `just mfa_enroll` therefore asks for a
code and checks it locally against the otpauth URL before letting you walk
away. Skipping that prompt is allowed and says so loudly.

**A username with trailing whitespace still resolves.** `just mfa_reset
'operator<newline>'` matched the real operator entity, destroyed a working
secret, and wrote the replacement QR to a filename containing a newline. The
script now strips and validates the name before anything destructive runs,
because refusing after `entity_id` succeeds is too late.

**`vault list -format=json` prints `{}` and exits 2 when the path is empty.**
Not `[]`, and not nothing. A `|| echo '[]'` fallback therefore APPENDS to that
rather than replacing it, giving `{}` and `[]` as two JSON values on one
stream. `jq length` then prints `0` twice, which matches neither `0` nor `1` in
a case statement. The first version of this script fell through to its
more-than-one branch and told the operator that stray methods existed whenever
Vault held none. `scripts/vault_mfa_test.sh` pins this case, and its fake Vault
reproduces the `{}` exactly, because a fake returning `[]` would pass while the
real thing failed.

**The method id is generated by Vault on create.** Nothing chooses it, so the
script looks it up instead of carrying a literal, and refuses when more than
one method exists rather than guessing.

**Re-enrolling always invalidates the old authenticator.** Vault stores one
secret per entity per method, so `mfa_reset` is destroy-then-generate and there
is no overlap window.

## Next steps

1. Apply in the order above, and confirm `localstack login` prompts for a
   passcode. That is the first time this runs against real Vault: the MFA
   exchange is covered by tests against a fake one, not by a live login.
2. Sign in to ov-dash through the provider page and read `/api/session`. The
   chain has three hops, and only the first is proven by a prompt appearing:
   the trade on `jwt-lab` and the mint can each fail with a token that looks
   fine until OpenViking answers 401.
3. Consider an audit device, so an enrollment or a reset is recorded. That gap
   is older and wider than this work.

## Key references

- `deployments/infrastructure/identity.tf`: the two MFA resources, and the
  `jwt-lab` mount, role and aliases the ov-dash chain needs.
- `deployments/applications/services/ov-dash.hcl`: the dashboard's own
  settings, and what each one is for.
- `deployments/infrastructure/oidc.tf`: the six clients this covers, ov-dash
  among them.
- `scripts/vault_mfa.sh`: enrollment, reset, status, and the traps.
- `scripts/vault_mfa_test.sh`: `just mfa_test`, a fake-Vault suite that needs
  no cluster.
- `justfile`: the three `mfa_*` recipes.
- `docs/vault-human-auth.md`: the login flow this adds a factor to.
- `cli/src/localstack_cli/auth/vault.py`: `MFARequired` and `validate_mfa`.
- `docs/cluster-roles.md`: what `developer` and `admin` can already reach.
