# R3-rollout-postgres-vault-db-creds: roll out short-lived Vault-minted Postgres credentials (Path A)

## 1. Title

Replace static, long-lived Postgres passwords (Terraform-generated,
stored in Vault KV2) with short-lived, keyless credentials minted by
Vault's database secrets engine against PG18, delivered to Nomad jobs
through Workload-Identity auth and rotated automatically. Prove it
end-to-end on at least one real service and document the migration
path for the rest.

## 2. Size / Effort

**L.** The change spans three layers and two Terraform root modules,
adds a Vault secrets engine that does not exist today, rewrites the
Vault-templating contract in every consuming Nomad job, and must solve
a live-system rotation wrinkle (connection pools outliving their
credentials) without an outage window. The size driver is breadth and
the migration sequencing, not algorithmic difficulty: each converted
service is a small diff, but there are several, they touch a running
cluster, and the cutover per service is irreversible in practice
(the old static role is dropped). A partial rollout (one service
converted, the rest documented) is an explicit acceptance target
precisely because doing all of them at once is too large and too risky
for one ticket.

## 3. Triggered by

Auth epic. Confirmed decisions: Vault is the OIDC provider for humans
(Zitadel dropped), Nomad Workload-Identity JWTs are machine identity.
This ticket **implements the outcome of S2** (the Postgres/Vault-creds
spike) along **Path A** — the mature, recommended path using Vault's
native database secrets engine — and **depends on F1** (the
Nomad-WI-to-Vault trust) already being in place. Today every service's
Postgres password is a 16-character static string generated once by
Terraform and read from KV2; it never rotates and is identical across
restarts. R3 removes that class of secret for Postgres.

## 4. Context

Today's state, cited. Every Postgres consumer authenticates with a
static password.

- **The Postgres job.** PG18 (pgvector image) runs as a single Nomad
  service constrained to `firebat`, static port 5432:
  `deployments/infrastructure/services/postgres.hcl:1` (job),
  `postgres.hcl:9` (firebat), `postgres.hcl:13` (static 5432),
  `postgres.hcl:47` (`POSTGRES_DB=localstack`), `postgres.hcl:52`
  (`pgvector/pgvector:pg18-trixie`). The Postgres task itself pulls its
  own superuser creds from KV2 via a `vault {}` + `template` block:
  `postgres.hcl:70-80`. The `postgres-exporter` sidecar also uses a
  static KV2 DSN: `postgres.hcl:122-130`.
- **The only Vault engine that exists is KV2.** The single
  `vault_mount` is the KV2 mount: `deployments/infrastructure/secrets.tf:2-7`
  (`vault_mount.kvv2`). There is **no** database secrets engine, and no
  Terraform `vault_database_secret_backend_*` resource anywhere
  (confirmed by search). The Postgres superuser/root credential that a
  database engine would rotate against lives in KV2 at
  `secret/default/postgres/localstack`, user `localstack`:
  `deployments/infrastructure/secrets.tf:68-88`.
- **Static roles and static KV2 creds (the applications layer).** The
  per-service login roles are created with a Terraform-generated
  password: `deployments/applications/database.tf:2-8` (role list:
  `ducklake_owner`, `ducklake_reader`, `memex`, `phoenix`, `mlflow`),
  `database.tf:47-51` (`random_password.password`), `database.tf:53-58`
  (`postgresql_role.role`, `login = true`). The databases they own:
  `database.tf:9-30`, `database.tf:60-68`. Those passwords are then
  written to KV2, one entry per consumer:
  `deployments/applications/secrets.tf:1-9`
  (`postgres_credentials`, `default/postgres/<role>`),
  `secrets.tf:11-18` (`phoenix`, `default/phoenix/postgres`),
  `secrets.tf:22-29` (`memex`, `default/memex/postgres`),
  `secrets.tf:53-60` (`mlflow`, `default/mlflow/postgres`).
- **How jobs consume the static creds.** Each service job renders a
  Postgres URL from its KV2 entry via `vault {}` + `template`:
  `deployments/applications/services/phoenix.hcl:57-66`,
  `deployments/applications/services/mlflow.hcl:45-60`,
  `deployments/applications/services/memex.hcl:44-60` (the `db-migrate`
  prestart task) and `memex.hcl:114-135` (the long-running `memex`
  task). The KV2 path is injected as a templatefile variable from
  `deployments/applications/services.tf:97-107` (phoenix),
  `services.tf:147-163` (memex), `services.tf:186-200` (mlflow).
