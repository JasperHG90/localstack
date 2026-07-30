---
verdict: fail
---

# Plan review: R3-rollout-postgres-vault-db-creds (pass `plan-validator`)

Plan fingerprint verified locally with `sha256sum`:
`4bdd1e4352d76fd13eae62554e8bce3474bb35f50989812e9f2fd3c5d1ac4bf5` matches
the briefing. The `plan:` line is deliberately OMITTED because this is a
`fail` and a failing verdict must not authorize the `PLANNING -> READY` flip.

## Premise verdict

**BROKEN.** Gate verdict: **fail**.

R3 was authored 2026-07-24. Since then its own dependency S2 was re-planned
on 2026-07-25 with the *opposite* answer on R3's central authorization
mechanism, F5/F6 shipped a config-split invariant that contradicts R3's
resolved Q2, a new ticket F9 took ownership of the very policy R3 plans to
edit, and B1 (2026-07-29) shifted every `deployments/applications/*.tf`
anchor R3 cites. Five load-bearing assumptions break; two more are
internally self-contradictory; one is the spike's unresolved core that R3
asserts as settled.

## Load-bearing assumptions

### P1 — "R3 extends the shared `nomad-workloads` Vault policy to grant `database/creds/<role>`" — **BREAKS**

This is R3's most pervasive claim. It appears as Requirement 3 (`plan:175-180`,
"mandatory"), a **edit** in the Code surface (`plan:239-242`), Subticket 3
(`plan:431-434`), Risk failure mode 1 (`plan:397-400`), Eval scenario 7
(`plan:362-371`) and eval row 8 (`.loop/evals/R3-…md:22`).

Its own dependency now forbids it. S2 was corrected on 2026-07-25:

- `/home/vscode/workspace/.loop/worktrees/A1-audit-plan-premise-sweep/.loop/plans/S2-spike-postgres-vault-creds.md:169-182`
  — "**DO NOT grant `database/creds/*` by editing the shared Ansible
  policy.** *(Corrected 2026-07-25: this plan previously made editing
  `vault_nomad_workloads.hcl.j2` its central wrinkle …)*" and instructs
  mirroring F3's per-job pattern instead.
- `S2-spike-postgres-vault-creds.md:243-247` — the same template is listed
  **DO NOT MODIFY**.

The replacement pattern is live and verifiable in the repo and cluster:
`deployments/infrastructure/acme.tf:41` (`vault_policy.acme_tls_write`),
`:66` (`vault_jwt_auth_backend_role.acme`), `:87`
(`token_policies = ["nomad-workloads", vault_policy.acme_tls_write.name]`),
`:109` (`vault_role` passed into the jobspec). Live confirmation:
`vault list auth/jwt-nomad/role` returns `acme` and `nomad-workloads`;
`vault policy list` returns `acme-tls-write`.

