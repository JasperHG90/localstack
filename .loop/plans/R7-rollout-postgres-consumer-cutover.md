---
epic = "rollout"
depends_on = ["R3-rollout-postgres-vault-db-creds"]
priority = 3
summary = "Convert every remaining application Postgres consumer (the three of memex, phoenix, mlflow, bifrost that R3 did not take) onto per-job Vault JWT roles reading database/creds/<role>. R3 proves the pattern on one; R7 finishes the set. Excludes the two localstack-root consumers (postgres-exporter, backup-postgres), the ducklake roles, and the golang-migrate runner."
tags = ["postgres", "vault", "secrets", "nomad", "rollout"]
---

# Ticket: R7-rollout-postgres-consumer-cutover

## 1. Title

Convert the remaining application Nomad jobs off static KV2 Postgres
passwords and onto per-job Vault JWT roles reading `database/creds/<role>`,
so no application password for Postgres survives a lease.

## 2. Size / Effort

**L.** Not algorithmically hard. The size comes from breadth, live blast
radius, and a per-service judgment call that cannot be batched.

Drivers:

- Three services (whichever of memex, phoenix, mlflow, bifrost R3 left),
  each needing its own Vault DB role, `vault_policy`,
  `vault_jwt_auth_backend_role`, jobspec template rewrite, and a Postgres
  membership grant on the minting admin.
- Every conversion is a live cutover against a database holding real data.
- Each service needs its own rotation answer (restart cadence versus pool
  lifetime), and memex's answer differs from the others because a restart
  reloads GPU models.
- One Postgres behavior S2 never measured (a dynamic user mutating an
  object the static role already owns) is R7's to prove, on production
  tables.

## 3. Triggered by

R3's §5 non-goal. R3 converts exactly ONE consumer and documents the path
for the rest: "Converting all of memex, phoenix, mlflow, the exporter, and
the migrations runner in this ticket is explicitly out of scope"
(`.loop/plans/R3-rollout-postgres-vault-db-creds.md:129-133`). No ticket
owns the remainder. R7 is that remainder, minus the exclusions in §5,
settled by the operator on 2026-08-04.

S2 already ran and proved the mechanism live on 2026-08-03. Its findings
are the authority for R7, so do not re-derive them. Read
`docs/postgres-vault-dynamic-creds-spike.md` first.

## 4. Context

### The four application Postgres consumers, all static today

Terraform mints one 16-character password per role at
`deployments/applications/database.tf:56-60`, attaches it to a login role
at `deployments/applications/database.tf:62-67`, and copies it to KV2 at
`deployments/applications/secrets.tf:1-9` plus a per-app entry each. The
role list is at `deployments/applications/database.tf:2-9`.

| Job | Static KV2 entry | Jobspec anchor | Consumption shape |
|---|---|---|---|
| memex | `deployments/applications/secrets.tf:22-29` | `deployments/applications/services/memex.hcl:52-55` and `:132-135` | two tasks, separate env vars |
| phoenix | `deployments/applications/secrets.tf:11-18` | `deployments/applications/services/phoenix.hcl:61` | one inline URL |
| mlflow | `deployments/applications/secrets.tf:53-60` | `deployments/applications/services/mlflow.hcl:49` | one inline URL |
| bifrost | `deployments/applications/secrets.tf:128-135` | `deployments/applications/services/bifrost.hcl:81-85` | env vars, then indirected through config.json |

Three distinct migration shapes, and they are not interchangeable:

- **memex** has TWO tasks that each read the credential: the `db-migrate`
  prestart task (`deployments/applications/services/memex.hcl:24-60`) and
  the long-running `memex` task
  (`deployments/applications/services/memex.hcl:68-196`). Both carry a bare
  `vault {}` block (`:44` and `:114`), so both need the dedicated role.
  memex also pools: `MEMEX_SERVER__META_STORE__POOL_SIZE=20` and
  `MAX_OVERFLOW=30` at `deployments/applications/services/memex.hcl:136-137`.
- **phoenix and mlflow** build the whole connection URL inline in one
  template line (`deployments/applications/services/phoenix.hcl:61`,
  `deployments/applications/services/mlflow.hcl:49`). Username and password
  are interpolated mid-string, so the rewrite is a different edit from
  memex's separate env vars.
- **bifrost** renders `PG_USER` and `PG_PASSWORD` into
  `secrets/bifrost.env` (`deployments/applications/services/bifrost.hcl:81-85`),
  then its config.json names them indirectly as `env.PG_USER` and
  `env.PG_PASSWORD` (`deployments/applications/services/bifrost.hcl:130-141`).
  Bifrost resolves those at process start, so a credential change reaches
  the running process only through a task restart.

The jobspecs receive the KV2 path as a templatefile variable from
`deployments/applications/services.tf:112-122` (phoenix),
`:167-188` (memex), `:191-219` (bifrost), `:295-308` (mlflow).

### What S2 left standing, and what it proved

Live on the cluster, verified 2026-08-04: the `database` mount, connection
`postgres-poc` authenticating as `vault-dbengine-admin` against
192.168.2.30:5432/memex with `allowed_roles [s2-poc]`, and role `s2-poc`.
The declarations are in `deployments/applications/database-secrets-poc.tf`,
a throwaway file R3 (or R7) deletes.

The findings R7 carries, each cited to the spike doc:

- `ALTER ROLE "{{name}}" SET ROLE "<owner>"` is mandatory in every role's
  `creation_statements`. Without it, revocation fails silently and the
  revoked credential keeps working
  (`docs/postgres-vault-dynamic-creds-spike.md:97-134`,
  `deployments/applications/database-secrets-poc.tf:251-264`).
- Per-job authorization uses a dedicated `vault_policy` plus a
  `vault_jwt_auth_backend_role` on the Ansible-owned `jwt-nomad` mount,
  following F3's pattern (`deployments/infrastructure/acme.tf:41-90`). The
  shared Ansible policy stays untouched
  (`docs/postgres-vault-dynamic-creds-spike.md:60`).
- One token per task. Naming a role in `vault { role = ... }` REPLACES
  `nomad-workloads`, so the dedicated role must list it in
  `token_policies` (`deployments/infrastructure/acme.tf:56-61`,
  `deployments/applications/database-secrets-poc.tf:286-310`).
- A HELD connection survives lease expiry, but a FRESH connect with an expired
  credential is refused
  (`docs/postgres-vault-dynamic-creds-spike.md:145-165`).