- **The Postgres Terraform provider itself uses a static admin creds
  path** read from KV2 at plan/apply time:
  `deployments/applications/providers.tf:46-53`, sourced from the
  ephemeral admin secret at `services.tf:16-19`. The Vault provider
  version is `~>5.3.0` in both roots
  (`deployments/applications/providers.tf:7-10`,
  `deployments/infrastructure/providers.tf:7-10`), which supports the
  `vault_database_secret_backend_connection` and
  `vault_database_secret_backend_role` resources this ticket needs.
- **F1 (the dependency) as it exists today.** Nomad servers are
  configured to issue Workload-Identity JWTs to Vault:
  `bootstrap/roles/nomad_server/templates/nomad.hcl.j2:37-46`
  (`vault { default_identity { aud = ["vault.io"] } }`). Vault trusts
  them through the `jwt-nomad` auth method and a `nomad-workloads`
  role: `bootstrap/roles/nomad_server/tasks/main.yml:207-245`,
  `bootstrap/roles/nomad_server/files/vault_role_nomad_workloads.json`
  (binds `aud=vault.io`, `user_claim=/nomad_job_id`, attaches policy
  `nomad-workloads`). **This is the load-bearing gap for R3:** the
  `nomad-workloads` Vault policy grants read only on
  `secret/data/<namespace>/<job_id>/*` and `bootstrap/*` —
  `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-24`.
  It grants **no** access to a `database/creds/<role>` path. A job's WI
  token cannot read dynamic DB creds until that policy is extended.
- **Migrations.** Schema changes run through golang-migrate:
  `applications/migrations/justfile` (`up`/`down`, `migrate -database
  ${POSTGRESQL_URL}`), `applications/migrations/db/migrations/000001_create_ducklake_user.up.sql`.
  This path uses `POSTGRESQL_URL` from `applications/migrations/.env`,
  a static connection string outside the Nomad/Vault flow.

What is wrong/missing: Postgres credentials never rotate, are minted
once and stored at rest in KV2 indefinitely, and are shared verbatim
by every restart of a job. There is no database secrets engine to mint
short-lived creds, no Vault policy path that would let a WI token read
them, and no rotation strategy for the connection pools that would hold
an expiring credential.

## 5. Non-goals / out of scope

- **Not converting every consumer.** The success bar is one real
  service end-to-end plus a documented path for the rest. Converting
  all of memex, phoenix, mlflow, the exporter, and the migrations
  runner in this ticket is explicitly out of scope; pick the safest
  single service to prove the pattern (see Open Questions Q1).
- **Not Path B.** S2 evaluated alternatives; this ticket commits to
  Path A (native database secrets engine). Do not build a custom
  rotation lambda, a sidecar credential broker, or a
  self-managed-rotation KV2 scheme.
- **Not changing the OIDC/human-auth design.** Human interactive access
  via Vault OIDC to the same `database/creds` path is in scope as a
  documented flow (Requirement 5), but standing up or reconfiguring the
  OIDC auth method itself is a separate epic ticket.
- **Not migrating the migrations runner's connection string** unless it
  falls out for free. `applications/migrations/.env` static
  `POSTGRESQL_URL` may stay static; note it explicitly rather than
  silently converting it.
- **Not touching PG18 tuning, ports, storage, or the exporter's
  metrics scope.** Only the credential source changes.
- **No Zitadel.** It was dropped from the auth design; any reference is
  a factual error.

## 6. Requirements & restrictions

The change MUST:

1. **Enable and configure the Vault database secrets engine against
   PG18.** A new mount (recommended `database/`, see Q2), a
   `vault_database_secret_backend_connection` pointing at
   `postgres-db` on firebat:5432 (`postgres.hcl:13`), authenticating
   with the existing superuser credential from
   `deployments/infrastructure/secrets.tf:68-88`, and an
   `allowed_roles` list. Decide and document whether Vault rotates the
   connection's root password (`rotate-root`) — if it does, Terraform
   and any other reader of `secret/default/postgres/localstack` can no
   longer use that credential (see Risk and Q3).
2. **Define one Vault DB role per consuming service**
   (`vault_database_secret_backend_role`) with least-privilege
   `creation_statements` / `revocation_statements`. Each dynamic user
   must land with exactly the grants the static role has today
   (owner vs reader — mirror `database.tf:60-68` and the reader grants
   at `database.tf:88-96`), and SCRAM password auth must work against
   PG18. Role naming must align with the per-job Vault convention so
   the policy in requirement 3 can be templated by `nomad_job_id`
   (the `user_claim` at
   `bootstrap/roles/nomad_server/files/vault_role_nomad_workloads.json`).
