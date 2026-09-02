# Short-lived Postgres credentials from Vault

**Vault's database secrets engine works, and R3 should roll it out. It needs
one statement most guides leave out.** A Nomad job now reads a freshly minted
Postgres user through its Workload Identity JWT and does memex's real work
against memex's real tables. That credential is minted on demand and dies with
its lease, so it exists in no Terraform state and no KV2 entry. It does reach
the task as a rendered file, `secrets/db.env`, exactly as today's static
passwords do: what changes is the credential's lifetime, not the delivery.
Proven live against firebat on 2026-08-03. One long-lived password remains, the
minting admin's, and it is named in "What this spike left running" below.

The statement is `ALTER ROLE "{{name}}" SET ROLE "<owner>"`. Without it the
spike fails, and it fails quietly, which is why this document leads with it.

## What would have ruled this out

Before running anything, the falsifier:

> A dynamically minted user cannot do the work an application does, because
> reproducing the grants and ownership of the static role it replaces needs
> `creation_statements` too complicated to maintain.

That is close to what happened on the first attempt. It turned out to need one
more statement, not an unmaintainable pile of them, so Path A survives. Had the
fix been a per-table grant list that drifts every time a migration runs, this
document would recommend against R3.

## Where the credentials live today

Every Postgres consumer holds a long-lived static password. Terraform generates
it, writes it to Vault KV2, and each job reads it back through a `vault {}`
block and a `template { env = true }`:

- the admin role, `deployments/infrastructure/secrets.tf:98-112`
- the per-application roles, `deployments/applications/database.tf:56-67`
- a job consuming one, `deployments/applications/services/memex.hcl:44-54`

Nothing rotates. A leaked password stays valid until a human changes it.

## Path A: Vault's database secrets engine

### The pieces

All in `deployments/applications/database-secrets-poc.tf`, in the applications
root because it is the only one with a `postgresql` provider:

1. `vault-dbengine-admin`, a dedicated Postgres role with `CREATEROLE` and
   membership in `memex` `WITH ADMIN OPTION`. The engine mints users as this
   role, never as `localstack`.
2. The `database` mount and a connection to firebat PG18 authenticating as
   that admin.
3. Role `s2-poc`, `default_ttl` 120s, `max_ttl` 300s, whose
   `creation_statements` create the user, grant it `memex`, and set its
   default role.
4. A `vault_policy` scoped to `read` on `database/creds/s2-poc` and a
   `vault_jwt_auth_backend_role` bound to the PoC job, following F3's pattern
   at `deployments/infrastructure/acme.tf:41-90`.

The shared Ansible policy was never touched. `git diff bootstrap/` is empty.

### Can a minted user do the app's work

Yes. Through the Nomad job, on its Workload Identity token:

```
S2 == identity ==
memex member_of=pg_database_owner,memex
S2 == read an existing memex-owned table ==
entities rows=25866
S2 == migration round-trip on a scratch table ==
CREATE TABLE
scratch owner=memex
INSERT 0 1
read back: written by a vault-minted user
DROP TABLE
S2 == grant test passed ==
```

Reading 25,866 rows from a table `memex` owns is the half `select 1` cannot
test: `select 1` needs only CONNECT and passes for a role with no privileges at
all.

The negative control ran 45 seconds earlier: the same template, in a job with a
bare `vault {}` so it fell back to the shared `nomad-workloads` role.

```
Recent Events:
Time                       Type        Description
2026-08-03T21:51:34+02:00  Template    Missing: vault.read(database/creds/s2-poc)
```

The template blocked and the task never started. That is what makes the
dedicated JWT role load-bearing rather than decorative, and it is why the
shared Ansible policy did not need widening.

### The ownership defect, which is the real finding

The first version of `creation_statements` did the obvious two things: create
the role, grant it `memex`. Reads worked. Writes worked. Then this:

```
ERROR:  role "v-root-s2-poc-..." cannot be dropped because some objects
        depend on it
DETAIL:  owner of table s2_orphan_probe
```

A table created by a dynamic user is owned by that dynamic user. Postgres
refuses to drop a role that owns objects, so Vault's revocation fails. What
makes it dangerous is how it fails:

- `vault lease revoke` answers `All revocation operations queued successfully!`
- 30 seconds later the role is still present
- the supposedly revoked credential still logs in and still queries