- A dynamic credential template reads `.Data.username`, not
  `.Data.data.username`; KV2 nests, a dynamic secret does not
  (`deployments/applications/services/poc-dynamic-creds.hcl:30-35`).
- Three Terraform traps that all pass `terraform validate`
  (`docs/postgres-vault-dynamic-creds-spike.md:196-232`).

### What is wrong today

Every application Postgres password is minted once and never rotates, sits
at rest in KV2 indefinitely, and is byte-identical across every restart of
every job. R3 removes that for one service. Three remain.

## 5. Non-goals / out of scope

- **The two `localstack` root consumers.** `postgres-exporter`
  (`deployments/infrastructure/services/postgres.hcl:88-130`, DSN at
  `:122-130`) and `backup-postgres`'s `pg_dumpall`
  (`deployments/infrastructure/services/backup-postgres.hcl:29`, credential
  at `:36-37`) both authenticate as the `localstack` root role
  (`deployments/infrastructure/secrets.tf:74-88`,
  `deployments/infrastructure/backup.tf:34-40`). Converting them is what
  would unlock Vault-managed rotation of that root, which is a different
  and riskier problem: S2 measured that rotating `localstack` breaks the
  exporter, the pg_dumpall backup, and this root's own `postgresql`
  provider (`deployments/applications/providers.tf:50-57`) at once
  (`deployments/applications/database-secrets-poc.tf:78-82`).
  **`R8-rollout-postgres-root-consumers` owns that**
  (`.loop/plans/R8-rollout-postgres-root-consumers.md`, a stub filed
  2026-08-04 and registered in the ledger). R7 names the exclusion and
  designs nothing for it. See Q8.
- **The `ducklake_owner` and `ducklake_reader` roles**
  (`deployments/applications/database.tf:3-4`). No Nomad job consumes them;
  DuckDB clients do, so there is no workload identity to attach a
  credential to. **No ticket owns them today, and this plan does not hand
  them to one.** They stay static. *(Corrected 2026-08-04: this bullet
  previously handed them to `S1-spike-boundary-evaluation` and cited
  `docs/postgres-vault-dynamic-creds-spike.md:346-355` for it. That anchor
  resolves but argues about human access in general and never says
  "ducklake"; `grep -in ducklake` on S1's plan returns zero hits, and S1 is
  `blocked` on its own BROKEN verdict. Claiming an owner that has not
  accepted the work is worse than naming the gap.)* Nothing breaks by
  leaving them: no workload consumes them, so they are a standing static
  credential and no more. Whoever picks up client access to DuckDB inherits
  the question. R7 leaves both roles, their passwords, and their KV2
  entries exactly as they are.