3. **Extend the `nomad-workloads` Vault policy** so a job's WI token
   can read `database/creds/<role>` for its own service, mirroring the
   existing per-job scoping in
   `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-24`.
   This is the F1 gap and is mandatory: without it the converted job
   gets a 403.
4. **Convert the chosen service's Nomad job** from the static KV2
   `template` block to a dynamic one that reads
   `database/creds/<role>` and renders username/password into the same
   env contract the app already expects (e.g. `phoenix.hcl:61`,
   `mlflow.hcl:49`, `memex.hcl:52-55`). The Vault template lease must
   drive credential renewal.
5. **Solve the connection-pool rotation wrinkle surfaced by S2.** A
   pooled client (memex sets `POOL_SIZE=20` / `MAX_OVERFLOW=30` at
   `memex.hcl:136-137`) holds connections whose credential will expire.
   Choose and document a coherent strategy: role `max_ttl` vs pool
   connection lifetime / `pool_recycle`, and the template `change_mode`
   (`restart` vs `signal`) so the app re-reads creds and re-pools
   before the lease dies. The chosen service must survive at least one
   full credential rotation without erroring.
6. **Document the human path.** Vault OIDC to the same
   `database/creds/<role>` for interactive DB access, as prose in the
   migration doc — the pattern, the role(s) a human maps to, and the
   `vault read database/creds/<role>` flow.
7. **Document the migration path for the remaining consumers** and
   name any that must stay static (candidates: the Terraform
   `postgresql` provider admin creds at `providers.tf:46-53`, and the
   golang-migrate runner) with the reason.

Restrictions the repo enforces (each cited):

- **Simplicity / no speculative build** (`CLAUDE.md` sections 2-3):
  minimum code that solves the problem; surgical changes; match
  existing style. Do not refactor the untouched service jobs while
  converting one.
- **Think before coding / surface forks** (`CLAUDE.md` section 1):
  present the layer-ownership and rotate-root forks (Open Questions),
  do not pick silently.
- **Gate discovery, not assumption** (`.claude/rules/prek-code-quality.md`):
  run the change through `just`, discover checks from
  `.pre-commit-config.yaml`; never `--no-verify`.
- **Docs slop scan** (`.claude/rules/slop-scan-for-docs.md`): the
  migration doc is markdown and must pass all three layers — no
  identity leaks, no hallucinated paths/identifiers, thesis-first,
  American spelling, 80-char wrap, em-dash budget. Every backticked
  path must resolve.
- **Adversarial review** (`.claude/rules/adversarial-reviews.md`):
  hand the finished change to a review sub-agent before declaring done.
- **Never reference Zitadel** — dropped from the auth design.

## 7. Code surface

Exact files and anchors, each with the change in a clause.

- `deployments/infrastructure/secrets.tf:2-7` — **read** as the model
  for a Vault engine mount; the new database-engine mount + connection
  + roles are added here (or in a new `database.tf` in this root; see
  Q2). `secrets.tf:68-88` — the superuser credential the connection
  authenticates with; note the rotate-root implication.
