---
epic = "spike"
depends_on = []
priority = 35
summary = "Spike: prove Vault's database secrets engine minting short-lived Postgres users on the existing PG18, consumed by a Nomad job via Workload Identity, and write up the credential-rotation-in-pools failure mode. Deliverable is a decision doc plus a proof of concept, not the rollout (that is R3)."
tags = ["spike", "postgres", "vault", "secrets"]
---

# S2 — Spike: Vault database secrets engine for short-lived Postgres creds

## 1. Title

Prove out Vault's database secrets engine minting short-lived Postgres
users on the existing PG18 on firebat, consumed by a Nomad job via Nomad
Workload Identity, and document the credential-rotation-in-pools wrinkle.
Deliverable is a decision doc plus a working proof-of-concept, not a
rollout.

## 2. Size / Effort

**M (spike, time-boxed).** Effort is driven by three things: (a) standing
up a new Vault secrets engine and a Vault policy path that does not exist
yet against a live cluster, (b) authoring a throwaway PoC Nomad job that
reads `database/creds/<role>` instead of a KV path, and (c) the
investigative write-up of the rotation-in-connection-pools failure mode.
The code surface is small; the cost is the live proof and the analysis.

This is a spike. Success is proving the mechanism and writing the
findings down, NOT migrating any real service. Full rollout is ticket R3
and is explicitly out of scope here (see Non-goals).

## 3. Triggered by

The home-lab auth epic. Confirmed decisions: Vault is the OIDC IdP for
humans and Nomad Workload Identity (WI) JWTs are the machine identity.
Today every Postgres consumer holds a long-lived static password minted
by Terraform and parked in Vault KV2 (see Context). The epic wants
short-lived, Vault-brokered Postgres credentials. This ticket is the
spike that decides whether Path A (Vault database secrets engine) is the
path, and surfaces the wrinkles before R3 commits to a rollout. It shares
findings with S1 (Boundary), which would broker these same Vault-issued
Postgres creds.

## 4. Context

Today's Postgres auth is entirely static, long-lived passwords:

- The Postgres job runs on firebat, image `pgvector/pgvector:pg18-trixie`,
  static port 5432, at `deployments/infrastructure/services/postgres.hcl:52`
  and `:13-16`, pinned to firebat at `:7-10`.
- The admin/root role password is a Terraform `random_password` written
  once to Vault KV2 at
  `deployments/infrastructure/secrets.tf:68-88` (key
  `default/postgres/localstack`). The KV2 mount itself is defined at
  `deployments/infrastructure/secrets.tf:2-7`.
- The Postgres job reads that static credential back through a
  Vault-templated `template { env = true }` block at
  `deployments/infrastructure/services/postgres.hcl:70-80`
  (the `vault {}` block at `:70`, the template at `:72-80`). The job is
  rendered by `nomad_job.postgres` which passes the KV path in at
  `deployments/infrastructure/services.tf:293-298`.
- Per-application roles (memex, phoenix, mlflow, ducklake_*) are also
  static `random_password` logins created by the PostgreSQL provider at
  `deployments/applications/database.tf:47-58`, with their passwords
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
  **It grants read only on `secret/data/<namespace>/<job_id>/*` and the KV
  mount. It does NOT grant any `database/creds/*` path.** This is the
  central wrinkle: a Nomad job cannot read dynamic DB creds until this
  policy is extended.

What is wrong / missing: there is no `database` secrets engine mounted, no
Vault DB connection config pointing at firebat's Postgres, no role that
mints short-lived users, and no Vault policy path that would let a Nomad
workload read `database/creds/<role>`. Nothing proves the mechanism works
against PG18, and nobody has measured what happens to a long-lived
connection pool when its lease expires.

## 5. Non-goals / out of scope

- **No rollout.** Do not migrate memex, phoenix, mlflow, ducklake, the
  exporter sidecar, or the root role off their static KV2 passwords. That
  is ticket R3.
- **Do not delete or rewrite** the existing static-credential resources
  (`secrets.tf`, `database.tf`, the KV reads in the job HCLs). The PoC
  runs alongside them.
- **No human OIDC path implementation.** The doc should note that humans
  reach `database/creds/<role>` via Vault OIDC login, but implementing or
  testing the OIDC login flow is out of scope for this spike.
