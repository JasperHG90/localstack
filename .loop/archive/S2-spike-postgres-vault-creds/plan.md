---
epic = "spike"
depends_on = []
priority = 35
summary = "Spike: prove Vault's database secrets engine minting short-lived Postgres users on the existing PG18, consumed by a Nomad job via Workload Identity, and write up the credential-rotation-in-pools failure mode. Deliverable is a decision doc plus a proof of concept, not the rollout (that is R3)."
tags = ["spike", "postgres", "vault", "secrets"]
---

# Ticket: S2-spike-postgres-vault-creds

## 1. Title

Prove out Vault's database secrets engine minting short-lived Postgres
users on the existing PG18 on firebat, consumed by a Nomad job via Nomad
Workload Identity, and document the credential-rotation-in-pools wrinkle.
Deliverable is a decision doc plus a working proof-of-concept, not a
rollout.

## 2. Size / Effort

**M (spike, time-boxed).** Effort is driven by three things: (a) standing
up a new Vault secrets engine and a per-job Vault authorization path that
does not exist yet against a live cluster, (b) authoring a throwaway PoC
Nomad job that reads `database/creds/<role>` instead of a KV path, and (c)
the investigative write-up of the rotation-in-connection-pools failure
mode. The code surface is small; the cost is the live proof and the
analysis.

This is a spike. Success is proving the mechanism and writing the findings
down, NOT migrating any real service. Full rollout is ticket R3 and is
explicitly out of scope here (see Non-goals).

## 3. Triggered by

The home-lab auth epic. Confirmed decisions: Vault is the OIDC IdP for
humans and Nomad Workload Identity (WI) JWTs are the machine identity.
Today every Postgres consumer holds a long-lived static password minted by
Terraform and parked in Vault KV2 (see Context). The epic wants
short-lived, Vault-brokered Postgres credentials. This ticket is the spike
that decides whether Path A (Vault database secrets engine) is the path,
and surfaces the wrinkles before R3 commits to a rollout. It shares
findings with S1 (Boundary), which would broker these same Vault-issued
Postgres creds — see "What S2 hands S1" for the artifact S2 leaves
standing for it.

## 4. Context

Today's Postgres auth is entirely static, long-lived passwords:

- The Postgres job runs on firebat, image `pgvector/pgvector:pg18-trixie`,
  static port 5432, at `deployments/infrastructure/services/postgres.hcl:52`
  and `:13-16`, pinned to firebat at `:7-10`.
- The admin/root role password is a Terraform `random_password` written
  once to Vault KV2 at `deployments/infrastructure/secrets.tf:69` and
  `:74-88` (key `default/postgres/localstack`). The KV2 mount itself is
  defined at `deployments/infrastructure/secrets.tf:2-7`.
- The Postgres job reads that static credential back through a
  Vault-templated `template { env = true }` block at
  `deployments/infrastructure/services/postgres.hcl:70-80` (the `vault {}`
  block at `:70`, the template at `:72-80`). The job is rendered by
  `nomad_job.postgres` which passes the KV path in at
  `deployments/infrastructure/services.tf:298-302`.
- Per-application roles (memex, phoenix, mlflow, ducklake_*) are also
  static `random_password` logins created by the PostgreSQL provider at
  `deployments/applications/database.tf:56-67` (`random_password.password`
  at `:56-60`, `postgresql_role.role` at `:62-67`), with their passwords
  copied into KV2 at `deployments/applications/secrets.tf:1-9` and per-app
  keys following it.
- Application jobs consume those static passwords the same way, e.g.
  `deployments/applications/services/memex.hcl:44` (`vault {}`) and
  `:46-54` (template reading `.Data.data.password`).

The machine-identity plumbing the spike will build on already exists:

- Nomad WI is wired to Vault as a JWT auth method `jwt-nomad` with default
  role `nomad-workloads`, configured in
  `bootstrap/roles/nomad_server/tasks/main.yml:207-242`.
- That role issues `service` tokens with policy `nomad-workloads`, period
  30m, defined at
  `bootstrap/roles/nomad_server/files/vault_role_nomad_workloads.json`.
- The `nomad-workloads` Vault policy is templated at
  `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`.
  **It grants read on `secret/data/<namespace>/<job_id>` and
  `secret/data/<namespace>/<job_id>/*`, plus `list` on
  `secret/metadata/<namespace>/*`, and nothing else.** F9 removed the
  broader bootstrap-mount grants; the template says so at
  `vault_nomad_workloads.hcl.j2:13-21`. **It grants no `database/` path of
  any kind.** This is the central wrinkle: a Nomad job cannot read dynamic
  DB creds until it is authorized on `database/creds/<role>`.

What is wrong / missing: there is no `database` secrets engine mounted, no
Vault DB connection config pointing at firebat's Postgres, no role that
mints short-lived users, and no Vault authorization path that would let a
Nomad workload read `database/creds/<role>`. Nothing proves the mechanism
works against PG18, and nobody has measured what happens to a long-lived
connection pool when its lease expires.

## 5. Non-goals / out of scope

- **No rollout.** Do not migrate memex, phoenix, mlflow, ducklake, the
  exporter sidecar, or the root role off their static KV2 passwords. That
  is ticket R3.
- **Do not delete or rewrite** the existing static-credential resources
  (`deployments/infrastructure/secrets.tf`,
  `deployments/applications/database.tf`, the KV reads in the job HCLs).
  The PoC runs alongside them.