- **The golang-migrate runner.** `applications/migrations/justfile:7-11`
  runs `migrate -database ${POSTGRESQL_URL}` from a static string in
  `applications/migrations/.env`. It runs outside Nomad, so it has no
  workload identity. R7 records that it stays static rather than silently
  converting it. *(Corrected 2026-08-04: an earlier draft said "R3 already
  deferred it". `.loop/plans/R3-rollout-postgres-vault-db-creds.md:490-494`
  is an unresolved Q6 leaning toward static, not a settled deferral. The
  decision to keep it static is R7's own and stands on its own reasoning.)* This is NOT
  memex's `db-migrate` prestart task
  (`deployments/applications/services/memex.hcl:24-42`), which runs the
  memex CLI inside Nomad and IS in scope.
- **Re-deciding R3's engine design.** The mount, the connection, the
  minting admin identity, and the role-statement shape are R3's output. R7
  discovers and extends them rather than redesigning them. If R3 shipped
  something the plan did not anticipate, raise it rather than diverging.
- **Widening the shared `nomad-workloads` policy.**
  `git diff bootstrap/` must stay empty
  (`docs/postgres-vault-dynamic-creds-spike.md:60`).
- **Dropping any static Postgres role.** See requirement 7: the static role
  stays as the owning group role.
- **Changing app behavior, tuning, ports, images, or storage.** Only the
  credential source moves.

## 6. Requirements & restrictions

The change MUST:

1. **Discover R3's output before writing anything.** Read the merged R3
   plan and diff, then read the live engine
   (`vault list database/roles`, `vault read database/config/<name>`,
   `vault list auth/jwt-nomad/role`) and confirm which service is already
   converted, what the connection is called, what the role naming
   convention is, and whether
   `deployments/applications/database-secrets-poc.tf` still exists. Do not
   hardcode a service list. Record the discovered facts in the commit or
   the doc so a reviewer can check them.
2. **Define one Vault DB role per remaining service**, matching R3's
   naming, whose `creation_statements` create the login role, grant it the
   service's static owner role, and set `ALTER ROLE "{{name}}" SET ROLE
   "<owner>"`. The third statement is not optional
   (`docs/postgres-vault-dynamic-creds-spike.md:97-134`). Add each role to
   the connection's `allowed_roles`.
3. **Hold the minting-admin invariant, and discover its current shape
   rather than assuming one.** The invariant: *the minting admin must hold
   ADMIN OPTION on the owner role of every service it mints for.* From
   PostgreSQL 16 on, a `CREATEROLE` role may only grant memberships it
   holds ADMIN on, so without it, minting fails with
   `permission denied to grant role ... (SQLSTATE 42501)` at
   `vault read database/creds/<role>` time — long after the apply that set
   it up reported success.

   Whether the invariant already holds for a given service is **discovery,
   part of requirement 1, not construction**. Check it with
   `select r.rolname, m.admin_option from pg_auth_members m join pg_roles r
   on m.roleid = r.oid join pg_roles g on m.member = g.oid where g.rolname
   = '<admin>'` and only then decide whether anything needs adding.

   *(Corrected 2026-08-04. This requirement previously stated as fact that
   the admin holds `memex` alone and instructed the implementer to add each
   new owner's name to the admin role's `roles` list by hand. Both are now
   wrong: commit `a21da6f` derives the grantable set from `local.databases`
   in `deployments/applications/database-secrets-poc.tf`, so all five owner
   roles are already covered and hand-adding names would regress a strictly
   better design. The plan-validator watched this premise flip mid-review;
   see `.loop/verdicts/R7-rollout-postgres-consumer-cutover.plan-validator.md`
   finding P10. State the invariant, not the snapshot.)*

   Two constraints on however the set is expressed. `roles` must name the
   memberships, because the provider reconciles them to empty when it is
   unset (`docs/postgres-vault-dynamic-creds-spike.md:216-220`), and each
   grant keeps its `replace_triggered_by` lifecycle block so a role-only
   update cannot silently strip the admin option.

   **Do not reach for `inherit = false` on the admin.** It is the obvious
   least-privilege move once one login holds membership in every owner
   role, and it breaks Vault's revocation: `REVOKE ALL PRIVILEGES` and
   `DROP OWNED BY` both fail with permission denied because "privileges of"
   means inheritance rather than admin option, while Vault reports
   `All revocation operations queued successfully!` and the role survives.
   Measured live 2026-08-04; the reasoning is recorded in
   `deployments/applications/database-secrets-poc.tf`. See Q5, which prices
   what this costs.
4. **Give each converted job a dedicated `vault_policy` and
   `vault_jwt_auth_backend_role`** on the `jwt-nomad` mount, bound to that
   job's `nomad_job_id`, following
   `deployments/infrastructure/acme.tf:66-90`. `claim_mappings` must mirror
   the shared role or the templated `nomad-workloads` paths resolve to
   nothing (`deployments/infrastructure/acme.tf:63-65`).
5. **Carry `nomad-workloads` in every dedicated role's `token_policies`,
   and verify the per-job KV grant inventory below holds.** A task holds
   ONE Vault token, so a dedicated role replaces the default rather than
   adding to it (`deployments/infrastructure/acme.tf:56-61`). Getting this
   wrong makes a template block forever at deploy time, which is exactly
   what S2's negative control showed
   (`docs/postgres-vault-dynamic-creds-spike.md:84-95`). The shared policy
   grants read on `secret/data/<namespace>/<job_id>/*`
   (`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-8`),
   so keeping it attached preserves each job's other reads. Confirm per
   job, and do not assume:

   | Job | Non-Postgres KV paths it still reads | Anchor |
   |---|---|---|
   | memex | `default/memex/minio`, `default/memex/auth`, `default/memex/bifrost` | `deployments/applications/services.tf:171-183` |
   | phoenix | none | `deployments/applications/services.tf:116` |
   | mlflow | `default/mlflow/minio` | `deployments/applications/services.tf:300` |
   | bifrost | `default/bifrost/credentials`, four `ollama-*`, `gemini` | `deployments/applications/services.tf:205-210` |

   Every path above sits under `default/<job_id>/`, so the inventory is
   satisfied by attachment rather than by hand-written path rules. If a
   later edit moves any of them outside that prefix, the dedicated policy
   must name it explicitly.
6. **Rewrite each jobspec template** to read `database/creds/<role>` with
   `.Data.username` and `.Data.password`
   (`deployments/applications/services/poc-dynamic-creds.hcl:30-35`), set
   `vault { role = ... }` on EVERY task that reads the credential (both
   memex tasks, if memex is R7's), and choose `change_mode` per service
   with a stated reason (requirement 8).
7. **Keep each static role, revoke its login.** The dynamic user
   `SET ROLE`s to the static role and every existing object is owned by it
   (`deployments/applications/database.tf:69-77` sets the database owner),
   so dropping it would orphan the schema. Set `login = false` on the
   converted service's `postgresql_role`, and remove its `random_password`
   and its KV2 entries (`deployments/applications/secrets.tf:1-9` per-role
   entry plus the per-app entry). Do this only AFTER the dynamic path is
   proven for that service, never in the same step.
8. **Choose the rotation strategy per service and justify it.** S2's
   ordered mitigations are Nomad `change_mode = "restart"` (the default,
   needs nothing from the app), pool `max_lifetime` below the lease TTL, or
   app-level reconnect on auth error
   (`docs/postgres-vault-dynamic-creds-spike.md:167-178`). These are
   long-running services, unlike S2's batch job, so the restart cadence is
   a real operational cost and differs per service (bifrost restarts
   cheaply, memex reloads GPU models). Record the choice and the reasoning.
9. **Set production TTLs.** S2's `default_ttl` 120s and `max_ttl` 300s
   exist to make expiry observable inside a test and are not production
   values (`deployments/applications/database-secrets-poc.tf:262-263`,
   `docs/postgres-vault-dynamic-creds-spike.md:378-379`). Pick real ones
   and say why. See Q2.
10. **Prove the untested half of failure mode 4.** S2 proved a dynamic user
    can CREATE and own new objects but never tested one MUTATING an object
    the static role already owns: no UPDATE, DELETE, or ALTER TABLE against
    a live application table
    (`docs/postgres-vault-dynamic-creds-spike.md:136-143`). R7 converts
    services that do exactly that on every request, so it must measure it.
11. **Keep the write-only credential chain intact** if it touches any part
    of it: `disable_read = true` on the KV2 admin secret
    (`deployments/applications/database-secrets-poc.tf:184-198`), the
    ephemeral password written by all its consumers in a single terraform
    run (`deployments/applications/database-secrets-poc.tf:39-53`), and
    `roles` named on the admin role. Note that a `roles`-only update with
    an unchanged `password_wo_version` is a no-op for the password
    (`deployments/applications/database-secrets-poc.tf:49-53`), so adding
    memberships does NOT require bumping the version. Bumping it
    needlessly re-writes the credential in three places at once.

Restrictions the repo enforces, each cited:

- **Surgical changes** (`CLAUDE.md` section 3): every changed line traces
  to this request. Do not refactor adjacent jobspecs or reformat
  `services.tf` while converting one service.
- **Surface forks, do not pick silently** (`CLAUDE.md` section 1): the
  open questions below are the operator's, not the loop's.
- **Gates through the task runner** (`.claude/rules/prek-code-quality.md`):
  run `just pre_commit`; never `--no-verify`; fix pre-existing failures
  rather than working around them
  (`.claude/rules/pre-existing-issues.md`).
- **Doc slop scan** (`.claude/rules/slop-scan-for-docs.md`): any markdown
  written or updated passes all three layers, and every backticked path
  resolves.
- **Plain language** (`.claude/rules/plain-language.md`) in comments,
  commit messages, and the doc.
- **Adversarial review** (`.claude/rules/adversarial-reviews.md`) before
  reporting done.
- **`git diff bootstrap/` stays empty.** The shared Ansible policy at
  `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2` is
  not this ticket's to widen.

## 7. Code surface

Exact files and anchors, each with the change in a clause.

**Terraform, applications root (`deployments/applications/`)**

- `deployments/applications/database-secrets-poc.tf:1-330` — **read as the
  working reference, then delete** if R3 has not. Every resource shape R7
  needs is here: the admin role (`:145-153`), the admin-option grant
  (`:172-182`), the write-only KV2 secret (`:188-198`), the mount
  (`:200-204`), the connection (`:210-224`), the DB role (`:251-264`), the
  dedicated policy (`:271-279`), and the dedicated JWT role (`:286-310`).
- **The Terraform file R3 created for the real engine** (name unknown until
  R3 lands, likely `deployments/applications/database.tf` or a sibling) —
  **edit**: add one `vault_database_secret_backend_role`, one
  `vault_policy`, and one `vault_jwt_auth_backend_role` per remaining
  service; extend the connection's `allowed_roles`; and, ONLY IF
  requirement 3's discovery shows the minting admin does not already cover
  the owner role, extend its grantable set. As of `a21da6f` that set is
  derived from `local.databases`
  (`deployments/applications/database-secrets-poc.tf:75`), so the likely
  correct edit is none at all. Do not hand-add names to a computed list.
- `deployments/applications/database.tf:56-67` — **edit, late**: drop the
  `random_password` entry and set `login = false` for each converted
  service's role, only after its cutover is proven. `:2-9` is the role
  list. `:69-77` shows each database's owner, which is why the role stays.
- `deployments/applications/secrets.tf:1-9,11-18,22-29,53-60,128-135` —
  **edit, late**: remove the converted service's per-role and per-app
  Postgres KV2 entries. Leave the two ducklake entries and every MinIO
  entry alone.
- `deployments/applications/services.tf:112-122,167-188,191-219,295-308` —
  **edit**: replace each converted job's `*_postgres_secret` templatefile
  variable with the `database/creds/<role>` path and the dedicated Vault
  role name.
- `deployments/applications/providers.tf:50-57` — **read only.** The
  `postgresql` provider authenticates as `localstack`; R7 does not touch
  it, and the exclusion in §5 is why.

**Nomad jobspecs (`deployments/applications/services/`)**

- `deployments/applications/services/memex.hcl:44,46-60` (db-migrate) and
  `:114,116-189` (memex) — **edit**: `vault { role = ... }` on both tasks,
  both Postgres blocks (`:52-55`, `:132-135`) rewritten to
  `.Data.username` / `.Data.password`, `change_mode` chosen. The MinIO,
  auth-key, and Bifrost-key blocks (`:124-127`, `:139-141`, `:156`) stay
  as they are and prove requirement 5.
- `deployments/applications/services/phoenix.hcl:57,59-66` — **edit**: the
  inline URL at `:61` becomes a dynamic-cred read.
- `deployments/applications/services/mlflow.hcl:45,47-60` — **edit**: same
  inline-URL shape at `:49`; the MinIO block at `:51-54` is untouched.
- `deployments/applications/services/bifrost.hcl:57,60-89` — **edit**: the
  `PG_USER` / `PG_PASSWORD` block at `:81-85` only. Leave config.json
  (`:94-151`) alone: it names `env.PG_USER` indirectly at `:134-137` and
  needs no change.
- `deployments/applications/services/poc-dynamic-creds.hcl:1-160` —
  **read**, then delete with the PoC Terraform file if it is still there.

**Read-only, cited so the implementer does not wander into them**

- `deployments/infrastructure/services/postgres.hcl:88-130` and
  `deployments/infrastructure/services/backup-postgres.hcl:29,36-37` —
  excluded root consumers.
- `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-9`
  — the shared policy R7 must not edit.
- `deployments/infrastructure/acme.tf:41-90` — the per-job JWT role
  pattern.
- `applications/migrations/justfile:7-11` — the static runner that stays.

**Docs**

- `docs/postgres-vault-dynamic-creds-spike.md:1-413` — **read**, the
  authority. Do not edit it: it is a dated record of a spike.
- **The migration doc R3 wrote.** Its path is R3's to choose and does not
  exist yet: R3's resolved fork Q4 names a `docs/rfcs/` directory that the
  repo does not have today (`docs/` holds `architecture/` and `notes/`).
  Find the real path in subticket 1, then **edit** it to mark each
  converted consumer done, record the per-service TTL and `change_mode`
  choices with reasons, record the measured result of requirement 10, and
  name the three exclusions with the ticket or plan that owns each.

## 8. Tests & validation gates

### Repo gate

`just pre_commit` (`justfile:17-19`) runs `pre-commit run --all-files`,
which is 14 hooks (`.pre-commit-config.yaml:1-73`). The four that bite
here:

- `nomad-fmt` (`.pre-commit-config.yaml:16-21`) on every edited `.hcl`.
- `terraform-fmt` (`.pre-commit-config.yaml:22-27`) on every edited `.tf`.
- `terraform-validate` (`.pre-commit-config.yaml:28-33`) runs
  `scripts/tf_validate.sh`, whose roots include `deployments/applications`
  (`scripts/tf_validate.sh:8-12`), offline with no state and no
  credentials.
- `end-of-file-fixer` (`.pre-commit-config.yaml:13`) on the doc.

Pass criterion: `just pre_commit` exits 0. No Python is touched, so the
ruff, mypy, and pytest hooks have no target here and
`.claude/rules/python-testing.md` has no code to cover. The verification
below is behavioral.

**Worktree setup, and a known gap.** `just worktree_setup <path>`
(`justfile:44-47`) symlinks `.ssh` and `.claude` and copies ONLY the
infrastructure tfvars. It does not copy
`deployments/applications/vars/prod.tfvars` or `.devcontainer/.env` (which
carries `CONSUL_TOKEN` for the Consul state backend); both are gitignored,
so a worktree has neither. `terraform validate` does not need them, but
every live apply from `deployments/applications/justfile` does. Copy both
by hand in a worktree.

### Live evals, per converted service

Substitute `<svc>` (service), `<role>` (Vault DB role), `<db>` (its
database), `<job>` (Nomad job id). Run the full set for each service, and
do not start the next service until the previous one passes.

1. **Role and connection.** `vault read database/roles/<role>` returns
   non-empty `creation_statements` including the `SET ROLE` statement, and
   the chosen production `default_ttl` / `max_ttl`.
   `vault read database/config/<name>` lists `<role>` in `allowed_roles`
   and shows `username` `vault-dbengine-admin`, never `localstack`.
2. **The credential mints and connects.**
   `vault read -format=json database/creds/<role>` returns a username, a
   password, and a `lease_id`. Capture them. `psql` is absent from the
   devcontainer, so connect with
   `docker run --rm -e PGPASSWORD=<pw> postgres:18 psql -h 192.168.2.30 -U
   <user> -d <db> -c 'select current_user, session_user'`. `current_user`
   must be the static owner role and `session_user` the minted user.
3. **The minted user does the app's work, including mutation (requirement
   10).** Against a table `<db>` already holds: a SELECT, then an UPDATE
   that sets a column to its own value and is rolled back
   (`begin; update <table> set <col> = <col> where <pk> = <known-id>;
   rollback;`), then `create table r7_probe(x int)`, check
   `select tableowner from pg_tables where tablename = 'r7_probe'` reads
   the static owner role, then `drop table r7_probe`. This is the half of
   failure mode 4 S2 left open
   (`docs/postgres-vault-dynamic-creds-spike.md:136-143`). Record the
   output.
4. **The service is healthy on the dynamic credential.**
   `nomad job status <job>` shows the alloc `running` with its health check
   passing: memex `/api/v1/health`
   (`deployments/applications/services/memex.hcl:78-83`), phoenix
   `/healthz` (`deployments/applications/services/phoenix.hcl:30-35`),
   mlflow `/health` (`deployments/applications/services/mlflow.hcl:27-32`),
   bifrost `/health` (`deployments/applications/services/bifrost.hcl:31-36`).
5. **Rotation is measured, not designed.** Revoke the live lease
   (`vault lease revoke -prefix database/creds/<role>`) or wait past
   `max_ttl`, then: the job returns to healthy on a new lease; the old
   username is gone
   (`select count(*) from pg_roles where rolname = '<old-user>'` returns 0,
   run as a role that is not the revoked one); the old credential is
   refused; and `nomad alloc logs <alloc>` shows no connection errors
   beyond the expected restart. Check the role count rather than trusting
   `vault lease revoke`, which reports success even when the DROP failed
   (`docs/postgres-vault-dynamic-creds-spike.md:110-118`).
6. **The dedicated policy is load-bearing and correctly scoped.** Positive:
   the job's own template renders (proven by 4). Negative: the same job
   with a bare `vault {}` blocks with
   `Missing: vault.read(database/creds/<role>)`, which is what S2's control
   showed (`docs/postgres-vault-dynamic-creds-spike.md:84-95`). Prove the
   negative once, on the first service R7 converts, rather than per
   service.
7. **The other KV grants survived (requirement 5).** For memex, mlflow, and
   bifrost, confirm the non-Postgres template blocks still render: the
   task starts, and `nomad alloc logs` shows no `Missing: vault.read(...)`
   for any KV path. A blocked template here is the predicted failure of
   the one-token trade-off.
8. **Nothing outside the converted service moved.**
   `git diff --stat bootstrap/` is empty. The unconverted services' jobs
   are still `running` and healthy.

### Docs and review

- Slop scan all three layers on the edited doc
  (`.claude/rules/slop-scan-for-docs.md`); every cited `path:line` resolves.
- Adversarial review before reporting done
  (`.claude/rules/adversarial-reviews.md`).

## 9. Risk assessment

**Blast radius, per service.** Each cutover risks exactly one service plus
the shared engine.

- **memex** is the worst. It holds the largest live dataset (S2 read 25,866
  rows from `entities`,
  `docs/postgres-vault-dynamic-creds-spike.md:66-78`), pools 20 connections
  with 30 overflow (`deployments/applications/services/memex.hcl:136-137`),
  runs a prestart migration that must succeed before the server starts, and
  restarts slowly because it loads ONNX and CUDA models
  (`deployments/applications/services/memex.hcl:168-177`). A bad cutover
  takes memex down and blocks hermes, which depends on it.
- **bifrost** is second: it is the LLM gateway every agent consumer routes
  through (`deployments/applications/services.tf:190-219`), and its
  `config_store` holds the governance virtual keys
  (`deployments/applications/services/bifrost.hcl:130-141`). Losing it
  takes memex's model calls with it.
- **mlflow and phoenix** are the cheap ones: tracking and observability
  UIs, no other service depends on them.
- **Shared surface.** Changing the minting admin's memberships or the
  connection's `allowed_roles` touches the engine every converted service
  now depends on, including R3's. A mistake there is cluster-wide, not
  per-service.

**Reversibility, per service.** Reversible while the static role still has
its password: revert the jobspec and the templatefile variable, re-apply,
and the job reads KV2 again. Irreversible once requirement 7 runs: after
`login = false` and the KV2 entries are gone, rollback means minting a new
static password and re-running the whole KV2 chain. Therefore: convert,
prove, wait, then de-privilege, in separate commits.

**Likeliest failure modes.**

1. **The other KV grants vanish.** The dedicated role omits
   `nomad-workloads` from `token_policies`, so memex's MinIO or auth-key
   template blocks forever and the task never starts. Mitigation:
   requirement 5, eval 7. This is the single most likely way to break a
   converted job.
2. **The minting admin lacks ADMIN OPTION on the new owner role.** Minting
   fails with `permission denied to grant role "<owner>" (SQLSTATE 42501)`
   at the next `vault read`, long after the terraform run reported success
   (`docs/postgres-vault-dynamic-creds-spike.md:216-220`). Mitigation:
   requirement 3's invariant check, eval 2. Note the failure is delayed by
   design of the engine, not by carelessness: nothing exercises the GRANT
   until a credential is actually minted, so `terraform apply` is green
   either way. Eval 2 is the only thing standing between this and a
   service that cannot get a credential.
3. **The `SET ROLE` statement is dropped from one role.** Revocation fails
   silently and revoked credentials keep working
   (`docs/postgres-vault-dynamic-creds-spike.md:97-134`). Mitigation:
   requirement 2, eval 5's role-count check.
4. **The template still reads `.Data.data.username`.** The credential
   renders empty and the app fails authentication at start
   (`deployments/applications/services/poc-dynamic-creds.hcl:30-31`).
   Mitigation: requirement 6, eval 4.
5. **A pooled connection outlives its lease under load.** memex looks
   healthy until it needs a connection it does not already hold, and the
   error arrives detached in time from the expiry that caused it
   (`docs/postgres-vault-dynamic-creds-spike.md:145-165`). Mitigation:
   requirement 8, eval 5.
6. **A dynamic user cannot mutate an object the static role owns.**
   Untested by S2. If it fails, every write path in the converted service
   fails and the ticket needs a grant redesign, not a patch. Mitigation:
   eval 3, run BEFORE the jobspec cutover for that service.
7. **The restart cadence is the outage.** With `change_mode = "restart"`
   the task restarts every `max_ttl`. A short TTL on memex means a GPU
   model reload several times a day. Mitigation: requirement 9, Q2.
8. **A stray full terraform run recreates the PoC job.** The PoC resources
   are still declared
   (`deployments/applications/database-secrets-poc.tf:14-19`). Mitigation:
   delete the file early (subticket 1).

## 10. Subtickets

Ordered and dependency-aware. If these become separate plan files, encode
the order in each file's `depends_on`.

1. **Discover R3's output and clean up the PoC.** Read the merged R3 plan,
   diff, and doc; read the live engine; write down which service is
   converted, the connection name, the role naming convention, and the TTL
   and `change_mode` R3 chose. Delete
   `deployments/applications/database-secrets-poc.tf` and
   `deployments/applications/services/poc-dynamic-creds.hcl` if R3 did not.
   Depends on: R3 done.
2. **Check the minting-admin invariant, and only then extend it.** Run the
   `pg_auth_members` query in requirement 3 first. As of commit `a21da6f`
   the grantable set is derived from `local.databases` and already covers
   all five owner roles, in which case this subticket is a no-op and says
   so. If R3 shipped a different admin, add the missing memberships and
   admin-option grants in one terraform run, with `replace_triggered_by`
   kept. Either way the check is the read-back, not the apply. Depends
   on: 1.
3. **Prove mutation on production tables (eval 3), for one service.** Mint
   a credential by hand against a new role for the cheapest service and run
   the SELECT, rolled-back UPDATE, and create/own/drop probe. This closes
   S2's open half BEFORE any jobspec changes. If it fails, stop and
   re-plan. Depends on: 2.
4. **Convert service 1 (cheapest restart: phoenix, or mlflow).** Vault DB
   role, policy, JWT role, jobspec rewrite, templatefile variable. Run
   evals 1 through 8, including the one-time negative control (eval 6).
   Depends on: 3.
5. **Convert service 2.** Same, evals 1 through 5 and 7. Depends on: 4.
6. **Convert service 3 (the expensive one: memex if R3 did not take it,
   else bifrost).** Same, plus the pool-specific parts of eval 5. Depends
   on: 5.
7. **De-privilege the static roles.** For each converted service only:
   `login = false`, remove `random_password` and both KV2 entries. Verify
   the service stays healthy and the static credential is refused. Depends
   on: 6, and on each service having run clean through at least one full
   rotation.
8. **Update the migration doc.** Per-service TTL and `change_mode` with
   reasons, the measured mutation result, and the three named exclusions
   with their owners. Depends on: 7.
9. **Slop scan, `just pre_commit`, adversarial review.** Depends on: 8.

## 11. Open questions

Settle Q1 through Q4 before the loop runs. Q5 through Q8 are the
implementation's to resolve but are listed so nothing is decided silently.

**Before settling any of these, note that R3's recorded blocker is stale.**
*(Added 2026-08-04.)* R3 is `blocked` with the headline "inlines S2's
conclusion but S2 never ran"; S2 is now `done` (commit `d394306`). R3 may
unblock more cheaply than this plan's dependency framing implies, which in
turn means less of R7 is genuinely unknown than the discovery-heavy
requirement 1 suggests.

- **Q1: one Vault connection for every service, or one per database?**
  S2's connection targets `/memex` in its `connection_url`
  (`deployments/applications/database-secrets-poc.tf:216`), but `CREATE
  ROLE`, `GRANT`, and `ALTER ROLE ... SET ROLE` are all cluster-wide, so
  the admin's connect database does not constrain which roles it can mint.
  *Recommendation:* ONE connection for all services, with every role in
  `allowed_roles`, and a name that is not `postgres-poc`. Renaming a Vault
  connection forces replacement, so R3 should own the rename. If R3 keeps
  `postgres-poc`, R7 renames it and re-points every role. Operator confirm,
  and check whether R3 already settled it.
- **Q2: production TTLs, and therefore the restart cadence.** With
  `change_mode = "restart"` the restart interval tracks `max_ttl`.
  *Recommendation:* `default_ttl` 1h and `max_ttl` 24h for phoenix and
  bifrost, which restart in seconds, and a longer `max_ttl` for memex (7d)
  because each restart reloads GPU models
  (`deployments/applications/services/memex.hcl:168-177`) and re-runs the
  prestart migration. A 7-day credential is still an enormous improvement
  on one that never rotates.

  **mlflow is not a cheap restart, and an earlier draft of this question
  said it was.** *(Corrected 2026-08-04.)*
  `deployments/applications/services/mlflow.hcl:38-41` runs
  `pip install --quiet --no-cache-dir psycopg2-binary boto3` on every task
  start, so a 24h `max_ttl` buys mlflow a daily PyPI fetch in its startup
  path, and a PyPI outage inside a rotation window becomes an mlflow
  outage. Three ways out, and this is a real operator fork rather than a
  detail: give mlflow the long `max_ttl` too (cheapest, least rotation);
  bake the two packages into an image so the restart really is seconds
  (correct, but it is a scope increase R7 does not otherwise need); or
  accept the daily fetch and say so. *Recommendation:* the long `max_ttl`
  for now, and file the image change separately rather than smuggling it
  into a credential ticket. Operator confirm.
- **Q3: memex's rotation strategy.** Restart, or pool `max_lifetime` below
  the lease TTL? The second avoids restarts but needs a memex config knob
  for pool connection lifetime. memex exposes `POOL_SIZE` and
  `MAX_OVERFLOW` (`deployments/applications/services/memex.hcl:136-137`)
  and it is NOT established that it exposes a recycle or lifetime setting.
  *Recommendation:* restart, per S2's ordered preference
  (`docs/postgres-vault-dynamic-creds-spike.md:167-178`), with a long
  `max_ttl` from Q2. Check for a lifetime knob during subticket 1. If one
  exists, raise it rather than switching unilaterally.
- **Q4: conversion order.** *Recommendation:* cheapest restart and
  smallest blast radius first (phoenix, then mlflow, then bifrost, then
  memex), among whichever R3 left. This inverts R3's deliberate
  "hardest first" call, and correctly so: R3 was proving the pattern and
  wanted the wrinkles early. R7 is repeating a proven pattern across live
  services and wants the cheap failures first. Operator confirm.
- **Q5: does the minting admin stay one shared identity, or does each
  service get its own?** *Recommendation:* one shared
  `vault-dbengine-admin` with memberships in every owner role. Per-service
  admins would multiply the long-lived credentials this work exists to
  reduce. R3's plan does not settle this. If R3 shipped per-service
  admins, follow R3.

  **Price the other side before confirming.** *(Added 2026-08-04.)* The
  shared admin must INHERIT every owner role it can mint for, because
  `inherit = false` breaks Vault's revocation silently (requirement 3, and
  the measurement recorded in
  `deployments/applications/database-secrets-poc.tf`). So once R7 lands,
  `vault-dbengine-admin` is a de-facto superuser across all five
  application databases, holding a credential that the write-only chain
  keeps out of Terraform state but that sits in KV2 at
  `default/postgres/vault-dbengine-admin` and does not itself rotate. The
  question is genuinely "one broad standing credential, or several narrow
  ones", not just a credential count — and the narrow option cannot use
  `noinherit` to get its narrowness either.
- **Q6: where do the new Terraform resources live?** R3 chose the file. If
  R3 put the engine in `deployments/infrastructure` and the roles in
  `deployments/applications` (its resolved fork Q2), R7 adds only to the
  applications root, since the `postgresql` provider exists only there
  (`deployments/applications/providers.tf:50-57`). *Recommendation:*
  follow R3's split exactly.
- **Q7: does R7 remove the `default/postgres/<role>` entries at
  `deployments/applications/secrets.tf:1-9` for converted services, or
  leave the whole `for_each` alone?** The resource is a single `for_each`
  over `random_password.password`, so removing one entry means removing its
  `random_password`. *Recommendation:* remove both, per requirement 7,
  which shrinks the `for_each` to the roles that are still static
  (ducklake_owner, ducklake_reader).
- **Q8: RESOLVED 2026-08-04 — `R8-rollout-postgres-root-consumers` owns
  the `localstack` root consumers.** Filed as a stub at
  `.loop/plans/R8-rollout-postgres-root-consumers.md` and registered in the
  ledger, covering `postgres-exporter`, `backup-postgres`, and the
  applications-root `postgresql` provider together, since S2 measured that
  rotating `localstack` breaks all three at once
  (`deployments/applications/database-secrets-poc.tf:78-82`). It
  `depends_on` R7 and is NOT in R7's own `depends_on`: it is downstream,
  not upstream. *(This question previously read "No ticket does today",
  contradicting §5's claim that a follow-up ticket owned it. §5 was the
  aspiration and Q8 was the truth; filing R8 makes them agree.)*

## Premises / assumptions

- **P1: R3 converts exactly one Postgres consumer and leaves the rest.**
  Anchor: `.loop/plans/R3-rollout-postgres-vault-db-creds.md:129-133`.
- **P2: R3's plan is currently blocked with a plan-review failure, so its
  final design may differ from what its plan file says today.** Anchor:
  `.loop/plans/R3-rollout-postgres-vault-db-creds.md:530-546`. probe:
  `loopctl ledger | grep R3-rollout`, captured 2026-08-04:
  `R3-rollout-postgres-vault-db-creds: blocked ... [unresolved-design-fork:
  plan review BROKEN/fail: ...]`. This is why requirement 1 is discovery
  and not a hardcoded list.
- **P3: exactly four application Nomad jobs read a static Postgres
  password from KV2: memex, phoenix, mlflow, bifrost.** Anchors:
  `deployments/applications/services/memex.hcl:52-55` and `:132-135`,
  `deployments/applications/services/phoenix.hcl:61`,
  `deployments/applications/services/mlflow.hcl:49`,
  `deployments/applications/services/bifrost.hcl:82-85`. probe:
  `grep -rn "postgres\|PG_USER" deployments/applications/services/*.hcl`,
  captured 2026-08-04: hits in exactly those four files plus the PoC
  jobspec.
- **P4: no Nomad job consumes `ducklake_owner` or `ducklake_reader`.**
  probe:
  `grep -rl ducklake deployments/applications/services deployments/infrastructure/services`,
  captured 2026-08-04: no matches. The roles exist only at
  `deployments/applications/database.tf:2-9`.
- **P5: `postgres-exporter` and `backup-postgres` both authenticate as the
  `localstack` root role.** Anchors:
  `deployments/infrastructure/services/postgres.hcl:122-130` fed from
  `deployments/infrastructure/services.tf:300-301`, and
  `deployments/infrastructure/services/backup-postgres.hcl:36-37` fed from
  `deployments/infrastructure/backup.tf:34-40`, whose `username` is
  literally `localstack` and whose password is
  `random_password.postgres_root`
  (`deployments/infrastructure/secrets.tf:69-79`).
- **P6: the shared `nomad-workloads` policy grants read only under
  `secret/data/<namespace>/<job_id>/`.** Anchor:
  `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-9`.
  probe: `vault policy read nomad-workloads`, captured 2026-08-04: three
  path rules, all templated on
  `identity.entity.aliases.auth_jwt_649fd6cc.metadata.nomad_namespace` and
  `...nomad_job_id`, with `read` on the data paths and `list` on metadata.
  No `database/` rule.
- **P7: a dedicated JWT role REPLACES `nomad-workloads` unless it lists it
  in `token_policies`.** Anchor:
  `deployments/infrastructure/acme.tf:56-61`. probe:
  `vault read auth/jwt-nomad/role/acme`, captured 2026-08-04:
  `token_policies [nomad-workloads acme-tls-write]`. Evidence for the
  failure it prevents: `docs/postgres-vault-dynamic-creds-spike.md:84-95`,
  where a bare `vault {}` produced
  `Missing: vault.read(database/creds/s2-poc)` and the task never started.
- **P8: every non-Postgres KV path the four jobs read sits under
  `default/<job_id>/`, so attaching `nomad-workloads` preserves them.**
  Anchors: `deployments/applications/services.tf:171-183` (memex reads
  `default/memex/minio`, `default/memex/auth`, `default/memex/bifrost`),
  `:300-301` (mlflow reads `default/mlflow/minio`), `:205-210` (bifrost
  reads six paths, all `default/bifrost/*`), `:116` (phoenix reads no other
  secret). Each job's Nomad `job` id equals that prefix:
  `deployments/applications/services/memex.hcl:1`,
  `deployments/applications/services/phoenix.hcl:1`,
  `deployments/applications/services/mlflow.hcl:1`,
  `deployments/applications/services/bifrost.hcl:1`.
- **P9: the `database` mount, connection `postgres-poc`, and role `s2-poc`
  are live, and the connection authenticates as `vault-dbengine-admin`
  against the `memex` database.** probe:
  `vault read database/config/postgres-poc`, captured 2026-08-04:
  `allowed_roles [s2-poc]`,
  `connection_url:postgresql://{{username}}:{{password}}@192.168.2.30:5432/memex?sslmode=disable`,
  `username:vault-dbengine-admin`, `plugin_name postgresql-database-plugin`.
  probe: `vault list database/roles`, captured: `s2-poc`. probe:
  `vault list auth/jwt-nomad/role`, captured: `acme`, `nomad-workloads`
  (the PoC JWT role is gone, as the spike doc records at
  `docs/postgres-vault-dynamic-creds-spike.md:404-407`).
- **P10: the minting admin must hold ADMIN OPTION on the owner role of
  every service it mints for, or minting fails at `vault read` time.**
  Evidence for the failure mode:
  `docs/postgres-vault-dynamic-creds-spike.md:216-220`. The current shape
  is `probe: select r.rolname, m.admin_option from pg_auth_members m join
  pg_roles r on m.roleid = r.oid join pg_roles g on m.member = g.oid where
  g.rolname = 'vault-dbengine-admin'`, which on 2026-08-04 returned all
  five owner roles with `admin_option = true`. The grantable set is derived
  at `deployments/applications/database-secrets-poc.tf:75` and consumed at
  `:149` and `:173`.

  *(Rewritten 2026-08-04. This premise previously asserted the admin held
  `memex` alone, which was true when the plan was authored and false by the
  time it was reviewed — commit `a21da6f` generalized it. The invariant is
  the durable claim; the membership list is discovery, per requirement 1.
  See `.loop/verdicts/R7-rollout-postgres-consumer-cutover.plan-validator.md`
  finding P10.)*
- **P10a: `inherit = false` is NOT available as a way to narrow that
  admin.** Under `noinherit`, Vault's `REVOKE ALL PRIVILEGES` and
  `DROP OWNED BY` both fail with permission denied, Vault reports
  `All revocation operations queued successfully!` anyway, and the role
  survives. Measured live 2026-08-04; recorded at
  `deployments/applications/database-secrets-poc.tf:121-144`. Consequence
  for Q5: the shared admin necessarily inherits every application's data
  privileges.
- **P11: `ALTER ROLE "{{name}}" SET ROLE "<owner>"` is mandatory or
  revocation fails silently while reporting success.** Source:
  `docs/postgres-vault-dynamic-creds-spike.md:97-134`, measured live
  2026-08-03. Applied form:
  `deployments/applications/database-secrets-poc.tf:257-260`.
- **P12: a dynamic-credential template reads `.Data.username`, not
  `.Data.data.username`.** Anchor:
  `deployments/applications/services/poc-dynamic-creds.hcl:30-35`.
- **P13: a HELD Postgres connection survives lease expiry, but a FRESH
  connect with an expired credential is refused.** Source:
  `docs/postgres-vault-dynamic-creds-spike.md:145-165`, measured live with
  a `psycopg_pool` idling 360s past a 300s `max_ttl`.
- **P14: a dynamic user MUTATING an object the static role already owns is
  UNTESTED.** Source: `docs/postgres-vault-dynamic-creds-spike.md:136-143`,
  which states no UPDATE, DELETE, or ALTER TABLE was run against a live
  memex table. Eval 3 measures it, before any jobspec changes.
  *(Corrected 2026-08-04: that same passage assigns the untested half to
  **R3**, not R7, so eval 3 may re-run work R3 already did. Keep it — it is
  a cheap check standing in front of a live cutover, and R7 must not
  assume R3 ran it.)*
- **P15: with `change_mode = "restart"` the task restart interval tracks
  the role's `max_ttl`, because Nomad renews a renewable lease until it
  cannot.** Partly UNCERTAIN: the renewal half is asserted at
  `deployments/applications/database-secrets-poc.tf:262-263` and the
  mitigation ordering at
  `docs/postgres-vault-dynamic-creds-spike.md:167-178`, but no measurement
  of the actual restart cadence on a long-running service exists. Eval 5
  measures it before Q2's TTLs are treated as settled.
- **P16: bifrost resolves `PG_USER` and `PG_PASSWORD` from process
  environment at startup, through indirection in config.json, so a
  credential change reaches it only via a task restart.** Anchors:
  `deployments/applications/services/bifrost.hcl:81-85` (rendered into
  `secrets/bifrost.env`, `env = true`) and `:134-137` (`"user":
  "env.PG_USER"`). The env template sets no `change_mode`, so it takes
  Nomad's default, restart.
- **P17: memex's `db-migrate` prestart task is a different thing from the
  golang-migrate runner.** Anchors:
  `deployments/applications/services/memex.hcl:24-42` runs the memex image
  with `["database", "upgrade"]` inside Nomad with a `vault {}` block,
  while `applications/migrations/justfile:7-11` runs `migrate -database
  ${POSTGRESQL_URL}` from a static env file outside Nomad, and its only
  migration is
  `applications/migrations/db/migrations/000001_create_ducklake_user.up.sql`.
  The first is in scope, the second is not.
- **P18: `just pre_commit` is the repo's single gate and validates the
  applications Terraform root.** Anchors: `justfile:17-19`,
  `.pre-commit-config.yaml:16-33`, `scripts/tf_validate.sh:8-12`. probe:
  `command -v nomad terraform pre-commit`, captured 2026-08-04: all three
  resolve.
- **P19: `just worktree_setup` seeds only the infrastructure tfvars, so a
  worktree lacks the applications tfvars and `CONSUL_TOKEN`.** Anchor:
  `justfile:44-47`. probe:
  `git check-ignore -v deployments/applications/vars/prod.tfvars .devcontainer/.env`,
  captured 2026-08-04: both are ignored, by `.gitignore:12` and
  `.gitignore:2`. `terraform validate` does not read them, but a live
  apply does.
- **P20: `psql` is not installed in the devcontainer.** probe:
  `command -v psql`, captured 2026-08-04: no output. Run it from a
  throwaway `postgres:18` container or from inside an alloc, as
  `docs/postgres-vault-dynamic-creds-spike.md:291-293` says. The exact
  invocation is in section 8.
- **P21: static Postgres roles cannot be dropped, only de-privileged,
  because each owns its database.** Anchor:
  `deployments/applications/database.tf:69-77`, where
  `postgresql_database.database` sets `owner` to the static role, and
  `deployments/applications/database-secrets-poc.tf:257-260`, where the
  dynamic user's grants come from membership in that same role.
- **P22: a `roles`-only update to the minting admin does not rewrite its
  password, so adding memberships needs no version bump.** Anchor:
  `deployments/applications/database-secrets-poc.tf:49-53`, which states
  that an unchanged version on an existing resource is a genuine no-op and
  that the hazard is a resource being created or whose version moved.