- **Path B is not built.** PostgreSQL 18 native OAuth bearer auth (`oauth`
  HBA method + validator module + device flow) is documented as a rejected
  alternative only. Do not add an `oauth` HBA entry or a validator module.
- **No Boundary work.** S1 owns Boundary; this ticket only records the
  shared finding that Boundary would broker these same creds.
- **No production password rotation** of the existing static roots.

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
   - record a real Path B evidence step: name the PG18 OAuth validator
     module, establish whether one exists that accepts Vault/Nomad-issued
     JWTs, and record the answer. Rejecting Path B on a rationale nobody
     checked is not evidence;
   - capture the rotation findings per requirement 4.
2. A working PoC, proven against the live firebat Postgres, of: the Vault
   `database` secrets engine enabled, a Vault DB connection to PG18, a
   role that mints a short-lived Postgres user, and a Nomad job that reads
   `database/creds/<role>` via Nomad WI and connects to Postgres with the
   minted credential.
   **The connection test must be a privileged operation against a real
   owned object, not `select 1`.** `select 1` needs only CONNECT and passes
   for a role with zero object privileges, so it proves authentication and
   nothing about viability. Point the PoC role at one real app database
   (memex or ducklake), write `creation_statements` — a REQUIRED attribute
   of `vault_database_secret_backend_role`, which this plan previously never
   mentioned — that reproduce the grants that role needs, and assert a
   read/write against an existing object owned by the static role.
   This is the ticket's hardest unknown: the applications layer owns every
   app object under a static role
   (`deployments/applications/database.tf:53-68`, `postgresql_database` with
   `owner = postgresql_role.role[...]`), and R3 names exactly this as its
   failure mode 4 — *"dynamic user lacks a grant the app needs, or ownership
   differs from the static role, so migrations or writes fail"*
   (`R3-rollout-postgres-vault-db-creds.md:409-412`). A spike that declares
   Path A proven while handing this to R3 undiminished has done nothing.
3. An explicit test of the known wrinkle: a long-lived connection pool
   holding a credential whose lease expires. Record the observed failure
   mode and the mitigation options.
   **Set a short `max_ttl` on the PoC role, not just `default_ttl`.**
   Nomad's template runner renews a renewable Vault lease continuously, so a
   dynamic DB credential expires at `max_ttl` — unset here, meaning Vault's
   768h default. As previously specified, this test renews quietly for 32
   days and reports nothing. Also name the pool apparatus: §7 describes the
   PoC job as "a minimal `driver = "podman"` job" with no pooling client, so
   the test currently has no subject.

Restrictions the repo enforces (cite where stated):

- **Secret-path convention.** Follow the epic convention
  `secret/data/<namespace>/<job_id>/<entry>` for any KV touch, and mirror
  the existing dynamic-secrets path style.
- **DO NOT grant `database/creds/*` by editing the shared Ansible policy.**
  *(Corrected 2026-07-25: this plan previously made editing
  `vault_nomad_workloads.hcl.j2` its central wrinkle, which would give every
  Nomad workload on the cluster read access to `database/creds/*` — for a
  throwaway spike — and require two live Ansible bootstrap re-runs, apply
  then revert.)* F3 already shipped the alternative in the same Terraform
  root, with the opposite answer: `acme.tf:50-65` makes the case in its
  comment, that the job gets its own JWT role and its own policy as a second
  role on the Ansible-owned mount, selected per-job via
  `vault { role = ... }`, leaving every other workload on the default role
  untouched. (F3 stated it first, in the `pki.tf` that T3 deleted; the
  archived plan keeps that wording.) Mirror it: `vault_policy` + `vault_jwt_auth_backend_role`
  bound to the PoC job, `vault { role = ... }` in the jobspec, shared policy
  untouched.
- **Record the one-token trade-off as a spike finding for R3.** A Nomad task
  holds exactly one Vault token, so a dedicated role's policy must ALSO
  carry the KV grants a converted job still needs (memex's `db-migrate`
  prestart, mlflow, phoenix). "Widen the shared policy" versus "per-job role
  that must re-grant KV" is precisely the decision a spike should make for
  R3, and neither option is free.
- **Never hardcode credentials; all secrets in Vault KV2** (CLAUDE.md, Key
  Conventions). The Vault DB connection's admin password must come from the
  existing `default/postgres/localstack` KV entry
  (`deployments/infrastructure/secrets.tf:74-88`), not a literal.