- `deployments/infrastructure/services/postgres.hcl:1,13,47,52` —
  **read** as the connection target (host/port/db/image) for the engine
  config. Optionally `postgres.hcl:70-80` and `:122-130` are candidate
  conversions (Postgres's own task and the exporter), but likely stay
  on the bootstrap superuser creds; if not converted, state why.
- `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2:1-24`
  — **edit**: add a `database/creds/<...>` read path scoped per
  `nomad_job_id`, mirroring the existing KV2 per-job scoping. This is
  the F1-gap fix.
- `bootstrap/roles/nomad_server/files/vault_role_nomad_workloads.json`
  — **read** for the claim/metadata shape the policy templates against.
- `deployments/applications/database.tf:2-8,53-68,88-96` — **read** as
  the source of truth for each role's grants; the Vault DB role
  `creation_statements` must reproduce these. If the static
  `postgresql_role` for a converted service is removed, do it here and
  clean the orphaned `random_password` / KV2 entry.
- `deployments/applications/secrets.tf:1-9,11-18,22-29,53-60` —
  **edit** for the converted service only: remove its static KV2
  Postgres entry once the job no longer reads it (surgical; leave the
  others).
- `deployments/applications/services/<chosen>.hcl` (one of
  `phoenix.hcl:57-66`, `mlflow.hcl:45-60`, `memex.hcl:44-60` +
  `:114-135`) — **edit**: swap the static `with secret` template for a
  `database/creds/<role>` read, set `change_mode` per requirement 5.
- `deployments/applications/services.tf:97-107,147-163,186-200` —
  **edit** for the converted service: replace the KV2 `*_secret`
  templatefile var (or repoint it at the `database/creds` path)
  consistent with the job edit.
- `deployments/applications/providers.tf:46-53` — **read**; if
  rotate-root is enabled this admin credential source must change.
  Flag, do not silently convert.
- `applications/migrations/justfile`, `applications/migrations/.env`
  (`POSTGRESQL_URL`) — **read**; document whether the migrations runner
  stays static.
- **CREATE** a migration/design doc (recommended
  `docs/notes/postgres-vault-dynamic-creds.md`, see Q4) covering the
  rotation strategy, the human OIDC path, and the per-consumer
  migration plan.

## 8. Tests & validation gates

### Repo gate (terraform-aware)

- **`just pre_commit`** (root `justfile:16-18` →
  `pre-commit run --all-files`) is the single blessed gate and now
  validates Terraform, so there is no separate manual `terraform
  validate` step. Configured hooks (`.pre-commit-config.yaml`):
  check-json, check-ast, check-merge-conflict, check-yaml (`--unsafe`),
  debug-statements, detect-private-key, end-of-file-fixer, and three
  local hooks — `nomad-fmt` (`nomad fmt -recursive` on `*.hcl`,
  lines 16-21), `terraform-fmt` (`terraform fmt -check -recursive` on
  `types: [terraform]`, lines 22-27), and `terraform-validate`
  (`scripts/tf_validate.sh`, lines 28-33). `scripts/tf_validate.sh`
  runs `terraform validate` on each root — `deployments/infrastructure`,
  `deployments/applications`, and `deployments/applications/modules/bucket`
  — offline (`init -backend=false`, no Consul state, no credentials), so
  the engine/role/policy `.tf` edits in both touched roots are validated
  by the gate itself.
- **Pass criteria:** `just pre_commit` exits 0. Every edited `.hcl` is
  `nomad fmt`-clean; every edited `.tf` is `terraform fmt`-clean and
  `terraform validate`-clean in its root; the new doc satisfies
  end-of-file-fixer and does not trip detect-private-key.
  `.pre-commit-config.yaml:1` excludes `^\.(claude|loop)/`, so this
  ticket file is not linted, but files under `deployments/`,
  `bootstrap/`, and `docs/` are.
- **No unit-test framework applies to this change.** This is Terraform
  + Nomad HCL + Ansible + a doc; there is no Python package and no
  `pytest` suite in the touched paths, so
  `.claude/rules/python-testing.md` (`all-code-needs-tests`) has no
  code target here. The verification is behavioral, below.

### Evals (live cluster)

The cluster is reachable and the acceptance below is runnable from this
environment: `VAULT_ADDR`, `VAULT_TOKEN`, `NOMAD_ADDR`, `NOMAD_TOKEN`,
and `CONSUL_HTTP_ADDR` are all set. These evals depend on **F1** (the
Nomad-WI-to-Vault trust) being deployed and on the **S2** Path A design;
run them against the converted service chosen in Q1 (recommended
phoenix). Substitute `<name>` (connection), `<role>` (Vault DB role),
`<db>` (owned database), and `<job>` (Nomad job id) for the chosen
service. Command + expected result each:

These scenarios are captured as the loop eval marker at
`.loop/evals/R3-rollout-postgres-vault-db-creds.md` (the five-column
scored contract the loop-reviewer judges against).

1. **Engine + connection exist.**
   `vault read database/config/<name>`
   — returns the connection config (plugin `postgresql-database-plugin`,
   `connection_url` targeting `firebat:5432`, `allowed_roles` including
   `<role>`). Non-existent mount/connection → the eval fails.
2. **Role exists.**
   `vault read database/roles/<role>`
   — returns the role with non-empty `creation_statements` /
   `revocation_statements` and the chosen `default_ttl` / `max_ttl`
   (Q5). Confirms requirement 2 is applied.
3. **Dynamic credential mints.**
   `vault read -format=json database/creds/<role>`
   — returns a fresh `data.username` / `data.password` with a
   `lease_id` and a `lease_duration` matching the role TTL. Capture the
   username (e.g. `v-token-<role>-…`) for steps 4-5.
4. **Minted user connects to PG18 with least privilege.**
   `psql "postgres://<user>:<pw>@firebat:5432/<db>" -c 'select 1'`
   — returns `1`. Then prove the grant boundary: an action the static
   role does NOT hold is denied. For a reader role,
   `psql "postgres://<user>:<pw>@firebat:5432/<db>" -c 'create table
   r3_probe(x int)'`
   — fails with `ERROR: permission denied`. For an owner role, a
   cross-schema/forbidden object is denied instead. The dynamic user's
   grants must match `database.tf:60-68` (owner) / `database.tf:88-96`
   (reader) exactly — no more.
5. **Converted service is healthy on the dynamic cred.**
   `nomad job status <job>`
   — the alloc is `running` and its health check passes (`phoenix`
   `/healthz`, `mlflow` `/health`, `memex` `/api/v1/health`). Confirms
   the job reads `database/creds/<role>` and the app connects
   (requirement 4).
6. **Rotation is proven, not just designed (the pool wrinkle).** Force
   or wait out one full lease cycle (revoke the lease with
   `vault lease revoke -prefix database/creds/<role>`, or wait past
   `max_ttl`), then re-run `nomad job status <job>` and the health
   check — the service reconnects on a new lease with **no** connection
   errors in `nomad alloc logs <alloc>`. Then confirm the OLD username
   captured in step 3 is revoked:
   `psql "postgres://<old-user>:<old-pw>@firebat:5432/<db>" -c 'select 1'`
   — fails with an authentication/`role does not exist` error. This
   validates requirement 5 (the `max_ttl` vs `pool_recycle` /
   `change_mode` choice) end-to-end.
7. **The extended `nomad-workloads` policy actually permits the path.**
   Positive: the converted job's WI token can read `database/creds/<role>`
   (proven transitively by step 5, or directly by minting a WI token and
   `vault read database/creds/<role>` under it). Negative: a job carrying
   the **old**, un-extended `nomad-workloads` policy is denied with a
   403 / `permission denied` on `database/creds/<role>`. This proves the
   policy edit at
   `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`
   is load-bearing and correctly scoped per `nomad_job_id`
   (requirement 3, the F1 gap).

### Docs and review

- **Doc slop scan** (`.claude/rules/slop-scan-for-docs.md`): run all
  three layers on the new doc; verify every cited `path:line` resolves.
- **Adversarial review** (`.claude/rules/adversarial-reviews.md`)
  before reporting done.

## 9. Risk assessment

- **Blast radius.** Medium-high for the converted service, low for the
  rest. The Vault engine + policy edits are cluster-wide surface: a
  wrong `revocation_statement` or an over-broad grant affects
  Postgres directly. The policy edit at
  `vault_nomad_workloads.hcl.j2` is applied to **all** Nomad workloads;
  a malformed template breaks WI-to-Vault for every job, not just the
  converted one.
- **Reversibility.** The Terraform engine/role/policy changes revert by
  `terraform destroy`/`apply` of those resources. The **per-service
  cutover is effectively one-way**: once the static `postgresql_role`
  and its KV2 entry are removed, rolling back means re-creating the
  static role and password. Keep the old static path in place until the
  dynamic path is proven, then remove in a follow-up — do not delete
  the static role in the same step that adds the dynamic one.
- **Likeliest failure modes:**
  1. **F1 gap missed** — job gets dynamic creds template but a 403,
     because the `nomad-workloads` policy was not extended
     (`vault_nomad_workloads.hcl.j2`). Mitigation: requirement 3 and
     acceptance check 4.
  2. **rotate-root foot-gun** — enabling Vault root rotation on the
     connection invalidates the `localstack` superuser password that
     the Terraform `postgresql` provider (`providers.tf:46-53`), the
     Postgres exporter (`postgres.hcl:122-130`), and the migrations
     runner still use. Mitigation: Q3 — decide rotate-root explicitly;
     if enabled, migrate those readers or use a dedicated
     Vault-managed rotation user, not the shared superuser.
  3. **Pool holds an expiring credential** — the app pools connections
     past the lease TTL and errors on the next reconnect. Mitigation:
     requirement 5 and acceptance check 3.
  4. **SCRAM / creation-statement mismatch** — dynamic user lacks a
     grant the app needs, or ownership differs from the static role, so
     migrations or writes fail. Mitigation: reproduce
     `database.tf:60-68,88-96` grants exactly; test with the real app.
  5. **`nomad fmt` / slop-scan gate failure** on edited HCL or the new
     doc. Mitigation: run `just pre_commit` before done.

## 10. Subtickets

Ordered, dependency-aware.

1. **Enable + configure the database secrets engine.** Add the mount,
   `vault_database_secret_backend_connection` against `postgres-db`
   firebat:5432, `allowed_roles`, authenticating with the superuser
   creds. Decide rotate-root (Q3). Verify `vault read database/config`.
   Depends on: nothing (F1 already deployed).
2. **Define the DB role(s)** with least-privilege creation/revocation
   statements mirroring `database.tf` grants; verify
   `vault read database/creds/<role>` mints a working user. Depends
   on: 1.
3. **Extend the `nomad-workloads` Vault policy** for per-job
   `database/creds/<role>` read; re-apply via the bootstrap role.
   Verify a WI token reads its role and is denied others. Depends
   on: 2.
4. **Convert one service job** (the chosen safest one) to the dynamic
   template, with the pool-rotation `change_mode` / TTL strategy.
   Depends on: 3.
5. **Prove rotation end-to-end** — health check green, survives a full
   lease rotation, old policy denied (acceptance checks 1-4). Depends
   on: 4.
6. **Remove the converted service's static role + KV2 entry**
   (`database.tf`, `secrets.tf`) and its orphaned `random_password`,
   only after 5 passes. Depends on: 5.
7. **Write the migration + human-OIDC doc**, naming the consumers that
   stay static and why. Depends on: 1-6.
8. **Slop scan + adversarial review**; run `just pre_commit`. Depends
   on: 7.

## 11. Open questions

Settle Q1-Q4 before the loop runs; Q5-Q6 are for the implementation to
resolve and are listed so the loop does not decide them silently.

- **Q1 — Which single service is the first conversion?**
  *Recommendation:* **phoenix**. It has the simplest job
  (`phoenix.hcl:57-66`, one task, one Postgres URL, no prestart
  migrate, no pool-size env), so the pool wrinkle is minimal and the
  blast radius is one observability UI. memex is the worst first
  choice (explicit `POOL_SIZE=20`/`MAX_OVERFLOW=30` at
  `memex.hcl:136-137`, a prestart `db-migrate`, GPU constraints) —
  convert it later as the pool-wrinkle proof, not first. Operator
  confirm.
- **Q2 — Which Terraform root owns the database engine and roles?**
  The KV2 mount and the Postgres superuser secret live in
  `deployments/infrastructure` (`secrets.tf:2-7,68-88`), but the
  per-service roles and databases live in `deployments/applications`
  (`database.tf`), which also has the `postgresql` provider. *Recommendation:*
  put the **engine mount + connection** in `infrastructure` (it is
  core, alongside the KV2 mount and the root secret it authenticates
  with) and the **per-service DB roles** in `applications` (next to
  the databases and grants they mirror). Note the cross-root
  dependency. Operator confirm.
- **Q3 — Enable Vault rotate-root on the connection?** If yes, Vault
  owns the `localstack` superuser password and the current readers
  (`providers.tf:46-53`, `postgres.hcl:122-130`, migrations `.env`)
  break. *Recommendation:* **do not rotate-root in this ticket.** Use
  a dedicated Vault-management user or leave the superuser static and
  document rotate-root as a follow-up, to keep the Terraform provider,
  exporter, and migrations runner working. Surface as a tradeoff.
- **Q4 — Where does the migration doc live?** *Recommendation:*
  `docs/notes/postgres-vault-dynamic-creds.md`, consistent with the
  S1 evaluation note placement under `docs/notes/`. Operator confirm.
- **Q5 — max_ttl / default_ttl for the DB roles, and the pool
  reconnect strategy.** For the implementation to choose and document
  (requirement 5): the TTL must exceed a comfortable reconnect window
  but stay short enough to be meaningful; `change_mode = "restart"` is
  the simplest correct default for a stateless service, `pool_recycle`
  below `max_ttl` for a pooled one. Do not pick silently — record the
  choice and the reasoning in the doc.
- **Q6 — Does the golang-migrate runner get dynamic creds or stay
  static?** For the implementation to resolve and state explicitly in
  the doc (requirement 7). *Leaning:* stay static for now (it runs
  outside Nomad/WI, from `applications/migrations/.env`), and note it
  as a known remaining static consumer.