Independently, a ticket created after R3 now owns that file and is pushing
it the *other* direction (narrowing, not widening):
`.loop/plans/F9-foundation-scope-nomad-workloads-policy.md:1-7` and
`:56-66` ("The mechanism for a narrower grant already exists and is proven:
the acme job's `acme.tf:41-90` …"). F9 is stage `ready`
(`.loop/ledger.json`), and R3's `depends_on` (`plan:3`) does not name it.

### P2 — "S2 concluded Path A; R3 implements that outcome and must not consider Path B" — **BREAKS** (inlined conclusion)

`plan:39-41` ("This ticket **implements the outcome of S2** … along **Path
A** — the mature, recommended path") and non-goal `plan:134-137` ("S2
evaluated alternatives; this ticket commits to Path A").

S2 has **never run** (stage `ready`, `.loop/ledger.json`), and its
2026-07-25 correction explicitly removed the pre-mandated conclusion and
added a falsifier that can block R3:

- `S2-spike-postgres-vault-creds.md:115-120` — "A decision doc that
  **reaches** a recommendation, rather than one mandated here. *(Corrected
  2026-07-25 … A spike whose conclusion is fixed in advance cannot de-risk
  anything …)*"
- `S2-spike-postgres-vault-creds.md:123-128` — "state the **falsifier** up
  front … if a dynamically minted user cannot be given the grants and
  ownership an app needs without unacceptable `creation_statements`
  complexity, **Path A is not viable and R3 must not be unblocked on it**."

R3 asserts the spike's verdict as settled fact and forbids the alternative
the spike is supposed to keep open. Textbook defect class 2.

### P3 — "The database secrets-engine mount + connection config belong in Terraform (`deployments/infrastructure`)" — **BREAKS** (stale premise)

R3's resolved fork `plan:508-511` ("DB secrets-engine mount + connection in
`infrastructure`"), Requirement 1 `plan:155-164`, Subticket 1 `plan:422-426`.

F5 and F6 are `done` (`.loop/ledger.json`) and shipped an explicit,
in-repo-documented invariant that says the opposite for exactly this engine
shape. `deployments/infrastructure/consul_deploy_role.tf:7-15`:

> The `consul` secrets engine mount, its `config/access` (which holds the
> Consul management token) … are all owned by Ansible bootstrap … Each
> requires the Consul management token, which **the config-split invariant
> keeps out of Terraform**.

Same in `deployments/infrastructure/nomad_deploy_role.tf:33-35`. Terraform
state lives in a Consul backend (`deployments/infrastructure/backend.tf:1-3`),
which is why the invariant exists. `database/config/<conn>` holds a Postgres
superuser credential — the identical shape. S2 raises exactly this as an
unsettled operator fork that R3 would inherit
(`S2-spike-postgres-vault-creds.md:456-467`: "§7 puts both the mount and the
connection config in Terraform, quietly departing from the pattern R3 would
then inherit at production scale … Do not pick silently."). R3 resolved it
silently, in the direction the invariant rejects, and never mentions the
`password_wo` / `password_wo_version` write-only-attribute technique S2
identified as the way to keep the credential out of state
(`S2-…md:222-231`).

### P4 — The `deployments/applications` `path:line` anchors resolve — **BREAKS**

B1 shipped 2026-07-29 (`git log`: `ac3267b B1-bifrost-native-auth-and-virtual-keys`)
and added a `bifrost` role, shifting `database.tf` by ~9 lines and
`services.tf` by up to ~100. Every R3 anchor into these files is now wrong:

| R3 claim | Actual |
|---|---|
| `database.tf:47-51` (`random_password.password`) | `deployments/applications/database.tf:56-60` |
| `database.tf:53-58` (`postgresql_role.role`) | `database.tf:62-67` |
| `database.tf:60-68` (databases they own; cited 4×) | `database.tf:69-77` |
| `database.tf:88-96` ("the reader grants"; cited 4×) | `database.tf:97-105`. Lines 88-96 are the body of `postgresql_extension.extension` — a *different resource* |
| `services.tf:97-107` (phoenix) | `nomad_job.phoenix` at `deployments/applications/services.tf:105` |
| `services.tf:147-163` (memex) | `nomad_job.memex` at `services.tf:159-178` |
| `services.tf:186-200` (mlflow) | `nomad_job.mlflow` at `services.tf:284-293` |
| `providers.tf:46-53` (postgresql provider; cited 4×) | `deployments/applications/providers.tf:50-57` |

`database.tf:88-96` and `services.tf:186-200` are the sharp ones: they
resolve to *real but wrong* content, so an implementer copying the "reader
grants" from `88-96` copies extension wiring instead.

Anchors that DO hold: `deployments/infrastructure/secrets.tf:2-7`, `:68-88`;
`deployments/infrastructure/services/postgres.hcl:1,9,14,47,52,70-80,122-130`
(note `static = 5432` is line **14**, not 13);
`deployments/applications/secrets.tf:1-9,11-18,22-29,53-60`;
`services/phoenix.hcl:57-66`; `services/mlflow.hcl:45-60`;
`services/memex.hcl:44-60`, `:114-135`, `:136-137`;
`deployments/applications/services.tf:16-19`;
`bootstrap/roles/nomad_server/templates/nomad.hcl.j2:37-46`;
`bootstrap/roles/nomad_server/tasks/main.yml:207-245`;
`vault_nomad_workloads.hcl.j2:1-24` (exactly 24 lines).

### P5 — "The per-service login roles are `ducklake_owner`, `ducklake_reader`, `memex`, `phoenix`, `mlflow`" (`plan:71-73`) — **BREAKS** (stale content behind a resolving anchor)

`deployments/applications/database.tf:2-8` still resolves, but the list is
now six: line 8 is `"bifrost"`, added by B1. R3's migration-path
requirement 7 (`plan:199-202`) enumerates consumers to convert or leave
static and omits an entire Postgres role that exists today. Related: memex's
task now reads a **fourth** KV path added by B1
(`services/memex.hcl:149,156,159`, `bifrost_key_secret`, wired at
`services.tf:174`), which materially worsens the "one token per task"
trade-off S2 flags for R3 (`S2-…md:183-188`) — a dedicated per-job role must
re-grant all four.

### P6 — The plan's chosen first service is internally consistent — **BREAKS**

The resolved fork picks **memex** (`plan:499-506`) against the planner's
recommendation. But the eval file was never updated:
`.loop/evals/R3-rollout-postgres-vault-db-creds.md:3` — "One real service
(**recommended phoenix, Q1**)"; `:11` — "Depends on: F1 … and S2 (Path A
design)"; and the Requirements/Evals prose still leads with phoenix
(`plan:311-312`). Eval row 4 (`evals:18`) leads with the reader-role probe
(`create table` denied) — memex is an **owner** role
(`database.tf:69-77`, `owner = postgresql_role.role[each.value.owner].name`,
`alter_object_ownership = true`), for which the row only says "a
cross-schema/forbidden object instead" without naming one. The scored
contract does not describe the ticket that was actually decided.

### P7 — "Authenticate the connection with the existing superuser credential" — **BREAKS** (self-contradiction, and an unowned prerequisite)

Requirement 1 `plan:155-164` and Subticket 1 `plan:422-426` say authenticate
with the existing `localstack` superuser from
`deployments/infrastructure/secrets.tf:68-88`. Resolved fork Q3
(`plan:512-515`) says "**Give Vault its own Postgres management user**".
These are different designs and both are in the plan. Worse, **no subticket
creates that management user**, and the only `postgresql` provider is in the
opposite Terraform root from where Q2 places the engine
(`deployments/applications/providers.tf:50-57`) — the identical "missing
owner" gap S2's review already flagged
(`S2-…md:421-427`).

### P8 — "`just pre_commit` is the single blessed gate and runs offline with no credentials" (`plan:275-291`) — **BREAKS**

The hook inventory is accurate (`.pre-commit-config.yaml:1` exclude,
`nomad-fmt` 16-21, `terraform-fmt` 22-27, `terraform-validate` 28-33;
`scripts/tf_validate.sh:8-12` lists the three roots and inits
`-backend=false`). But R3 omits the worktree prerequisite S2 documents:
`S2-…md:258-263` — "run `just worktree_setup <path>` (`justfile:30-32`) BEFORE
the first gate, or `terraform-validate` dies on the gitignored `.ssh/id_rsa`".
Verified: `justfile:30-32` symlinks `.ssh`;
`deployments/infrastructure/services.tf:290` and
`deployments/applications/services.tf:97` both call
`file("${path.root}/../../.ssh/id_rsa")`; and `ls .ssh` in this worktree
returns "No such file or directory". The hook has `pass_filenames: false`, so
it fires on every invocation. R3's gate section is not runnable as written in
a loop worktree. Also `plan:277` cites `justfile:16-18` for `pre_commit`; the
recipe is at `justfile:18-19`.

### P9 — The evals are runnable as written — **BREAKS**

Four of the seven eval rows and eval scenarios 3,4,6 invoke bare `psql`
(`plan:337-343`, `:358`; `evals:17,18,21`). `which psql` returns nothing in
this environment, and S2 already recorded the gap and the workaround
(`S2-…md:265-270`: "**Environment gap: `psql` is NOT installed here.** …
`docker run --rm postgres:18 psql …`"). R3 names no mechanism.

Shape-check audit (required by the briefing): **no instance found.** Every
scorer in `.loop/evals/R3-…md:15-22` is a `deterministic check` on a `vault
read` / `psql` / `nomad job status` with an asserted output substring, except
row `:20` which is `model + rubric` at 4/5. None is `ls`, `grep`, or
file-existence, so none would pass against wrong file content.

### P10 — "No database secrets engine exists; the only engine is KV2" — **HOLDS**

Live: `vault secrets list` returns `bootstrap/ consul/ cubbyhole/ identity/
nomad/ secret/ sys/` — no `database/`. Repo: `vault_mount.kvv2` at
`deployments/infrastructure/secrets.tf:2-7`. Caveat on the plan's wording
"**The only Vault engine that exists is KV2**" (`plan:61`): `consul/` and
`nomad/` engines are live (F5/F6, both `done`) and their Terraform lives in
`consul_deploy_role.tf` / `nomad_deploy_role.tf`. The KV2-only claim is
stale; the operative sub-claim (no database engine, no
`vault_database_secret_backend_*` resource) holds.

### P11 — "The `nomad-workloads` policy grants no `database/creds` path" — **HOLDS**

Live `vault policy read nomad-workloads` returns exactly the four KV blocks
plus `bootstrap/data/*` read/create/update and `bootstrap/metadata/*` list.
No `database/` path. Matches
`bootstrap/roles/nomad_server/templates/vault_nomad_workloads.hcl.j2` (24
lines). Note `user_claim` is `/nomad_job_id`
(`bootstrap/roles/nomad_server/files/vault_role_nomad_workloads.json`), but
the policy templates against `metadata.nomad_job_id`, which comes from
`claim_mappings` in the same file — the plan's phrasing at `plan:172-174`
conflates the two; harmless but imprecise.

### P12 — "F1 (the dependency) is already deployed" (`plan:426`) — **HOLDS in substance, false as stated**

F1 is stage `ready`, not `done` (`.loop/ledger.json`), and F1 is a
documentation-plus-test-job ticket
(`.loop/plans/F1-foundation-nomad-wi-jwt-trust.md:5`, `:23-32`). The
underlying trust R3 needs is live independently of the ticket: `vault auth
list` shows `jwt-nomad/`, `vault list auth/jwt-nomad/role` shows
`nomad-workloads`, and the Ansible that built it is at
`bootstrap/roles/nomad_server/tasks/main.yml:207-245`. The plan's claim is
factually wrong about the ticket and right about the cluster.

### P13 — Environment/target facts (firebat:5432, PG18, running jobs, provider version) — **HOLDS**

`getent hosts firebat` returns `192.168.2.30`. `nomad job status postgres`:
`Status = running`, 1 alloc. `nomad job status memex`: running, resubmitted
2026-07-29. Image `docker.io/pgvector/pgvector:pg18-trixie`
(`postgres.hcl:52`). Vault provider `~>5.3.0`
(`deployments/applications/providers.tf:7-10`) does carry
`vault_database_secret_backend_connection` / `_role`. Minor: the exporter DSN
hardcodes `192.168.2.30:5432`, not the hostname (`postgres.hcl:124`), so the
eval's "`connection_url` targeting `firebat:5432`" (`evals:15`) prejudges a
form the repo does not use.

### P14 — "A dynamic user can be given exactly the static role's grants, including ownership" (`plan:165-174`, `:411-414`) — **UNCERTAIN**

R3 states this as a mirroring exercise ("reproduce `database.tf` grants
exactly"). It is not obviously one:
`deployments/applications/database.tf:69-77` sets database **ownership** to
the static role with `alter_object_ownership = true`, and objects created by
the static role are owned by it — a per-request dynamic user cannot inherit
ownership without role-membership plus `SET ROLE` or default-privilege
plumbing that R3 never specifies. S2 names this its "hardest unknown"
(`S2-…md:139-152`) and makes it the falsifier for Path A. I cannot settle it
from the repo or a read-only cluster probe, so: UNCERTAIN — which is exactly
why it must remain the spike's to answer, not R3's to assume.

## Most dangerous assumption

**P2 — that S2 has concluded Path A.** If S2 runs and its falsifier fires
(P14: dynamic users cannot be given the app's grants and ownership without
unacceptable `creation_statements` complexity), S2 itself says "R3 must not
be unblocked on it" (`S2-…md:126-128`). R3 has already spent its non-goals
forbidding the alternative. Every other finding here is a repair; this one
decides whether the ticket should exist in its current form.

Runner-up for blast radius: **P1**, which is woven through five sections and
would have an implementer edit a cluster-wide shared policy that both R3's
dependency and F9 now say to leave alone.

## Required fixes

1. **Replace Requirement 3, the `vault_nomad_workloads.hcl.j2` code-surface
   edit, Subticket 3, Risk failure mode 1, eval scenario 7 and eval row 8**
   with the per-job pattern: a dedicated `vault_policy` +
   `vault_jwt_auth_backend_role` on `jwt-nomad`, selected via
   `vault { role = … }`, mirroring `deployments/infrastructure/acme.tf:41-90`
   and `services/acme.hcl`. Carry S2's one-token consequence
   (`S2-…md:183-188`): the dedicated policy must ALSO re-grant memex's KV
   reads — now four of them, including `bifrost_key_secret`
   (`services/memex.hcl:132,139,124,149`). Add `F9-foundation-scope-nomad-workloads-policy`
   to `depends_on` or state explicitly why the two do not collide.
2. **Un-inline S2's conclusion.** Reword `plan:39-41` and non-goal
   `plan:134-137` so Path A is the *expected* outcome conditional on S2,
   and add S2's falsifier verbatim as an explicit precondition: if S2's
   grant/ownership test fails, R3 does not proceed.
3. **Re-anchor every `deployments/applications` citation** per the P4 table.
   In particular stop citing `database.tf:88-96` as the reader grants (it is
   `97-105`; `88-96` is `postgresql_extension`) and `services.tf:186-200` as
   mlflow (it is `284-293`). Update the role list at `plan:71-73` to include
   `bifrost` and decide its migration disposition in Requirement 7.
4. **Reopen Q2 against the F5/F6 config-split invariant.** Cite
   `consul_deploy_role.tf:7-15` and `nomad_deploy_role.tf:33-35`, and either
   follow it (Ansible owns the `database/` mount and `config/`, Terraform
   owns only the role) or argue the exception explicitly. If the connection
   config stays in Terraform, specify `password_wo` / `password_wo_version`
   and keep the credential out of `connection_url`, given state is in a
   Consul backend (`backend.tf:1-3`).
5. **Resolve the P7 contradiction.** Pick one admin identity — the Q3
   resolution (dedicated Vault management user) or Requirement 1's existing
   superuser — make the plan say only that, and add a named subticket that
   creates the management role, naming which Terraform root owns it given
   the only `postgresql` provider is at `providers.tf:50-57`.
6. **Regenerate `.loop/evals/R3-rollout-postgres-vault-db-creds.md` for
   memex.** Fix the DoD line `:3` ("recommended phoenix"), replace row `:18`'s
   reader-role probe with a concrete owner-role forbidden action, and align
   the eval with whichever authorization mechanism fix 1 lands on.
7. **Fix the gate section.** Add `just worktree_setup <path>`
   (`justfile:30-32`) as a stated prerequisite before the first
   `just pre_commit`, citing `services.tf:290` / `:97`. Correct the
   `pre_commit` anchor to `justfile:18-19`. Name the `psql` mechanism
   (`docker run --rm postgres:18 psql …` or run from inside the alloc) in
   every eval row that shells out to `psql`.
8. **Correct two statements of fact.** `plan:61` "The only Vault engine that
   exists is KV2" — `consul/` and `nomad/` are live (F5/F6, `done`).
   `plan:426` "F1 already deployed" — F1 is stage `ready`; the underlying
   `jwt-nomad` trust is live via Ansible bootstrap, which is what R3 actually
   depends on. Say that instead.

## Method note

All cluster interaction was read-only: `vault secrets list`, `vault auth
list`, `vault policy list`, `vault policy read nomad-workloads`, `vault list
auth/jwt-nomad/role`, `vault read auth/jwt-nomad/role/*`, `nomad job status
postgres`, `nomad job status memex`, `getent hosts firebat`, `which psql`. No
write, apply, or mutating git command was issued. `terraform validate` was
NOT run, because its `init -backend=false` writes `.terraform/` into the
repo; P8 rests on the file evidence and S2's recorded finding instead.