- **Podman, not Docker**, on cluster nodes (CLAUDE.md). The PoC job uses
  `driver = "podman"`, matching `postgres.hcl:31`.
- **Terraform state is in Consul**; providers `vault ~>5.3.0` and
  `nomad ~>2.5.0` are already declared at
  `deployments/infrastructure/providers.tf:1-24`. Reuse them; do not add a
  new provider.
- **Injection pattern.** Any job reads secrets via `vault {}` +
  `template { env = true }`, as in `postgres.hcl:70-80` and
  `memex.hcl:44-54`. The PoC must not invent a different mechanism.
- **Surgical changes** (CLAUDE.md §3): touch only what the PoC needs; do
  not "improve" adjacent static-credential code.
- **Docs are held to the slop-scan rule** (`.claude/rules/slop-scan-for-docs.md`):
  the decision doc must be thesis-first, evidence-backed, and free of the
  banned patterns. Prose wraps at 80 chars.

## 7. Code surface

New or changed files. Anchors are the existing patterns to mirror.

- `docs/postgres-vault-dynamic-creds-spike.md` — **new.** The decision
  doc: Path A recommendation, Path B rejection rationale, PoC runbook, and
  rotation-in-pools findings. Sits alongside existing design docs such as
  `docs/credential-rotation.md` (same directory, same audience).
- `deployments/infrastructure/database-secrets-poc.tf` — **new, PoC,
  clearly labelled throwaway.** Terraform that mounts the `database`
  secrets engine, configures a Vault DB connection to firebat PG18 using
  the admin creds ephemerally read from `default/postgres/localstack`, and
  defines one short-lived role (with `creation_statements` per requirement 2
  and a short `max_ttl` per requirement 3).
  **The ephemeral-read pattern does not transfer as cited.**
  `deployments/applications/services.tf:11-19` and
  `providers.tf:46-53` are *provider configuration*, the one context where
  ephemeral values are unconditionally legal; feeding an ephemeral value
  into an ordinary resource attribute is a hard Terraform error. For
  `vault_database_secret_backend_connection.postgresql` use
  **`password_wo` + `password_wo_version`** (write-only attributes present
  in the pinned vault 5.3.0 provider), and keep the credential OUT of
  `connection_url`. Reuse `var.secret_mount`
  (`deployments/infrastructure/variables.tf:1-4`) and the vault provider
  at `deployments/infrastructure/providers.tf:28`. NOTE: this lives in the
  infrastructure layer because that is where the Postgres job and its root
  KV entry live (`secrets.tf:68-88`, `services.tf:293-298`); see Open
  Questions on layer placement.
- `deployments/infrastructure/services/poc-dynamic-creds.hcl` — **new,
  throwaway PoC Nomad job.** A minimal `driver = "podman"` job with
  `vault {}` and a `template { env = true }` block reading
  `{{ with secret "database/creds/<role>" }}`, modeled on
  `postgres.hcl:70-80`. Connects to Postgres to prove the minted user
  works. Rendered by a `nomad_job` resource mirroring
  `services.tf:293-298`.
- `bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2` —
  **DO NOT MODIFY.** *(Corrected 2026-07-25; this was previously listed as
  "modify — the load-bearing wrinkle".)* Editing the shared policy grants
  every workload on the cluster `database/creds/*` and needs two live
  Ansible re-runs. Use the per-job pattern instead, below.
- `deployments/infrastructure/database-secrets-poc.tf` (same new file) —
  also carries the authorization: a `vault_policy` granting `read` on
  `database/creds/<role>` only, plus a `vault_jwt_auth_backend_role` on
  backend `jwt-nomad` bound to the PoC job's `nomad_job_id`/
  `nomad_namespace`, with `claim_mappings` replicated. Mirror
  `acme.tf:41-90` exactly. The PoC job then selects it with
  `vault { role = "<poc-role>" }` (pattern `services/acme.hcl:73-75`).

## 8. Tests & validation gates

**Prerequisite in a worktree:** run `just worktree_setup <path>`
(`justfile:30-32`, added in `3c12c7a`) BEFORE the first gate, or
`terraform-validate` dies on the gitignored `.ssh/id_rsa` that
`services.tf:287` evaluates — a failure unrelated to this ticket. The hook
has `pass_filenames: false`, so it runs on every gate invocation regardless
of what S2 touched.

