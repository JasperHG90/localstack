eval: S2-spike-postgres-vault-creds

Definition of Done: Path A (Vault database secrets engine) is proven live
against firebat PG18 — a short-lived Postgres user is minted, read by a
Nomad Workload-Identity job, and connects — the rotation-in-pools wrinkle
is characterized, and the decision doc records the proof plus the Path B
rejection, all without pointing the engine at the real root creds.

| Behavior | Input | Expected | Scorer | Threshold |
| --- | --- | --- | --- | --- |
| The Vault database engine is mounted and its connection points at firebat PG18 | `vault read database/config/<poc-conn>` | Config prints with `plugin_name` = `postgresql-database-plugin` and an `allowed_roles` list containing the PoC role; no error | deterministic check (`vault read database/config/<poc-conn>`) | 100% |
| The DB connection uses a dedicated PoC admin, never the real root creds, with root rotation left off | `vault read database/config/<poc-conn>` and inspect the configured admin identity | Connection `username` is the dedicated `vault-dbengine-admin` role, NOT the real `localstack` root; Vault-managed root rotation is not enabled | deterministic check (`vault read database/config/<poc-conn>`) | 100% |
| A PoC role mints a fresh short-lived Postgres user on demand | `vault read database/creds/<poc-role>` | A fresh `username`/`password` pair with a non-zero `lease_id` and a short `lease_duration` (the deliberately short PoC TTL) | deterministic check (`vault read database/creds/<poc-role>`) | 100% |
| The minted ephemeral user actually authenticates to Postgres and can query | `PGPASSWORD=<minted-pw> psql -h firebat -U <minted-user> -d <db> -c 'select 1'` | `?column?` / `1` is returned with exit code 0 | deterministic check (`psql -h firebat -U <minted-user> -c 'select 1'`) | 100% |
| The Nomad WI job's read of `database/creds/*` is DENIED before the policy edit and the job runs after it | Run the PoC job, then `nomad job status <poc-job>`, once before and once after applying the `vault_nomad_workloads.hcl.j2` edit | Before the edit the WI token is denied on `database/creds/*`; after the edit the allocation reaches `running` and connects to Postgres with the minted user | deterministic check (`nomad job status <poc-job>`) | 100% |
| The decision doc's rotation-in-pools finding and Path B rejection rationale are sound | Hold an idle pooled connection past the lease TTL, let Vault revoke the role, check out from the pool; then review `docs/postgres-vault-dynamic-creds-spike.md` | Doc records the observed pool behavior (existing vs. new checkouts after revocation) with at least one mitigation option, and rejects Path B on validator-library availability plus role mapping; reasoning is coherent and evidence-backed | model + rubric (adversarial review agent) | 4/5 |
