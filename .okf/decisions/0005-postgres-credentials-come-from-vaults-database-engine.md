---
type: decision
title: "ADR 0005: Short-lived Postgres credentials come from Vault's database secrets engine, not PostgreSQL 18 native OAuth"
description: "The S2 spike proved Path A, Vault minting a Postgres user per lease, against memex's real tables, and recommended R3 roll it out. Path B, PostgreSQL 18 OAuth, was rejected because no usable validator exists for Vault or Nomad tokens."
generated:
  by: claude-opus/5.5
  at: 2026-09-26
tags: [adr, decision, postgres, vault, workload-identity]
status: stable
decision_status: Accepted, not yet rolled out
decided_on: 2026-08-03
sources:
  - id: postgres-vault-dynamic-creds-spike
    resource: git:3ec5d1e:docs/postgres-vault-dynamic-creds-spike.md
    last_modified: 2026-09-03
---

# ADR 0005: Short-lived Postgres credentials come from Vault's database secrets engine, not PostgreSQL 18 native OAuth

- Status: Accepted, not yet rolled out
- Date: 2026-08-03

> Written retrospectively from `docs/postgres-vault-dynamic-creds-spike.md`, dated 2026-09-03.
> R3, the rollout it recommends, is blocked in `.loop/ledger.json` as of
> 2026-09-26, and the PoC it describes was deleted in commit 19c1696.

## Context

Every Postgres consumer holds a long-lived static password. Terraform generates
it, writes it to Vault KV2, and each job reads it back through a `vault {}`
block and a `template { env = true }`:

- the admin role, `deployments/infrastructure/secrets.tf:98-112`
- the per-application roles, `deployments/applications/database.tf:56-67`
- a job consuming one, `deployments/applications/services/memex.hcl:44-54`

Nothing rotates. A leaked password stays valid until a human changes it.

Before running anything, the falsifier:

> A dynamically minted user cannot do the work an application does, because
> reproducing the grants and ownership of the static role it replaces needs
> `creation_statements` too complicated to maintain.

That is close to what happened on the first attempt. It turned out to need one
more statement, not an unmaintainable pile of them, so Path A survives. Had the
fix been a per-table grant list that drifts every time a migration runs, this
document would recommend against R3.

### Path B: PostgreSQL 18 native OAuth

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

## Decision

**Vault's database secrets engine works, and R3 should roll it out. It needs
one statement most guides leave out.** A Nomad job now reads a freshly minted
Postgres user through its Workload Identity JWT and does memex's real work
against memex's real tables. That credential is minted on demand and dies with
its lease, so it exists in no Terraform state and no KV2 entry. It does reach
the task as a rendered file, `secrets/db.env`, exactly as today's static
passwords do: what changes is the credential's lifetime, not the delivery.
Proven live against firebat on 2026-08-03. One long-lived password remains, the
minting admin's, and it is named in "What this spike left running" in
[the proposal](/proposals/postgres-dynamic-credentials.md).

The statement is `ALTER ROLE "{{name}}" SET ROLE "<owner>"`. Without it the
spike fails, and it fails quietly, which is why the
[proposal](/proposals/postgres-dynamic-credentials.md) leads with it.

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

## Consequences

Every converted job carries the six points above. The measurements behind
them, the runbook the spike used, and what it left running on the cluster are
in [the proposal](/proposals/postgres-dynamic-credentials.md). The per-job JWT role in point 4 is its own record,
[ADR 0006](/decisions/0006-each-converted-job-gets-its-own-vault-jwt-role.md).

The Redis cache credentials in `deployments/infrastructure/database.tf` use
the same engine, mounted at `redis` rather than `database` for the reason that
file records.