**Environment gap: `psql` is NOT installed here.** `which psql` returns
nothing, and neither `.devcontainer/Dockerfile` nor `bootstrap.sh` installs a
Postgres client. Requirement 2's connection test therefore cannot run as a
bare `psql` invocation. Docker-in-docker is enabled, so
`docker run --rm postgres:18 psql ...` works; alternatively run the check
from inside the PoC alloc. Name whichever mechanism is chosen.

**Repo gate (what the loop runs):** `just pre_commit` runs
`pre-commit run --all-files` (root `justfile:18-19`). The hooks in
`.pre-commit-config.yaml` now include Terraform validation, so the PoC
`.tf` is gated, not just formatted:

- `nomad-fmt` (`nomad fmt -recursive`) on `*.hcl`
  (`.pre-commit-config.yaml:16-21`) formats the PoC Nomad job.
- `terraform-fmt` (`terraform fmt -check -recursive`,
  `.pre-commit-config.yaml:22-27`) fails on unformatted `.tf`.
- `terraform-validate` (`scripts/tf_validate.sh`,
  `.pre-commit-config.yaml:28-33`) runs `terraform validate` per root,
  and `deployments/infrastructure` is one of the three roots it validates
  (`scripts/tf_validate.sh:8-12`). It inits with `-backend=false`, so it
  validates offline without touching the Consul backend or credentials.
  This means the new `database-secrets-poc.tf` must be syntactically valid
  and internally consistent for the gate to pass.
- The generic hooks (`check-json`, `check-ast`, `check-merge-conflict`,
  `check-yaml --unsafe`, `debug-statements`, `detect-private-key`,
  `end-of-file-fixer`) still apply.

`.pre-commit-config.yaml:1` excludes `^\.(claude|loop)/`, so the new
`.hcl` and `.tf` files ARE checked while the ticket file is not.

**Decision-doc gate.** The new `docs/postgres-vault-dynamic-creds-spike.md`
is held to the markdown slop-scan (`.claude/rules/slop-scan-for-docs.md`):
run the three layers (P0 critical patterns, document economy, sentence
slop), verify prose wraps at 80 chars, and confirm `end-of-file-fixer`
leaves a trailing newline. The doc must be thesis-first — stating whatever
conclusion the evidence supports, NOT a pre-mandated one — and every
backticked identifier / cited path must resolve.

**Evals (live PoC acceptance).** The cluster is reachable this run:
`VAULT_ADDR`, `VAULT_TOKEN`, `NOMAD_ADDR`, `NOMAD_TOKEN`, and
`CONSUL_HTTP_ADDR` are set in the environment. The PoC is therefore proven
live, not merely documented. Run each check below and record its result in
the decision doc. Use the DEDICATED `vault-dbengine-admin` Postgres role
for the Vault DB connection (see Open Questions 2 and Risk assessment); do
NOT point the connection at the real `localstack` root creds, and do NOT
enable Vault-managed root rotation during the spike.

1. **DB engine + connection exist against PG18 on firebat.**
   Command: `vault read database/config/<poc-conn>`.
   Expect: the connection config prints with `plugin_name`
   `postgresql-database-plugin` and an `allowed_roles` list containing the
   PoC role; no error. Confirms the engine is mounted and points at
   firebat PG18.
2. **A PoC role mints a short-lived user.**
   Command: `vault read database/creds/<poc-role>`.
   Expect: a fresh `username`/`password` pair plus a non-zero `lease_id`
   and a short `lease_duration` (the deliberately short PoC TTL, Open
   Question 6). Confirms dynamic minting works.
3. **The minted user actually authenticates.**
   Command: `PGPASSWORD=<minted-pw> psql -h firebat -U <minted-user> -d
   <db> -c 'select 1'` (host per `postgres.hcl:7-10`, port 5432 per
   `postgres.hcl:13-16`).
   Expect: `?column?` / `1` returned. Confirms the role's grants let the
   ephemeral user connect and query.
4. **The throwaway Nomad job reads creds via its WI token.**
   Commands: run the PoC job, then `nomad job status <poc-job>`.
   Expect: allocation reaches `running`; its `template { env = true }`
   block reading `database/creds/<poc-role>` (modeled on
   `postgres.hcl:70-80`) renders, and the alloc connects to Postgres with
   the minted user. Run this once BEFORE applying the
   `vault_nomad_workloads.hcl.j2` policy edit to observe the WI token being
   DENIED on `database/creds/*`, and again AFTER, to prove the policy
   change (Code surface) is load-bearing.