- **No writes to real application data.** Requirement 2's grant test reads
  an existing app table and round-trips through a scratch table it creates
  and drops (§6 requirement 2). It must not INSERT, UPDATE or DELETE rows
  in any table an application owns.
- **No human OIDC path implementation.** The doc should note that humans
  reach `database/creds/<role>` via Vault OIDC login, but implementing or
  testing the OIDC login flow is out of scope for this spike.
- **Path B is not built.** PostgreSQL 18 native OAuth bearer auth (`oauth`
  HBA method + validator module + device flow) is investigated on paper
  only (§6 requirement 1). Do not add an `oauth` HBA entry or a validator
  module.
- **No Boundary work.** S1 owns Boundary; this ticket records the shared
  finding and leaves S1 a standing credential engine (see "What S2 hands
  S1").
- **No production password rotation** of the existing static roots, and no
  Vault-managed root rotation on the PoC connection.

## 6. Requirements & restrictions

Must achieve:

1. A decision doc that **reaches** a recommendation, rather than one
   mandated here. *(Corrected 2026-07-25: three places in this plan
   previously required the doc to "recommend Path A", and the eval's rubric
   supplied the Path B rejection rationale as the expected answer. A spike
   whose conclusion is fixed in advance cannot de-risk anything — it can
   only fail on a broken command.)* The doc must:
   - state the **falsifier** up front: the concrete observation under which
     R3 should NOT proceed with Path A. The obvious candidate is
     requirement 2's grant test — if a dynamically minted user cannot be
     given the grants and ownership an app needs without unacceptable
     `creation_statements` complexity, Path A is not viable and R3 must not
     be unblocked on it;
   - record a real Path B evidence step, **time-boxed to one hour**: name
     the PG18 OAuth validator module searched for, establish whether one
     exists that accepts Vault- or Nomad-issued JWTs, and record the answer
     with a citation. If the hour produces no answer, record "not
     established within the time box" — that is an honest result. Rejecting
     Path B on a rationale nobody checked is not;
   - capture the rotation findings per requirement 3.
2. A working PoC, proven against the live firebat Postgres, of: the Vault
   `database` secrets engine enabled, a Vault DB connection to PG18, a role
   that mints a short-lived Postgres user, and a Nomad job that reads
   `database/creds/<role>` via Nomad WI and connects to Postgres with the
   minted credential.
   **The connection test must be a privileged operation against a real
   owned object, not `select 1`.** `select 1` needs only CONNECT and passes
   for a role with zero object privileges, so it proves authentication and
   nothing about viability. Point the PoC role at one real app database
   (memex or ducklake) and write `creation_statements` — a REQUIRED
   attribute of `vault_database_secret_backend_role` — that reproduce the
   grants that role needs. Then assert two things:
   - a `SELECT` against an existing table owned by the static app role
     (read-only, zero blast radius);
   - a `CREATE TABLE` / `INSERT` / `SELECT` / `DROP TABLE` round-trip on a
     scratch table `s2_poc_scratch` in the same database, which is what a
     migration actually does. Ownership of the scratch table is itself a
     finding: record whether it lands on the ephemeral user or the static
     role, because that is R3's problem.

   **State the gap this leaves.** These two assertions do not cover a
   dynamic user *modifying* an object the static role owns — writing rows,
   or running `ALTER TABLE` against an app-owned table. That is R3's
   failure mode 4 word for word
   (`.loop/plans/R3-rollout-postgres-vault-db-creds.md:411-414`), and §5
   forbids it here because the blast radius is a live application database.
   The doc must say plainly which half of failure mode 4 the spike settled
   (grants and ownership on new objects) and which half R3 still carries
   (mutating existing app-owned objects), so R3 does not read this spike as
   more than it is.

   This is the ticket's hardest unknown: the applications layer owns every
   app object under a static role
   (`deployments/applications/database.tf:69-72`, `postgresql_database` with
   `owner = postgresql_role.role[each.value.owner].name` at `:72`), and R3
   names exactly this as its failure mode 4 — *"dynamic user lacks a grant
   the app needs, or ownership differs from the static role, so migrations
   or writes fail"*
   (`.loop/plans/R3-rollout-postgres-vault-db-creds.md:411-414`). A spike
   that declares Path A proven while handing this to R3 undiminished has
   done nothing.
3. An explicit test of the known wrinkle: a long-lived connection pool
   holding a credential whose lease expires. Record the observed failure
   mode and the mitigation options.
   **Set a short `max_ttl` on the PoC role, not just `default_ttl`.**
   Nomad's template runner renews a renewable Vault lease continuously, so
   a dynamic DB credential expires at `max_ttl` — unset, that is Vault's
   768h default, and the test renews quietly for 32 days and reports
   nothing.
   **The pool needs a named subject.** The PoC job carries a second task
   running `docker.io/library/python:3.12-slim` with `psycopg[binary,pool]`
   installed at start: open a pool with `min_size=1`, hold it idle past
   `max_ttl`, then check out and issue a query. Log the result on both the
   held connection and a fresh checkout. A `psql` loop is not a pool — each
   invocation opens a new connection and cannot exhibit the failure.

Restrictions the repo enforces (cite where stated):

- **Secret-path convention.** Follow the epic convention
  `secret/data/<namespace>/<job_id>/<entry>` for any KV touch, and mirror
  the existing dynamic-secrets path style.
- **DO NOT grant `database/creds/*` by editing the shared Ansible policy.**
  *(Corrected 2026-07-25; correction finished 2026-08-03 after the
  plan-validator found it had reached only §6 and §7.)* Editing
  `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2`
  would give every Nomad workload on the cluster read access to
  `database/creds/*` — for a throwaway spike — and require two live Ansible
  bootstrap re-runs, apply then revert. F3 already shipped the alternative
  with the opposite answer: `deployments/infrastructure/acme.tf:51-65`
  makes the case in its comment, that the job gets its own JWT role and its
  own policy as a second role on the Ansible-owned mount, selected per-job
  via `vault { role = ... }`, leaving every other workload on the default
  role untouched. Mirror it: `vault_policy` +
  `vault_jwt_auth_backend_role` bound to the PoC job,
  `vault { role = ... }` in the jobspec, shared policy untouched.
  **`git diff bootstrap/` must be empty at the end of this ticket** (eval
  row 5, 100% threshold).
- **Record the one-token trade-off as a spike finding for R3.** A Nomad
  task performs a single JWT login and holds a single Vault token, so a
  dedicated role's policy REPLACES `nomad-workloads` rather than adding to
  it (`deployments/infrastructure/acme.tf:51-65`) — unless the dedicated
  role lists `nomad-workloads` in its own `token_policies`, which
  `acme.tf:66-90` does. Either way a converted job's role must ALSO carry
  the KV grants it still needs (memex's `db-migrate` prestart, mlflow,
  phoenix). "Widen the shared policy" versus "per-job role that must
  re-grant KV" is precisely the decision a spike should make for R3, and
  neither option is free.
- **Never hardcode credentials; all secrets in Vault KV2** (CLAUDE.md, Key
  Conventions). The Vault DB connection authenticates as the dedicated
  `vault-dbengine-admin` Postgres role created by this ticket (§10
  subticket 2), never as the real `localstack` root.
- **Podman, not Docker**, on cluster nodes (CLAUDE.md). The PoC job uses
  `driver = "podman"`, matching
  `deployments/infrastructure/services/postgres.hcl:31`.
- **Terraform state is in Consul**
  (`deployments/applications/backend.tf`); providers `vault ~>5.3.0`,
  `nomad ~>2.5.0` and `postgresql ~>1.26.0` are already declared at
  `deployments/applications/providers.tf:1-31`. Reuse them; do not add a
  new provider.
- **Injection pattern.** Any job reads secrets via `vault {}` +
  `template { env = true }`, as in
  `deployments/infrastructure/services/postgres.hcl:70-80` and
  `deployments/applications/services/memex.hcl:44-54`. The PoC must not
  invent a different mechanism.
- **Surgical changes** (CLAUDE.md §3): touch only what the PoC needs; do
  not "improve" adjacent static-credential code.
- **Docs are held to the slop-scan rule**
  (`.claude/rules/slop-scan-for-docs.md`): the decision doc must be
  thesis-first, evidence-backed, and free of the banned patterns. Prose
  wraps at 80 chars.

## 7. Code surface

New or changed files. Anchors are the existing patterns to mirror.

**Layer: `deployments/applications/`, not `deployments/infrastructure/`.**
*(Resolved 2026-08-03, OQ3.)* The applications root is the only one with a
`postgresql` provider (`deployments/applications/providers.tf:50-57`;
`grep -n postgresql deployments/infrastructure/*.tf` returns nothing), it
already reads the Postgres admin credential ephemerally
(`deployments/applications/services.tf:16-19`), and it owns the app roles
and databases the grant test targets
(`deployments/applications/database.tf:56-72`). Creating
`vault-dbengine-admin` in applications while configuring the Vault
connection in infrastructure would put a cross-root ordering constraint on
a throwaway spike. One root removes it. `deployments/applications` is a
`terraform-validate` root (`scripts/tf_validate.sh:8-12`), so the gate
still covers the new file.

- `docs/postgres-vault-dynamic-creds-spike.md` — **new.** The decision
  doc: the falsifier, the Path A evidence, the Path B investigation
  result, the PoC runbook, the grant/ownership finding, and the
  rotation-in-pools findings. Sits alongside existing design docs such as
  `docs/credential-rotation.md` (same directory, same audience).
- `deployments/applications/database-secrets-poc.tf` — **new, PoC,
  clearly labelled throwaway.** Carries four things:
  1. `postgresql_role.vault_dbengine_admin` — the dedicated minting admin,
     `create_role = true`, `login = true`, and `roles` listing the app
     owner roles it must be a member of so the users it mints can be
     granted on app-owned objects (requirement 2).
     **Its password never enters state.** Do NOT copy
     `deployments/applications/database.tf:56-67`, which uses
     `random_password` + `postgresql_role.password` and writes the result
     to `terraform.tfstate` in plaintext. Use the write-only chain instead
     (see item 2).
  2. **The state-free credential chain.** *(Added 2026-08-03. The previous
     draft fed `password_wo` from `random_password...result` and told R3 the
     credential "never enters state" — false, because `random_password`
     stores `result` in state. The whole OQ3 exception rests on that claim,
     so the chain has to be true.)* All four links exist in the pinned
     providers — probed with `terraform providers schema -json` against a
     scratch root:
     - `ephemeral "random_password"` (random 3.9.0) generates the value;
     - `postgresql_role.password_wo` + `password_wo_version`
       (cyrilgdn 1.26.0) sets it on the role;
     - `vault_kv_secret_v2.data_json_wo` + `data_json_wo_version`
       (vault 5.3.0) copies it to KV2 under the epic's path convention;
     - the connection's `postgresql { password_wo, password_wo_version }`
       (vault 5.3.0) hands it to the database engine.

     **The three `_wo_version` values must be bumped together in one
     apply**, or the role's password and the copies desync. The same
     applies to a single link being replaced on its own: recreating any one
     of the three hands it a freshly generated password while the other two
     keep the old one. The connection fails loudly if that happens
     (`verify_connection` defaults true and §7 forbids disabling it), but
     the KV2 copy would go stale in silence. On any replacement of one link,
     bump all three versions. Write them from
     a single `local` so one edit moves all three. An ephemeral value is
     regenerated every run but only *written* when its version changes, so
     an unchanged version is a no-op, not a rotation.
  3. `vault_mount` for the `database` engine plus
     `vault_database_secret_backend_connection.postgres_poc`, taking the
     credential from the chain above. Feeding an ephemeral value into an
     ordinary resource attribute is a hard Terraform error;
     `deployments/applications/services.tf:11-19` and
     `deployments/applications/providers.tf:50-57` are *provider
     configuration*, the one context where ephemeral values are
     unconditionally legal, so that pattern does not transfer here — the
     write-only attributes are what make it legal on a resource.
     **`connection_url` still needs its `{{username}}` and `{{password}}`
     templates** — "keep the credential out of `connection_url`" means no
     literal secret, NOT dropping the templates. A config missing
     `{{password}}` passes `terraform validate` and then fails to
     authenticate against firebat.
     Do NOT set `verify_connection = false` to paper over a failure, and do
     NOT enable Vault-managed root rotation.
  4. `vault_database_secret_backend_role.poc` with `creation_statements`
     (a REQUIRED attribute), a short `default_ttl`, and a short **`max_ttl`**
     (requirement 3).
  5. The authorization: a `vault_policy` granting `read` on
     `database/creds/<poc-role>` only, plus a `vault_jwt_auth_backend_role`
     on backend `jwt-nomad` bound to the PoC job's `nomad_job_id` /
     `nomad_namespace`, with `claim_mappings` replicated and
     `token_policies` including `nomad-workloads`. Mirror
     `deployments/infrastructure/acme.tf:41-90` exactly.

  Reuse `var.secret_mount` and the vault provider at
  `deployments/applications/providers.tf:36`.
- `deployments/applications/services/poc-dynamic-creds.hcl` — **new,
  throwaway PoC Nomad job.** `driver = "podman"`, with `vault { role = ... }`
  selecting the dedicated JWT role (pattern
  `deployments/infrastructure/services/acme.hcl:73-75`) and a
  `template { env = true }` block reading
  `{{ with secret "database/creds/<role>" }}`, modeled on
  `deployments/infrastructure/services/postgres.hcl:70-80`. Two tasks:
  one that runs the grant test (requirement 2), one that runs the pooling
  client (requirement 3). Rendered by a `nomad_job` resource mirroring
  `deployments/infrastructure/services.tf:298-302`.
- `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2` —
  **DO NOT MODIFY.** Editing the shared policy grants every workload on
  the cluster `database/creds/*` and needs two live Ansible re-runs. The
  per-job pattern above replaces it, and eval row 5 checks
  `git diff bootstrap/` is empty.

## 8. Tests & validation gates

**Prerequisite in a worktree:** run `just worktree_setup <path>`
(`justfile:41-43`) BEFORE the first gate, or `terraform-validate` dies on
the gitignored `.ssh/id_rsa` that
`deployments/infrastructure/services.tf:290` evaluates — a failure
unrelated to this ticket. The hook has `pass_filenames: false`, so it runs
on every gate invocation regardless of what S2 touched.

**Environment gap: `psql` is NOT installed here.** `which psql` returns
nothing, and neither `.devcontainer/Dockerfile` nor `bootstrap.sh` installs
a Postgres client. Requirement 2's connection test therefore cannot run as
a bare `psql` invocation. Docker-in-docker is enabled, so
`docker run --rm postgres:18 psql ...` works from the devcontainer; the
in-alloc tasks run their own client images. Name whichever mechanism each
check uses.

**Repo gate (what the loop runs):** `just pre_commit` runs
`pre-commit run --all-files` (root `justfile:18-19`). The hooks in
`.pre-commit-config.yaml` include Terraform validation, so the PoC `.tf` is
gated, not just formatted:

- `nomad-fmt` (`nomad fmt -recursive`) on `*.hcl`
  (`.pre-commit-config.yaml:16-21`) formats the PoC Nomad job.
- `terraform-fmt` (`terraform fmt -check -recursive`,
  `.pre-commit-config.yaml:22-27`) fails on unformatted `.tf`.
- `terraform-validate` (`scripts/tf_validate.sh`,
  `.pre-commit-config.yaml:28-33`) runs `terraform validate` per root, and
  `deployments/applications` is one of the three roots it validates
  (`scripts/tf_validate.sh:8-12`). It inits with `-backend=false`, so it
  validates offline without touching the Consul backend or credentials.
  The new `database-secrets-poc.tf` must be syntactically valid and
  internally consistent for the gate to pass.
- The generic hooks (`check-json`, `check-ast`, `check-merge-conflict`,
  `check-yaml --unsafe`, `debug-statements`, `detect-private-key`,
  `end-of-file-fixer`) still apply.

`.pre-commit-config.yaml:1` excludes `^\.(claude|loop)/`, so the new `.hcl`
and `.tf` files ARE checked while the ticket file is not.

**Decision-doc gate.** The new `docs/postgres-vault-dynamic-creds-spike.md`
is held to the markdown slop-scan (`.claude/rules/slop-scan-for-docs.md`):
run the three layers (P0 critical patterns, document economy, sentence
slop), verify prose wraps at 80 chars, and confirm `end-of-file-fixer`
leaves a trailing newline. The doc must be thesis-first — stating whatever
conclusion the evidence supports, NOT a pre-mandated one — and every
backticked identifier and cited path must resolve.

**Evals (live PoC acceptance).** The cluster is reachable this run:
`VAULT_ADDR`, `VAULT_TOKEN`, `NOMAD_ADDR`, `NOMAD_TOKEN`, and
`CONSUL_HTTP_ADDR` are set in the environment. The PoC is therefore proven
live, not merely documented. Run each check below and record its result in
the decision doc.

1. **DB engine + connection exist against PG18 on firebat.**
   Command: `vault read database/config/<poc-conn>`.
   Expect: the connection config prints with `plugin_name`
   `postgresql-database-plugin` and an `allowed_roles` list containing the
   PoC role; no error. Confirms the engine is mounted and points at
   firebat PG18.
2. **The connection authenticates as the dedicated admin, not the root.**
   Command: `vault read database/config/<poc-conn>`, inspect `username`.
   Expect: `vault-dbengine-admin`, NOT `localstack`, and no Vault-managed
   root rotation enabled. This is the outage guard: rotating the
   `localstack` root would break the postgres_exporter,
   `backup-postgres`'s `pg_dumpall`, and the applications-layer provider,
   all of which authenticate as `localstack`.
3. **A PoC role mints a short-lived user, bounded by `max_ttl`.**
   Commands: `vault read database/creds/<poc-role>`, then
   `vault read database/roles/<poc-role>`.
   Expect: a fresh `username`/`password` pair plus a non-zero `lease_id`
   and a short `lease_duration`, AND an explicit short `max_ttl` on the
   role. Without `max_ttl` the lease renews to Vault's 768h default and
   check 6 cannot fire.
4. **The minted user can do the app's work, not merely connect.**
   Commands: with the minted credential against the chosen app database
   (memex or ducklake), via `docker run --rm postgres:18 psql ...` or from
   inside the PoC alloc — a `SELECT` on an existing table owned by the
   static app role, then a `CREATE TABLE s2_poc_scratch` / `INSERT` /
   `SELECT` / `DROP TABLE` round-trip.
   Expect: both succeed, demonstrating that `creation_statements`
   reproduced the grants and ownership the app needs. A bare `select 1`
   does NOT satisfy this check. **Failure here is a legitimate spike
   outcome and must be recorded as such, not worked around**: it is the
   falsifier for Path A and would mean R3 should not proceed. Record which
   role owns `s2_poc_scratch` after creation.
5. **The PoC job reads creds through a DEDICATED JWT role, shared policy
   untouched.**
   Commands: run the PoC job, `nomad job status <poc-job>`, then
   `git diff bootstrap/`.
   Expect: the `vault_policy` + `vault_jwt_auth_backend_role` exist
   (pattern `deployments/infrastructure/acme.tf:41-90`), the jobspec
   selects the role with `vault { role = ... }`, the alloc reaches
   `running`, its template renders, and it connects with the minted user.
   `git diff bootstrap/` is **empty**.
   **The before/after denial test runs against the per-job role, not the
   shared policy.** Run the job once with the `vault { role = ... }` stanza
   omitted, so it falls back to the default `nomad-workloads` role, and
   observe the template failing with a 403 on `database/creds/<role>`.
   Then run it with the stanza present and observe it render. That proves
   the dedicated authorization is load-bearing without touching
   `bootstrap/`.
6. **Rotation-in-pools wrinkle is exercised and recorded.**
   Command/setup: the pooling task (§6 requirement 3) holds an idle pooled
   connection past `max_ttl`, Vault revokes the lease, then the task checks
   out from the pool and queries.
   Expect: record the observed behavior for the held connection and for a
   fresh checkout after revocation, plus at least one mitigation (Nomad
   `change_mode = "restart"`/`"signal"` on the template, pool
   `max_lifetime` below the lease TTL, or app-level reconnect-on-auth-
   error). An inconclusive result counts ONLY if the doc shows `max_ttl`
   was short enough for the lease to have expired inside the window. This
   is the spike's central finding; characterize it, do not fix it.
7. **Doc deliverables exist.** The decision doc records the falsifier, the
   results of checks 1-6, the Path B investigation result with a citation,
   the one-token trade-off finding for R3, and a recommendation that
   follows from the recorded evidence in whichever direction it points.

**Cleanup, and it runs LAST.** Every eval check that observes a live
resource must be run and its result written into the decision doc BEFORE
anything is destroyed. Check 5 scores `nomad job status <poc-job>` as
`running`, so tearing the job down first makes that check unscoreable.
Order: run checks 1-6, record them, then destroy the throwaway Nomad
job, its `vault_policy` and its
`vault_jwt_auth_backend_role`, and drop `s2_poc_scratch`. **Leave the
`database` mount, the connection, the PoC role and `vault-dbengine-admin`
standing** — S1 needs them (see "What S2 hands S1"). `bootstrap/` is never
touched, so there is nothing to revert there.

On completion return "done" plus a one-line summary naming which checks
passed live and what the rotation test observed.

**Eval marker.** The Definition-of-Done scenarios for these gates live at
`.loop/evals/S2-spike-postgres-vault-creds.md`. Its 2026-07-25 rewrite is
stricter than the plan it scores and its rows stand. One correction landed
2026-08-03: row 5 named `deployments/infrastructure/database-secrets-poc.tf`
and now names the applications path, following the layer decision in §7.

## 9. Risk assessment

- **The minting admin identity.** The database engine needs a Postgres
  role that can create users. Pointing the connection at the real
  `localstack` root and letting Vault rotate it would break every existing
  static consumer that authenticates as `localstack`. Mitigation:
  `vault-dbengine-admin` is a dedicated role (§10 subticket 2), Vault root
  rotation stays off, and eval row 2 checks it deterministically at 100%.
- **Writing into a live application database.** *(Added 2026-08-03; the
  risk section had not been updated for corrected requirement 2.)*
  Requirement 2 runs against a real app database — memex or ducklake — on
  the live firebat Postgres. Blast radius is bounded three ways: the
  existing-table assertion is a `SELECT` only; the write path uses a
  scratch table `s2_poc_scratch` this ticket creates and drops; and §5
  forbids INSERT/UPDATE/DELETE against any app-owned table. Residual risk:
  a `creation_statements` typo could grant the ephemeral user more than
  intended inside that database. Review the rendered statements before
  apply, and prefer ducklake over memex if either database is less
  load-bearing.
- **New Vault mount on a live server.** Mounting a `database` engine and
  creating a role is additive. The per-job `vault_policy` and
  `vault_jwt_auth_backend_role` are bound to one job id, so no other
  workload's authorization changes — that is the whole point of the F3
  pattern over the shared-policy edit.
- **Reversibility.** High. The throwaway job, policy and JWT role are
  destroyed at cleanup and `bootstrap/` is never edited. The engine,
  connection, PoC role and `vault-dbengine-admin` deliberately survive for
  S1 (see "What S2 hands S1"); if S1 is dropped, `terraform destroy
  -target` on those four
  resources plus `DROP ROLE vault-dbengine-admin` removes them.
- **Likeliest failure modes.**
  1. The grant test fails because the ephemeral user cannot act on
     objects owned by the static role. This is the falsifier, not a bug to
     work around — record it and do not unblock R3 on Path A.
  2. `connection_url` is written without its `{{password}}` template; the
     config validates and then fails to authenticate against firebat.
  3. `nomad fmt` or `terraform fmt` reformats the PoC files and the loop
     must re-run the gate.
  4. The rotation test is inconclusive because the pool's client silently
     reconnects, masking the failure — force an idle-past-`max_ttl`
     condition and log both the held connection and a fresh checkout.

## 10. Subtickets

Ordered, dependency-aware.

1. **Decision-doc skeleton.** Create
   `docs/postgres-vault-dynamic-creds-spike.md` with the **falsifier stated
   up front** (requirement 1), the Path A vs. Path B comparison, and
   placeholder sections for the PoC runbook, the grant/ownership result,
   the Path B investigation, and the rotation findings. The conclusion is
   written LAST, after the evidence exists. Verify: doc passes slop-scan
   layers and `end-of-file-fixer`.
2. **The minting admin, on the state-free credential chain.** In
   `deployments/applications/database-secrets-poc.tf`, add
   `postgresql_role.vault_dbengine_admin` with `create_role = true`,
   `login = true`, and membership in the app owner roles. Its password
   comes from `ephemeral "random_password"` through `password_wo` +
   `password_wo_version`, with the KV2 copy on `data_json_wo` +
   `data_json_wo_version`. Do NOT mirror
   `deployments/applications/database.tf:56-67`, which puts the password in
   state. Drive all three `_wo_version` values from one `local`.
   Verify: `just pre_commit` green; `terraform apply` creates the role;
   `\du` shows `CREATEROLE` and the memberships;
   `terraform state pull | grep -c <the-password>` is 0, and no `result`
   or `data_json` attribute in state holds it. The state lives in the
   Consul backend, so `state pull` is the only way to read it — there is no
   local `terraform.tfstate` to grep.
3. **PoC Terraform: engine, connection, role.** Same file: `vault_mount`
   for `database`, `vault_database_secret_backend_connection.postgres_poc`
   taking the credential from subticket 2's chain via
   `postgresql { password_wo, password_wo_version }` and a `connection_url` that
   keeps its `{{username}}`/`{{password}}` templates, and
   `vault_database_secret_backend_role.poc` with `creation_statements`, a
   short `default_ttl` and a short `max_ttl`. Verify: `just pre_commit`
   green; `vault read database/config/<poc-conn>` and
   `vault read database/creds/<poc-role>` both succeed (eval checks 1-3).
4. **Per-job authorization.** *(New 2026-08-03; §7 required these and eval
   row 5 scores them, but no subticket built them.)* Same file: a
   `vault_policy` scoped to `read` on `database/creds/<poc-role>` and a
   `vault_jwt_auth_backend_role` on backend `jwt-nomad` bound to the PoC
   job, mirroring `deployments/infrastructure/acme.tf:41-90` including
   `claim_mappings` and `token_policies`. Verify: `vault policy read`
   shows exactly the one path; `git diff bootstrap/` empty.
5. **PoC Nomad job + grant test.** Add
   `deployments/applications/services/poc-dynamic-creds.hcl` and its
   `nomad_job` resource. Task 1 reads `database/creds/<poc-role>` via
   `vault { role = ... }` + `template { env = true }` and runs the
   requirement 2 assertions (`SELECT` on an app-owned table, then the
   `s2_poc_scratch` round-trip). Verify: `nomad fmt` clean; the alloc
   reaches `running`; run once WITHOUT the `vault { role = ... }` stanza to
   observe the 403 on `database/creds/<poc-role>`, then WITH it to observe
   the render (eval checks 4-5). Record which role owns the scratch table.
6. **Rotation-in-pools test + findings.** *(Subject named 2026-08-03.)*
   Add task 2 to the PoC job: `docker.io/library/python:3.12-slim` with
   `psycopg[binary,pool]`, `min_size=1`, holding an idle connection past
   `max_ttl`, then checking out and querying. Write the observed failure
   mode and mitigation options into the doc. Verify: findings section names
   the concrete failure for both the held connection and a fresh checkout,
   and at least one mitigation (eval check 6).
7. **Path B investigation.** Time-boxed to one hour: search for a PG18
   OAuth validator module that accepts Vault- or Nomad-issued JWTs, record
   what was searched and what was found, with a citation. Verify: the doc's
   Path B section names a module or states "not established within the time
   box" — never a bare assertion.
8. **Cleanup + doc finalize.** Destroy the throwaway job, its
   `vault_policy` and `vault_jwt_auth_backend_role`; drop
   `s2_poc_scratch`. Leave the engine, connection, PoC role and
   `vault-dbengine-admin` standing for S1 (see "What S2 hands S1").
   Finalize the decision doc
   with the recommendation the evidence supports, the one-token trade-off
   finding, and the runbook. Verify: `just pre_commit` green;
   `git diff bootstrap/` empty; doc complete.

## Premises / assumptions

Verified by the plan-validator on 2026-08-03 unless noted.

- **P1.** Today's Postgres auth is entirely static passwords generated at
  apply time and parked in KV2, consumed via `vault {}` +
  `template { env = true }`.
  *Evidence:* `deployments/infrastructure/secrets.tf:74-88`,
  `deployments/infrastructure/services/postgres.hcl:70-80`,
  `deployments/applications/database.tf:56-67`,
  `deployments/applications/secrets.tf:1-9`,
  `deployments/applications/services/memex.hcl:44-54`.
- **P2.** The shared `nomad-workloads` Vault policy grants no `database/`
  path, so a Nomad job cannot read dynamic DB creds until it is authorized
  separately.
  *Evidence:*
  `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2` is
  21 lines and contains only three `secret/` paths.
- **P3.** F3's per-job JWT role is the shipped alternative to editing the
  shared policy, and it carries the one-token argument in its own comment.
  *Evidence:* `deployments/infrastructure/acme.tf:41-49` (`vault_policy`),
  `:51-65` (the comment), `:66-90` (`vault_jwt_auth_backend_role` with
  `bound_claims`, `claim_mappings`, `token_policies`),
  `deployments/infrastructure/services/acme.hcl:73-75`
  (`vault { role = ... }`).
- **P4.** `password_wo` and `password_wo_version` exist on
  `vault_database_secret_backend_connection` in the pinned vault 5.3.0
  provider, and feeding an ephemeral value into an ordinary attribute is a
  hard error.
  *Evidence:* probed against the local provider mirror —
  `password = ephemeral...` gives `Error: Invalid use of ephemeral value
  ... not an assignable attribute`; `password_wo = ephemeral...`
  validates.
- **P5.** `creation_statements` is a required argument of
  `vault_database_secret_backend_role`; `default_ttl` and `max_ttl` both
  validate on it.
  *Evidence:* probed — omitting it gives `Error: Missing required
  argument`.
- **P6.** Without a short `max_ttl` the rotation test cannot fire, because
  Nomad's template runner renews a renewable Vault lease until `max_ttl`,
  falling back to Vault's 768h system default when unset.
  *Evidence:*
  `.loop/verdicts/S2-spike-postgres-vault-creds.plan-validator.md`, whose
  premise P6 checked this claim and upheld it.
- **P7.** The cluster is reachable from this environment (`VAULT_ADDR`,
  `NOMAD_ADDR`, `CONSUL_HTTP_ADDR` and their tokens are set) and `psql` is
  absent.
  *Evidence:* `probe: which psql` prints nothing;
  `.pre-commit-config.yaml:28-33` declares the validation hook with
  `pass_filenames: false`; `scripts/tf_validate.sh:8-12` lists the roots;
  `.loop/verdicts/S2-spike-postgres-vault-creds.plan-validator.md` records
  the hook exiting 0 offline on an initialized root.
- **P8.** `deployments/applications` is the only one of the three roots in
  `scripts/tf_validate.sh` carrying a `postgresql` provider, and it is
  itself a validated root.
  *Evidence:* `deployments/applications/providers.tf:50-57`;
  `probe: grep -n postgresql deployments/infrastructure/*.tf` prints
  nothing; `scripts/tf_validate.sh:8-12`.
- **P11.** A credential can travel from generation to Postgres to Vault to
  KV2 without ever landing in state, using only the pinned providers. This
  is what OQ3's exception to the F5/F6 invariant rests on.
  *Evidence:* `probe: terraform providers schema -json` in a scratch root
  pinned to vault 5.3.0, cyrilgdn/postgresql 1.26.0 and random 3.9.0 lists
  `random_password` as an ephemeral resource, `password_wo` /
  `password_wo_version` on `postgresql_role` and on the connection's
  `postgresql` block, and `data_json_wo` / `data_json_wo_version` on
  `vault_kv_secret_v2`. The same probe shows `random_password` the
  *resource* exposing `result`, which is why §7 forbids it here.
- **P9. UNCERTAIN — this is the spike.** A dynamically minted user can be
  given the grants and ownership an app needs through
  `creation_statements`. Nothing in the repo tests it and no anchor can
  settle it; requirement 2 and eval check 4 are the test. If it is false,
  Path A is not viable and R3 must not proceed on it.
  *Related evidence:* `deployments/applications/database.tf:69-72` shows
  every app object owned by a static role, which is why the question is
  open.
- **P10. UNCERTAIN — this is the spike.** Whether a PG18 OAuth validator
  module exists that accepts Vault- or Nomad-issued JWTs is not
  established. The previous version of this plan asserted the negative
  without checking; subticket 7 investigates it in a one-hour time box and
  records whichever answer it finds, including "not established".
  *Related evidence:*
  `.loop/verdicts/S2-spike-postgres-vault-creds.plan-validator.md`
  identifies the unchecked assertion.

## What S2 hands S1

*(Added 2026-08-03. `.loop/plans/S1-spike-boundary-evaluation.md:3` lists
S2 in `depends_on`, and `:322-324` names S2 a hard blocker so the Boundary
evaluation can test the real "keep" path — Vault credential engines — end
to end, fixing the spike order as S2 then S1. The previous cleanup step
destroyed the engine, so S2 completing did not discharge that blocker.)*

S2 leaves standing, deliberately:

- the `database` secrets engine mount,
- `vault_database_secret_backend_connection.postgres_poc` against firebat
  PG18, authenticated as `vault-dbengine-admin`,
- `vault_database_secret_backend_role.poc` with its short TTLs,
- the `vault-dbengine-admin` Postgres role itself.

S2 destroys: the throwaway Nomad job, its `vault_policy`, its
`vault_jwt_auth_backend_role`, and the `s2_poc_scratch` table.

S1 therefore inherits a working `database/creds/<poc-role>` path it can
point Boundary at, and does not rebuild the engine. S1 owns the separate
question of whether Boundary is needed at all: Nomad WI already covers
machine access to Postgres, so Boundary's case rests on *human* access —
brokered sessions, session recording, and removing the direct network path
to 5432. S2 records that framing as a finding and decides nothing about it.

## 11. Open questions

1. **RESOLVED 2026-07-25 — the PoC is proven live.** This question is
   struck. It claimed the gate "cannot reach the live Vault or firebat
   Postgres" and that "the repo has no `terraform validate` recipe or CI",
   both of which §8 refutes. The one real gap is `psql`, handled in §8.

2. **RESOLVED 2026-08-03 — the Vault DB connection uses a dedicated
   admin.** Operator confirmed: create `vault-dbengine-admin` (§10
   subticket 2), leave Vault-managed root rotation off for the spike, and
   never point the connection at the real `localstack` root. Eval row 2
   enforces it at a 100% threshold.

3. **RESOLVED 2026-08-03 — Terraform owns the mount and `database/config/`,
   in the applications root.** Operator settled the fork this ticket was
   blocked under. Two parts:
   - *Ansible vs Terraform.* F5 and F6 established a config-split
     invariant: Ansible owns the mount and `config/` for Vault engines
     needing a privileged external credential, precisely because that
     credential must stay out of Terraform state, which lives in a Consul
     backend (`deployments/infrastructure/consul_deploy_role.tf:7-15`,
     `deployments/infrastructure/nomad_deploy_role.tf:32-35`). The
     write-only chain in §7 item 2 satisfies that rationale directly: with
     `ephemeral "random_password"` feeding `password_wo` on the role, on the
     connection, and `data_json_wo` on the KV2 copy, the credential never
     enters state. F5 and F6 predate those attributes.
     **The exception stands only if the chain is built as specified.** A
     plain `random_password` writes `result` to state in cleartext, which
     would put a `CREATEROLE` Postgres admin in the Consul backend — the
     exact thing the invariant exists to prevent — and the exception would
     collapse. R3 inherits the argument and the condition together.
   - *Which root.* Applications, not infrastructure — see §7. The
     infrastructure root has no `postgresql` provider, so
     `vault-dbengine-admin` cannot be created there, and splitting the two
     across roots would impose an apply-order constraint on a throwaway
     spike.

4. **Scope of the authorization path.** Grant `database/creds/*` (all
   roles) or a single-role path for the PoC? **Resolved:** scope the
   `vault_policy` to the one PoC role, keeping blast radius minimal. R3
   decides the production shape (likely per-job or per-namespace scoping
   mirroring the existing KV path templating).

5. **How does R3 handle the rotation wrinkle at rollout?** The spike only
   needs to characterize the failure. **Resolved:** record the options
   (Nomad template `change_mode`, pool `max_lifetime` < lease TTL, app
   reconnect-on-auth-error) and defer the choice to R3; do not decide it
   here.

6. **Lease/TTL values for the PoC role.** Short TTL makes the rotation
   test fast but is arbitrary for the spike. **Resolved:** use a
   deliberately short `default_ttl` and `max_ttl` (minutes) purely to
   exercise expiry quickly, and note that R3 must set
   production-appropriate TTLs.