A revoked credential that keeps working is worse than one that never expires,
because the operator believes it is gone. Vault retries in the background and
keeps failing. The lease sat at a negative TTL and would not clear.

The fix is one statement:

```sql
-- in the Vault role's creation_statements, alongside the CREATE ROLE and GRANT
ALTER ROLE "{{name}}" SET ROLE "memex";
```

Every object the minted user creates then lands on `memex`, matching what the
static role produced. Re-measured after the fix:

- `current_user=memex`, `session_user=v-root-s2-poc-...`, so the audit trail
  still records which minted user acted
- `probe owner=memex`
- revocation succeeds, the role is gone
- the revoked credential is refused: `password authentication failed`

**What this does not settle.** The test covers a dynamic user creating and
owning new objects. It does not cover one modifying an object the static role
already owns: no `UPDATE`, `DELETE` or `ALTER TABLE` was run against a live
memex table, because the blast radius is a production database. That is R3's
failure mode 4
(`.loop/plans/R3-rollout-postgres-vault-db-creds.md:411-414`), and its
second half is still R3's to prove. Role membership makes it very likely to
pass, but likely is not measured.

### What happens to a connection pool when the lease expires

A `psycopg_pool` pool with `min_size=1` held a connection idle for 360s, past
the role's 300s `max_ttl`, with `change_mode = "noop"` so Nomad would not
restart the task and hide the result:

```
S2 pool: opened as memex
S2 pool: idling 360 seconds, past the role max_ttl
S2 pool: HELD connection still works after expiry, rows = 25867
S2 pool: FRESH connect FAILED after expiry: OperationalError connection failed:
  ... FATAL: password authentication failed for user "v-jwt-noma-s2-poc-..."
```

The split is the whole point. PostgreSQL authenticates once, at connection
time, so an open session survives its role being dropped. A new connection with
the same credential is refused. An application therefore looks perfectly
healthy until the moment it needs a connection it does not already have: the
pool growing under load, a reconnect after a network blip, a pool recycling an
old connection. The failure arrives detached in time from the expiry that
caused it, which is what makes it hard to diagnose.

Three mitigations, for R3 to choose between:

1. **Nomad `change_mode = "restart"` on the template**, the default. The task
   restarts when the credential is re-rendered, so the pool is rebuilt with a
   live credential. Costs a restart per rotation.
2. **Pool `max_lifetime` below the lease TTL.** Connections retire before the
   credential does. No restarts, but every pooled client needs configuring, and
   the value has to track the Vault role's TTL.
3. **Reconnect on auth error in the application.** Most correct, least
   available: it needs a code change in every consumer.

Option 1 needs nothing from the applications and is where R3 should start.

### The one-token trade-off R3 inherits

A Nomad task performs a single JWT login and holds a single Vault token, so
naming a dedicated role in `vault { role = ... }` REPLACES `nomad-workloads`
rather than adding to it. The PoC role works around this the way `acme.tf` does,
by listing `nomad-workloads` in its own `token_policies`.

For R3 this is a real cost. Every converted job needs a dedicated JWT role
whose policy carries both the new `database/creds/*` read and the KV grants the
job still uses: memex's `db-migrate` prestart, mlflow, phoenix. The alternative,
widening the shared `nomad-workloads` policy, is one line of Ansible and gives
every workload on the cluster the ability to mint database users.

Take the per-job cost. It is bounded by the number of jobs converted, and F3
already carries the pattern.

### A Terraform trap worth knowing about

Three defects in the write-only credential chain cost real time here, and all
three pass `terraform validate`:

**An ephemeral value is not shared across applies.** `ephemeral
"random_password"` is regenerated every run and persisted nowhere, so consumers
that write in different applies get different passwords. Creating the Postgres
role in one targeted apply and the Vault connection in the next produced
`failed SASL auth ... password authentication failed`. `verify_connection`
caught it, which is a good argument for never setting that to false. An
unchanged `_wo_version` on an existing resource really is a no-op. The hazard
is any resource that writes: one being created, or one whose version moved.

**`vault_kv_secret_v2` reads the secret back by default.** The computed `data`
attribute then holds the plaintext, putting the credential into the
Consul-backed state through the back door. `disable_read = true` is required,
not optional.

