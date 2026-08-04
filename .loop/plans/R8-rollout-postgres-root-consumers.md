---
epic = "rollout"
depends_on = ["R7-rollout-postgres-consumer-cutover"]
priority = 3
summary = "Convert the three consumers that authenticate as the `localstack` Postgres root — the postgres-exporter sidecar, backup-postgres's pg_dumpall, and the applications-root postgresql provider — off that shared root, so Vault-managed root rotation becomes possible at all."
stub = true
---
# Ticket: rollout-postgres-root-consumers

## Triggered by

Split out of `R7-rollout-postgres-consumer-cutover` on the operator's call
2026-08-04. R7 converts the application jobs, which is mechanical once R3
proves the pattern. These three are a different and riskier problem, and
bundling them risked the easy work stalling behind the hard work.

The plan-validator then found that R7 asserted "a follow-up ticket owns
that" while its own Q8 admitted "no ticket does today"
(`.loop/verdicts/R7-rollout-postgres-consumer-cutover.plan-validator.md`,
finding P23). This ticket is that owner.

## Vision & rough premises

- P1 (VERIFIED, S2 measured it live 2026-08-03): rotating the `localstack`
  root breaks three consumers at once, which is why S2 built a dedicated
  `vault-dbengine-admin` instead and left root rotation disabled
  (`deployments/applications/database-secrets-poc.tf:78-82`).
- P2 (VERIFIED): the three consumers are the postgres-exporter sidecar
  (`deployments/infrastructure/services/postgres.hcl:88-130`, DSN at
  `:122-130`), `backup-postgres`'s `pg_dumpall`
  (`deployments/infrastructure/services/backup-postgres.hcl:29`, credential
  at `:36-37`), and the applications-root `postgresql` provider
  (`deployments/applications/providers.tf:50-57`, reading
  `default/postgres/localstack` via
  `deployments/applications/services.tf:16-19`).
- P3 (VERIFIED): the first two run inside Nomad, so they have workload
  identities and can follow R7's per-job JWT role pattern. The third does
  not: Terraform runs outside Nomad, so it needs either a human OIDC login
  or a deploy-time identity. That asymmetry is the ticket's real content.
- P4 (UNVERIFIED): whether the exporter can take a least-privileged role at
  all. `postgres_exporter` wants `pg_monitor`; whether that plus a dynamic
  user covers every metric it currently collects is unmeasured.
- P5 (UNVERIFIED): whether `pg_dumpall` works as a non-superuser. It dumps
  globals including roles and passwords, which normally wants superuser, so
  the backup may not be convertible without changing what it backs up.
- P6 (UNVERIFIED, and the reason this is not just R7 again): even after all
  three convert, enabling Vault-managed root rotation means Vault owns the
  `localstack` password. Nothing has established what else authenticates as
  `localstack` outside the repo — a psql session, a GUI, a cron on a host.

## Non-goals

- Not converting the application jobs. That is R7.
- Not enabling root rotation speculatively. Rotation is the last step and
  only once P4, P5 and P6 are settled.

## Open questions

1. Does the exporter keep full metric coverage under `pg_monitor` plus a
   dynamic user? Recommendation: measure before designing, by diffing the
   metric set as the root against the same as a candidate role.
2. Can `pg_dumpall` run without superuser, and if not, does the backup
   change shape (`pg_dump` per database plus a separate globals dump) or
   keep a static credential with a documented exception?
3. What identity does the applications-root `postgresql` provider use?
   This overlaps `F8-foundation-deployer-provider-cutover`, which is
   blocked on its own BROKEN verdict. Recommendation: check whether F8
   already owns this before designing anything.
4. Is Vault-managed root rotation the actual goal, or is "nothing shares
   the root" enough? The rotation is the risky half and may not be worth
   it on its own.

## Premises / assumptions

See "Vision & rough premises" above — P1-P6. P1-P3 are verified against
the repo and against S2's live measurements; P4-P6 are UNCERTAIN and are
what flesh-out must settle.
