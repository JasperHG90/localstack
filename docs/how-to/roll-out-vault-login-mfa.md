# How to roll out Vault login MFA

## Introduction

Five steps, and the order is the whole point: the enforcement lands last,
because it is the only step that can lock somebody out, and the ov-dash chain
lands before the dashboard that depends on it.

## Prerequisites

- A checkout of this repo, with `git status` checked: see step 1.
- The `localstack` CLI, for `eval "$(localstack env)"`.
- Every person who logs in at userpass, with a phone and an authenticator
  app, for step 2.

## Directions

### Step 1: Apply the TOTP method on its own

Every apply below is targeted. Both roots carry unrelated pending work, and an
untargeted apply on the infrastructure root restarts MinIO while one on the
applications root re-registers OpenViking. Check `git status` first and know
what else is in the tree.

```sh
cd deployments/infrastructure
eval "$(localstack env)"
terraform apply -var-file=./vars/prod.tfvars \
  -target=vault_identity_mfa_totp.lab
```

### Step 2: Enroll everyone who logs in at userpass

Scan each QR and confirm a code
works before going further. The enforcement is mount-wide, so an unenrolled
account cannot complete a login at all. `just mfa_status` lists who it covers.

```sh
just mfa_enroll operator
just mfa_enroll veerle
```

### Step 3: Apply the ov-dash chain in one apply

The mount, the role and the aliases go
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

### Step 4: Deploy the dashboard

Move `ov_dash_image` in
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
(see [What this does not cover](../explanation/vault-login-mfa.md#what-this-does-not-cover)).

Two things to check after the apply. That the deployed release carries the
trade: `ov_dash_image` in `deployments/applications/services.tf`. And that each
person has an alias on `jwt-lab`. Without the alias Vault invents a fresh
entity for the login rather than refusing it, and that entity is in no group,
so its token holds `default` alone and the mint answers 403. It fails closed,
but the error to look for is Vault's permission denied at the mint, not
anything ov-dash says about claims.

### Step 5: Apply the enforcement, last and alone

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

## Additional resources

- [Vault login MFA](../reference/vault-login-mfa.md): the `mfa_*` recipes
  and what the factor reaches.
- [Two-factor auth on Vault logins](../explanation/vault-login-mfa.md)
- [How to turn off Vault login MFA](turn-off-vault-login-mfa.md)
