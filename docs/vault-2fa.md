# Two-factor auth on Vault logins

Handoff, 2026-09-11. Nothing is enforced yet, and the last step is blocked.
The enrollment tooling is built, the Terraform below is written and not
applied, and the method can land today. The enforcement cannot: `localstack
login` and ov-dash both post straight at the userpass mount and neither can
answer an MFA challenge. Fix those first. Then the order matters, because
enforcing before everyone holds a secret locks every userpass login out.

## Why the Vault login is the place to do it

Vault is the OIDC provider for humans here, so a person reaches an app by
completing a Vault login first. Five clients are registered with the `lab`
provider (`deployments/infrastructure/oidc.tf`): the smoke client, nomad,
memex, oauth2-proxy (which fronts dash) and grafana.

One enforcement on the `userpass` mount covers all five. It also covers
everything that posts a username and password straight at
`auth/userpass/login/*`, and two of those cannot answer an MFA challenge today.
Read the blockers before applying anything.

## Blockers, as of 2026-09-11

Two first-party consumers log in at the userpass mount directly, and neither
speaks Login MFA. The enforcement breaks both.

**`localstack login` stops working.** `login_userpass`
(`cli/src/localstack_cli/auth/vault.py:117`) posts to
`auth/userpass/login/<user>` and raises unless the response carries
`auth.client_token`. Under Login MFA, Vault answers with a challenge and no
token, so the CLI fails, and its message points at the wrong layer: "Check the
username and that the `userpass` backend is enabled." Nothing in the CLI
handles MFA, and `grep -rni mfa cli/src/` returns nothing.

That bites harder than it looks. All three `mfa_*` recipes open with
`eval "$(localstack env)"`, which needs a live session
(`cli/src/localstack_cli/commands/env.py:33`). Existing sessions keep renewing,
so the rollout looks clean on the day it lands. Once a session lapses, the
operator cannot log in to reach `just mfa_reset`, which is the lost-phone
recovery, and the root token becomes the only way back.

**ov-dash stops working, and it is the only path `veerle` has.**
`deployments/applications/services/ov-dash.hcl:94` sets
`AUTH_MODE = "vault-userpass"` against the same mount, so a person signs in
there with a Vault username and password. Whether `ov-dash:0.3.0` can answer a
challenge is not knowable from this repo, and nothing here suggests it can.

So the order is: teach the CLI the `sys/mfa/validate` exchange, check ov-dash
against an enforced mount, then enforce. The method can land before any of
that, because it enforces nothing on its own.

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

## The Terraform, not yet applied

Goes in `deployments/infrastructure/identity.tf`, beside
`vault_auth_backend.userpass`. Human auth backends live in that file.

```hcl
resource "vault_identity_mfa_totp" "lab" {
  issuer                  = "vault.lab.orangecluster.nl"
  period                  = 30
  algorithm               = "SHA256"
  digits                  = 6
  key_size                = 20
  max_validation_attempts = 5
}

### Accessor, not `auth_method_types`: Vault treats an enforcement's targets as
### a union, so naming the type would sweep in any later userpass mount, and
### naming a second target widens rather than narrows. jwt-nomad stays outside
### this, which is what keeps workload identity working.
resource "vault_identity_mfa_login_enforcement" "userpass" {
  name                  = "userpass-totp"
  mfa_method_ids        = [vault_identity_mfa_totp.lab.method_id]
  auth_method_accessors = [vault_auth_backend.userpass.accessor]
}
```

## Rollout order

Apply the method on its own first. The enforcement is what locks people out,
and it must land after every human holds a secret.

```sh
cd deployments/infrastructure
CONSUL_HTTP_TOKEN=${CONSUL_TOKEN} terraform apply \
  -var-file=./vars/prod.tfvars \
  -target=vault_identity_mfa_totp.lab
```

Then enroll each human and have them confirm a code works before going on.
Two entities need it today. The names are the userpass usernames, not display
names, and `just mfa_status` lists them:

```sh
just mfa_enroll operator
just mfa_enroll veerle
```

Then, and only once both blockers above are cleared, apply the rest, which
adds the enforcement:

```sh
CONSUL_HTTP_TOKEN=${CONSUL_TOKEN} terraform apply -var-file=./vars/prod.tfvars
```

Verify by logging in fresh and expecting a passcode prompt. If the rollout goes
wrong, the root token still logs in and can delete
`identity/mfa/login-enforcement/userpass-totp`.

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

## What this does not cover

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

1. Teach `login_userpass` the `sys/mfa/validate` exchange. Until that lands,
   enforcing MFA costs the CLI, and with it the recovery recipes.
2. Check `ov-dash:0.3.0` against an MFA-enforced mount. If it cannot answer a
   challenge, decide whether `veerle` keeps ov-dash or gets MFA, because the
   mount-wide enforcement cannot give her both.
3. Apply the method, enroll both people, then enforce.
4. Consider an audit device, so an enrollment or a reset is recorded. That gap
   is older and wider than this work.

## Key references

- `deployments/infrastructure/identity.tf`: where the two resources go.
- `deployments/infrastructure/oidc.tf`: the five clients this covers.
- `scripts/vault_mfa.sh`: enrollment, reset, status, and the traps.
- `scripts/vault_mfa_test.sh`: `just mfa_test`, a fake-Vault suite that needs
  no cluster.
- `justfile`: the three `mfa_*` recipes.
- `docs/vault-human-auth.md`: the login flow this adds a factor to.
- `docs/cluster-roles.md`: what `developer` and `admin` can already reach.
