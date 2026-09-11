# Two-factor auth on Vault logins

Handoff, 2026-09-11. Ready to apply, scoped to the operator. The enrollment
tooling is built and tested, `localstack login` now speaks Login MFA, and the
two Terraform resources are in `deployments/infrastructure/identity.tf`. What
is left is to apply them, in the order below, because enforcing before the
operator holds a secret locks that account out of userpass.

## Why the Vault login is the place to do it

Vault is the OIDC provider for humans here, so a person reaches an app by
completing a Vault login first. Five clients are registered with the `lab`
provider (`deployments/infrastructure/oidc.tf`): the smoke client, nomad,
memex, oauth2-proxy (which fronts dash) and grafana. A second factor on the
Vault login therefore reaches all five without touching any of them.

## Why the enforcement names one entity, not the mount

`auth_method_accessors = [vault_auth_backend.userpass.accessor]` is the obvious
form and covers every human at once. It also covers everything that posts a
username and password straight at `auth/userpass/login/*`, and there are two of
those.

**`localstack login` was one, and is now fixed.** `login_userpass` raised
unless the reply carried `auth.client_token`, and Vault answers an enforced
mount with HTTP 200, a null `auth` and an `mfa_requirement`. The CLI reported
that as "returned no token. Check the username", which sends the reader looking
for a typo that is not there. It now raises `MFARequired`, prompts for the
passcode, and finishes at `sys/mfa/validate`. This mattered more than it
looked: all three `mfa_*` recipes open with `eval "$(localstack env)"`, so an
unfixed CLI would have stranded the operator with no way to reach
`just mfa_reset` once a session lapsed.

**ov-dash is the other, and is not fixed.**
`deployments/applications/services/ov-dash.hcl:94` sets
`AUTH_MODE = "vault-userpass"` against the same mount. Whether
`ov-dash:0.3.0` can answer a challenge is not knowable from this repo, and
nothing here suggests it can. ov-dash is the only service `veerle` reaches, so
a mount-wide enforcement would trade her entire access for a factor she cannot
supply.

So the enforcement names `vault_identity_entity.operator` and nothing else.
That is the account worth protecting anyway: `developer` plus the `admin`
group, which reach root in a few commands. Widening to the mount is a one-line
change once somebody checks ov-dash against an enforced login.

Scoping this way spares `veerle`, and only her. The operator still meets the
challenge at every userpass login, ov-dash included. See the coverage section
below before applying.

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

Two resources in `deployments/infrastructure/identity.tf`, beside
`vault_auth_backend.userpass`, because human auth backends live in that file:
`vault_identity_mfa_totp.lab` and
`vault_identity_mfa_login_enforcement.operator`. The comment above the second
records why it names an entity rather than the mount.

Neither has been applied. `terraform validate` and `terraform fmt` pass;
`terraform plan` was never run, because this devcontainer's Consul token lacks
`key:read` on `terraform/infrastructure`.

## Rollout order

Apply the method on its own first. The enforcement is what locks the account
out, and it has to land after the operator holds a secret.

```sh
cd deployments/infrastructure
CONSUL_HTTP_TOKEN=${CONSUL_TOKEN} terraform apply \
  -var-file=./vars/prod.tfvars \
  -target=vault_identity_mfa_totp.lab
```

Then enroll, scan the QR, and confirm a code works before going on. Only the
operator is in scope; `just mfa_status` lists who a mount-wide enforcement
would cover if that changes later.

```sh
just mfa_enroll operator
```

Then apply the rest, which adds the enforcement:

```sh
CONSUL_HTTP_TOKEN=${CONSUL_TOKEN} terraform apply -var-file=./vars/prod.tfvars
```

Verify with `localstack login`, which should ask for the password and then a
TOTP passcode. If the rollout goes wrong, the root token still logs in and can
delete `identity/mfa/login-enforcement/operator-totp`.

## Running it

| Command | Does |
| --- | --- |
| `just mfa_status` | Shows the method, the enforcements, and who logs in through userpass |
| `just mfa_enroll <username>` | Writes that person's QR to `tmp/`. Refuses if they already have a secret |
| `just mfa_reset <username>` | Destroys the old secret and issues a new QR. For a lost phone |

All three call `scripts/vault_mfa.sh`, which holds the traps in comments. The
QR lands in `tmp/`, which the repo gitignores. It carries the seed in full, so
it stays a secret until it is scanned and deleted.

Terraform owns the method and the enforcement. The script owns only the
per-person secret, and Terraform must never hold that: the secret is the second
factor, so putting it in state files both factors in one place.

## What a second factor on the Vault login actually reaches

Covered, because they redirect to the `lab` provider and the prompt happens at
Vault: nomad, memex, dash, registry-ui (it reuses the `oauth2_proxy` client)
and Grafana's Vault sign-in button. The factor is asked once per VAULT
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

### ov-dash breaks for the operator, not for veerle

Scoping the enforcement to an entity does NOT spare ov-dash. Vault matches the
enforcement wherever that entity authenticates, and ov-dash posts straight at
`auth/userpass/login/operator`. So if `ov-dash:0.3.0` cannot answer a
challenge, applying the enforcement costs the operator ov-dash. `veerle` keeps
it because she is out of scope.

Test that before the third apply. If it breaks, either drop the enforcement or
reach OpenViking through the Vault UI until ov-dash learns the exchange.

## What this does not cover

- **Only the operator is enforced.** `veerle` logs in at the same mount and is
  deliberately out of scope until ov-dash is checked, so her password is still
  a single factor. Widening is one line, and the reason it is not that line
  today is written above the resource.
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
2. Check `ov-dash:0.3.0` against an MFA-enforced login. If it can answer a
   challenge, widen the enforcement to
   `auth_method_accessors = [vault_auth_backend.userpass.accessor]` and enroll
   `veerle`. If it cannot, `veerle` keeps ov-dash and stays out of scope.
3. Consider an audit device, so an enrollment or a reset is recorded. That gap
   is older and wider than this work.

## Key references

- `deployments/infrastructure/identity.tf`: where the two resources go.
- `deployments/infrastructure/oidc.tf`: the five clients this covers.
- `scripts/vault_mfa.sh`: enrollment, reset, status, and the traps.
- `scripts/vault_mfa_test.sh`: `just mfa_test`, a fake-Vault suite that needs
  no cluster.
- `justfile`: the three `mfa_*` recipes.
- `docs/vault-human-auth.md`: the login flow this adds a factor to.
- `cli/src/localstack_cli/auth/vault.py`: `MFARequired` and `validate_mfa`.
- `docs/cluster-roles.md`: what `developer` and `admin` can already reach.