5. **Rotation-in-pools wrinkle is exercised and recorded.**
   Command/setup: hold an idle pooled connection past the lease TTL, let
   Vault revoke the role, then check out from the pool. Force the
   idle-past-TTL condition so a silent client reconnect cannot mask it.
   Expect: record the observed behavior (existing connections vs. new
   checkouts after revocation) and at least one mitigation option (Nomad
   `change_mode = "restart"`/`"signal"` on the template, pool
   `max_lifetime` below the lease TTL, or app-level reconnect-on-auth-
   error). This is the spike's central finding; characterize it, do not
   fix it (Non-goals, Open Question 5).
6. **Doc deliverables exist.** The decision doc records: Path A proven
   (with the results of checks 1-5), the Path B rejection rationale
   (validator-library availability plus role mapping, per Requirements),
   and the rotation-in-pools findings from check 5.

**Cleanup.** After the live checks, tear down the PoC engine, role, and
job, and revert the `vault_nomad_workloads.hcl.j2` policy if the operator
wants the spike fully reversed, so no throwaway resources linger on the
cluster (Risk assessment: reversibility).

On completion return "done" plus a one-line summary naming which checks
passed live and what the rotation test observed.

**Eval marker.** The five-column Definition-of-Done scenarios for these
gates live at `.loop/evals/S2-spike-postgres-vault-creds.md` (author with the
`create-eval` skill before implementation).

## 9. Risk assessment

- **Blast radius (live steps).** The PoC touches a live Vault and the live
  firebat Postgres. Mounting a new `database` engine and creating a role
  is additive and low-risk. The real hazard is the Vault DB connection's
  admin user: the database engine wants a Postgres superuser/role-creator
  to mint users, and Vault may rotate that admin password. If the PoC
  points the connection at the real `localstack` root role and Vault
  rotates it, every existing static consumer that authenticates as
  `localstack` breaks. Mitigation: create a dedicated
  `vault-dbengine-admin` Postgres role for the PoC and do NOT enable
  Vault-managed root rotation during the spike. Flag in Open Questions.
- **Policy change.** Editing `vault_nomad_workloads.hcl.j2` affects EVERY
  Nomad workload's Vault policy, not just the PoC. Adding a scoped
  `database/creds/*` read is additive, but a mistake here widens all
  workloads' access. Keep it minimal and review the rendered policy.
- **Reversibility.** High. All PoC artifacts are throwaway and namespaced;
  the engine, role, and job can be destroyed. The policy edit is revertible
  by restoring the template and re-running the bootstrap task.
- **Likeliest failure modes.** (1) The WI token is denied on
  `database/creds/<role>` because the policy edit was not applied to the
  live Vault (Ansible re-run skipped). (2) `nomad fmt` reformats the PoC
  HCL and the loop must re-run the gate. (3) The rotation test is
  inconclusive because the pool's client silently reconnects, masking the
  failure — the runbook must force an idle-past-TTL condition.

## 10. Subtickets

Ordered, dependency-aware:

1. **Decision-doc skeleton.** Create
   `docs/postgres-vault-dynamic-creds-spike.md` with the **falsifier stated
   up front** (requirement 1), the Path A vs. Path B comparison, and
   placeholder sections for the PoC runbook, the grant/ownership result, and
   the rotation findings. The conclusion is written LAST, after the evidence
   exists. Verify: doc passes slop-scan layers and `end-of-file-fixer`.
2. **PoC Terraform.** Add `database-secrets-poc.tf`: mount `database`
   engine, configure the Vault DB connection to firebat PG18 via an
   ephemeral read of `default/postgres/localstack`, define one short-lived
   role. Verify: `just pre_commit` green; manual `terraform apply` mints a
   user via `vault read database/creds/<role>`.
3. **Vault policy extension.** Add the scoped `database/creds/*` read to
   `vault_nomad_workloads.hcl.j2`. Verify: rendered policy grants exactly
   the new path; manual re-run of the bootstrap policy task applies it.