**`postgresql_role` fights `postgresql_grant_role`.** With `roles` left unset,
the provider reconciles the role's memberships to the empty set on every update,
silently stripping the membership granted elsewhere. Minting then failed with
`permission denied to grant role "memex" (SQLSTATE 42501)` at the next
`vault read`, long after the apply that broke it reported success. Naming the
membership in both places keeps them agreeing.

With all three handled, the state is clean: `terraform state pull` over 233 KB
contains zero occurrences of the admin password.

That last point is what justifies keeping this engine's mount and config in
Terraform at all. F5 and F6 hand both to Ansible whenever a Vault engine needs
a privileged external credential
(`deployments/infrastructure/consul_deploy_role.tf:7-15`), precisely to keep
that credential out of the Consul-backed state. The write-only chain achieves
the same end, so the exception is earned rather than assumed. It is earned only
while the chain stays intact: swap the ephemeral for a `random_password`
resource and the password lands in state, and the exception collapses.

## Path B: PostgreSQL 18 native OAuth

Investigated for one hour on 2026-08-03. Answer: **you would have to write the
validator yourself, so this is not a near-term option.**

PostgreSQL 18 ships no built-in OAuth validator, by design: "Because OAuth
implementations vary so wildly, and bearer token validation is heavily
dependent on the issuing party, the server cannot check the token itself"
(https://www.postgresql.org/docs/18/oauth-validators.html). `pg_hba`'s
`validator=` must name a library in `oauth_validator_libraries`, empty by
default (https://www.postgresql.org/docs/18/auth-oauth.html).

Third-party validators that do exist:

| Module | Validates by |
|---|---|
| Percona `pg_oidc_validator` (https://github.com/percona/pg_oidc_validator) | JWT signature against a JWKS, locally |
| dvob `pg_oidc_validator` (https://github.com/dvob/pg_oidc_validator) | JWT against JWKS; self-described proof of concept |
| TantorLabs `oauth_validator` (https://github.com/TantorLabs/oauth_validator) | parses the JWT payload; base version verifies no signature |
| CloudNativePG Keycloak validator (https://github.com/cloudnative-pg/postgres-keycloak-oauth-validator) | a Keycloak-proprietary UMA call |

None calls a standard RFC 7662 introspection endpoint, and Vault has no
introspection endpoint to call. Vault's OIDC provider issues an opaque batch
token, not a JWT (https://developer.hashicorp.com/vault/docs/concepts/oidc-provider),
so a JWKS-verifying validator has nothing to verify.

Two further points against, and one open question:

- PG18's `oauth` method drives the *client* through the OAuth Device
  Authorization Grant. Neither Vault's OIDC provider nor Nomad implements it,
  so even a working validator leaves the client side unsolved.
- A Vault *identity* token and a Nomad Workload Identity JWT are real JWTs with
  real JWKS endpoints, unlike the OIDC provider's access token.
- **Not established within the time box:** whether Percona's validator would
  accept a Nomad WI JWT if pointed at Nomad's discovery URL. Settling it needs
  a code read and a live test, not a documentation lookup. If Path A were ever
  rejected, this is where to resume.

## Runbook

Everything below runs from `deployments/applications`. Terraform state is in
the Consul backend, so every terraform call needs the `CONSUL_HTTP_TOKEN`
prefix the justfile recipes set.

**Mint a credential and use it.** This is what S1 inherits.

```
vault read database/creds/s2-poc
```

Returns a `username`, a `password` and a `lease_id`. The user is dropped when
the lease expires, at `max_ttl` 300s at the latest. To use it:

```
PGPASSWORD=<password> psql -h 192.168.2.30 -U <username> -d memex -c 'select 1'
```

`psql` is not installed in the devcontainer. Use
`docker run --rm -e PGPASSWORD=<password> postgres:18 psql ...` instead, or run
from inside an allocation.

**Confirm the engine is healthy.**

```
vault read database/config/postgres-poc
vault read database/roles/s2-poc
```

The connection's `username` must read `vault-dbengine-admin`, never
`localstack`, and the role must show a short `max_ttl`.

**Revoke early.**

```
vault lease revoke <lease_id>
```

Check it worked rather than trusting the reply. `vault lease revoke` answers
`All revocation operations queued successfully!` even when the DROP failed. Run
the check as `localstack`, not as the user you just revoked, whose connection
the revoke is meant to have destroyed:

```sql
select count(*) from pg_roles where rolname = '<username>';
```

Zero means the revoke really took.

**Rebuild what is standing.** This does NOT include the Nomad job, its
`vault_policy` or its `vault_jwt_auth_backend_role`. `-target` pulls in a
resource's dependencies, never its dependents, and the job depends on the role
rather than the reverse, so it is excluded by construction as well as on
purpose. To opt back into it, add `-target=nomad_job.s2_poc_dynamic_creds`.

```
CONSUL_HTTP_TOKEN=${CONSUL_TOKEN} terraform apply -var-file=./vars/prod.tfvars \
  -target=postgresql_role.s2_poc_admin \
  -target=postgresql_grant_role.s2_poc_admin_owner \
  -target=vault_kv_secret_v2.s2_poc_admin \
  -target=vault_mount.database \
  -target=vault_database_secret_backend_connection.postgres_poc \
  -target=vault_database_secret_backend_role.poc
```

All six in ONE apply. Splitting them across applies gives the Postgres role and
the Vault connection different passwords, and the apply fails with
`failed SASL auth`. The reason is in "A Terraform trap worth knowing about"
above.

**Tear the rest down.** The command is in the header of
`deployments/applications/database-secrets-poc.tf`.

## Does this need Boundary

No, not for this. Boundary brokers *human* access: a session proxy, session
recording, and no direct network route to 5432. Machine access is already
solved end to end by Nomad Workload Identity, as the job above demonstrates
with no key material anywhere in the path.

Whether the human half justifies Boundary is a separate question and S1 owns
it. S1 inherits a working `database/creds/s2-poc` path from this spike rather
than a description of one, so it can test brokering against real credentials.

## Recommendation

**Proceed with Path A in R3.** The evidence:

| Check | Result |
|---|---|
| Engine and connection against firebat PG18 | pass |
| Connection authenticates as `vault-dbengine-admin`, root rotation off | pass |
| Role mints a short-lived user, `max_ttl` 300s | pass |
| Minted user does memex's work on memex-owned objects | pass, after the `SET ROLE` fix |
| Nomad job reads creds via a dedicated JWT role, `bootstrap/` untouched | pass |
| Rotation in pools characterized | pass, held connection survives, fresh connect fails |
| Path B investigated | no usable validator exists |

R3 must carry forward:

1. `ALTER ROLE "{{name}}" SET ROLE "<owner>"` in every role's
   `creation_statements`. Without it, revocation silently fails and revoked
   credentials keep working.
2. `change_mode = "restart"` on credential templates, unless a consumer is
   changed to reconnect on auth errors.
3. Production TTLs. 120s and 300s here exist to make expiry observable inside a
   test, and are not sensible for a running service.
4. A dedicated JWT role per converted job, whose policy carries both the
   `database/creds/*` read and that job's existing KV grants.
5. The write-only chain intact, including `disable_read = true`, `roles` named
   on the admin role, and all consumers written in one apply.
6. The untested half of failure mode 4: a dynamic user mutating an object the
   static role already owns.

## What this spike left running

Kept, because S1 needs them:

- the `database` mount
- connection `postgres-poc` against firebat, as `vault-dbengine-admin`
- role `s2-poc`
- the `vault-dbengine-admin` Postgres role, which holds `CREATEROLE`
- that role's password, at the KV2 path
  `<secret_mount>/default/postgres/vault-dbengine-admin`, which is
  `secret/default/postgres/vault-dbengine-admin` on this cluster

The last one is a long-lived credential this spike created, so treat it as
part of the surface rather than an implementation detail. It is the only
password the change writes. Everything the PoC job used was minted and
revoked.

Destroyed: the `s2-poc-dynamic-creds` Nomad job, its `vault_policy`, its
`vault_jwt_auth_backend_role`, and every scratch table and minted user. No
`v-root-s2-poc%` or `v-jwt-noma-s2-poc%` role and no `s2_%` table remains in
memex.

Those three destroyed resources are still declared in
`deployments/applications/database-secrets-poc.tf`, because they are the
working reference R3 copies. A full `terraform apply` of that root recreates
them. The file header carries the one command that removes them again. R3
deletes the file once it ships the real thing.