4. **PoC Nomad job.** Add `poc-dynamic-creds.hcl` + its `nomad_job`
   resource; job reads `database/creds/<role>` via WI and connects.
   Verify: `nomad fmt` clean; manual run connects (denied before subticket
   3, allowed after).
5. **Rotation-in-pools test + findings.** Execute the pool-past-TTL test;
   write the observed failure mode and mitigation options into the doc.
   Verify: findings section names the concrete failure and at least one
   mitigation.
6. **Cleanup + doc finalize.** Tear down PoC resources; finalize the
   decision doc with the recommendation the evidence supports and the
   runbook. Verify: `just pre_commit` green; doc complete.

**Missing owner:** OQ2 and the evals require the Vault DB connection to
authenticate as a dedicated `vault-dbengine-admin` Postgres role, but no
subticket above creates it. It needs `CREATEROLE` and, per requirement 2,
membership in the app owner roles — and the repo's only `postgresql`
provider is at `deployments/applications/providers.tf:46-53`, the opposite
root from where OQ3 places the PoC. Assign its creation to a named subticket
and resolve the cross-root implication in OQ3 before implementing.

## 11. Open questions

1. **RESOLVED 2026-07-25 — the PoC is proven live.** This question is
   struck. It claimed the gate "cannot reach the live Vault or firebat
   Postgres" and that "the repo has no `terraform validate` recipe or CI",
   both of which §8 itself refutes: `terraform-validate` is a configured
   pre-commit hook (`.pre-commit-config.yaml:28-33`) and the cluster IS
   reachable from this environment (`VAULT_ADDR`, `NOMAD_ADDR`,
   `CONSUL_HTTP_ADDR` and their tokens are set). The two statements
   contradicted each other, leaving "done" undefined. §8 stands: the PoC is
   proven live, not merely documented. The one real gap is `psql`, handled
   in §8.

2. **Which admin identity does the Vault DB connection use to mint users?**
   Reusing the real `localstack` root role risks a cluster-wide outage if
   Vault rotates it. **Recommendation:** create a dedicated
   `vault-dbengine-admin` Postgres role for the PoC and leave Vault root
   rotation disabled for the spike. Needs an operator decision because it
   adds a role to the live DB.

3. **Layer placement of the PoC Terraform, AND the Ansible-vs-Terraform
   split this plan never asked about.** Postgres and its root KV entry live
   in `deployments/infrastructure/`, but the per-app DB roles and the
   PostgreSQL provider live in `deployments/applications/`
   (`providers.tf:46-53`). **Recommendation:** put the PoC in
   `infrastructure/`; revisit for R3.
   **The unasked half:** F5 and F6 established a config-split invariant for
   Vault engines needing a privileged external credential — Ansible owns the
   mount and `config/`, Terraform owns only the role, precisely because the
   management credential must stay out of Terraform state (which lives in a
   Consul backend, `backend.tf:2`). See `consul_deploy_role.tf:7-15` and
   `nomad_deploy_role.tf:32-35`. The database engine has that exact shape:
   `database/config/<conn>` holds a Postgres superuser credential. §7 puts
   both the mount and the connection config in Terraform, quietly departing
   from the pattern R3 would then inherit at production scale. The invariant
   is not absolute — F3 put `vault_mount.pki` in Terraform — but PKI needs no
   external privileged credential, which is the distinguishing criterion.
   *Operator must settle:* follow F5/F6 (Ansible owns mount + `config/`), or
   argue the exception explicitly. Do not pick silently.

4. **Scope of the policy path.** Grant `database/creds/*` (all roles) or a
   single-role path for the PoC? **Recommendation:** scope to the one PoC
   role for the spike to keep blast radius minimal; R3 decides the
   production shape (likely per-job or per-namespace scoping mirroring the
   existing KV path templating).

5. **How does R3 handle the rotation wrinkle at rollout?** The spike only
   needs to characterize the failure. **Recommendation:** record the
   options (Nomad template `change_mode`, pool `max_lifetime` < lease TTL,
   app reconnect-on-auth-error) and defer the choice to R3; do not decide
   it here.

6. **Lease/TTL values for the PoC role.** Short TTL makes the rotation
   test fast but is arbitrary for the spike. **Recommendation:** use a
   deliberately short default TTL (e.g. a few minutes) purely to exercise
   expiry quickly, and note that R3 must set production-appropriate TTLs.
